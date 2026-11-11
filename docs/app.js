// 거래대금 급증 스크리너 — data/index.json과 data/days/{일자}.json을 읽어 그린다.
// 일자 파일 구조는 surge/screen.py 머리말 참고. 투신 수급 탭은 data/flow/index.json과 data/flow/{일자}.json(surge/flow.py 머리말),
// 기관 수급 탭은 data/inst/index.json과 data/inst/{일자}.json(surge/inst.py 머리말).
(() => {
  const SLOTS = ["1005", "1205", "1405", "close"];
  const LABEL = { all: "종합", "1005": "10:05", "1205": "12:05", "1405": "14:05", close: "종가" };
  const WD = "일월화수목금토";
  const $ = (id) => document.getElementById(id);

  const state = { view: "surge", idx: null, docs: {}, day: null, slot: "all", mkt: "", sort: null,
    fidx: null, fdocs: {}, fday: null, flow: null, ftab: "t",
    iidx: null, idocs: {}, iday: null, inst: null, itab: "pow", imkt: "Q" };

  const fmt = (v, d = 0) => (v == null || isNaN(v) ? "–" :
    Number(v).toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const cls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "flat");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url} ${r.status}`);
    return r.json();
  }

  // ── 기준 설명 ─────────────────────────────────────────────────────────
  function renderRules(c) {
    const eok = (w) => fmt(w / 1e8);
    const scale = c.scale.map(([r, s]) => ({ s, t: `시장 내 거래대금 <b>${r}위</b> 이내` }));
    const turn = c.turnover.map(([p, s]) => ({ s, t: `회전율 <b>${p}%</b> 이상` }));
    const rows = [3, 2, 1].map((s) => `<tr><td class="stars">${"★".repeat(s)}</td>
      <td>${(scale.find((x) => x.s === s) || {}).t || ""}</td>
      <td>${(turn.find((x) => x.s === s) || {}).t || ""}</td></tr>`).join("");
    $("rules-body").innerHTML = `
      <p>시가총액 <b>${eok(c.min_mcap)}억</b> 이상 · 최근 <b>${c.base_days}거래일</b> 같은 시각 누적거래대금
        <b>중앙값의 ${c.multiple}배</b> 이상 · 누적거래대금 장중 <b>${eok(c.min_value["1005"])}억</b> /
        종가 <b>${eok(c.min_value.close)}억</b> 이상.</p>
      <p>등급은 두 기준에서 각각 별을 매기고 높은 쪽을 쓴다. 규모는 큰 종목에, 회전율(거래대금 ÷ 시가총액)은
        작은 종목에 유리해 서로 빈 곳을 메운다. 별이 없으면 배수로는 급증이지만 시장 전체로 보면 크지 않다는 뜻이다.</p>
      <table class="grade-tbl"><thead><tr><th></th><th>규모</th><th>손바뀜</th></tr></thead>
        <tbody>${rows}</tbody></table>
      <p>같은 날 여러 시각에 걸쳐 잡힐수록 일시적 쏠림이 아니라 하루 내내 이어진 급증이다.</p>`;
  }

  // ── 일자·시각 탭 ──────────────────────────────────────────────────────
  function renderDays() {
    $("days").innerHTML = state.idx.days.map(({ d, n }) => {
      const wd = WD[new Date(d + "T12:00:00Z").getUTCDay()];
      return `<button data-d="${d}" class="${d === state.day ? "on" : ""}">
        <span class="d">${d.slice(5)} <span class="w">${wd}</span></span>
        <span class="n">${n.all ?? 0}</span></button>`;
    }).join("");
    const on = $("days").querySelector(".on");
    if (on) on.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  function renderSlots(doc) {
    const keys = ["all", ...SLOTS];
    const count = (k) => k === "all" ? Object.keys(doc.stocks || {}).length
      : doc.slots?.[k] ? Object.keys(doc.slots[k].hits).length : null;
    $("slots").innerHTML = keys.map((k) => {
      const n = count(k);
      return `<button data-s="${k}" class="${k === state.slot ? "on" : ""}" ${n == null ? "disabled" : ""}>
        ${LABEL[k]}<span class="n">${n == null ? "–" : n}</span></button>`;
    }).join("");
  }

  // ── 표 ────────────────────────────────────────────────────────────────
  function buildRows(doc) {
    const stocks = doc.stocks || {};
    const hitSlots = (code) => SLOTS.filter((s) => doc.slots?.[s]?.hits?.[code]);
    if (state.slot === "all") {
      return Object.entries(stocks).map(([code, st]) => {
        const on = hitSlots(code);
        const hs = on.map((s) => doc.slots[s].hits[code]);
        return {
          code, st, on, cnt: on.length,
          grade: Math.max(...hs.map((h) => h[2])), mult: Math.max(...hs.map((h) => h[0])),
          price: st.p, chg: st.c, cap: st.cap, value: st.v, turn: st.turn,
        };
      });
    }
    const hits = doc.slots?.[state.slot]?.hits || {};
    return Object.entries(hits).map(([code, h]) => {
      const st = stocks[code] || {};
      const on = hitSlots(code);
      return {
        code, st, on, cnt: on.length, grade: h[2], mult: h[0],
        price: h[3], chg: h[4], cap: st.cap, value: h[5], turn: h[6],
      };
    });
  }

  const COLS = [
    { k: "idx", t: "#" },
    { k: "cnt", t: "포착 시각", sort: true },
    { k: "grade", t: "등급", sort: true },
    { k: "name", t: "종목 · 최근 뉴스", sort: true },
    { k: "chart", t: "3개월 일봉" },
    { k: "mult", t: "배수", sort: true, r: true },
    { k: "price", t: "현재가", sort: true, r: true },
    { k: "chg", t: "등락률", sort: true, r: true },
    { k: "cap", t: "시총(억)", sort: true, r: true },
    { k: "value", t: "거래대금(억)", sort: true, r: true },
    { k: "turn", t: "회전율", sort: true, r: true },
  ];

  function defaultSort() {
    return state.slot === "all" ? [{ k: "cnt", dir: -1 }, { k: "mult", dir: -1 }] : [{ k: "mult", dir: -1 }];
  }

  function sortRows(rows) {
    const keys = state.sort ? [state.sort, { k: "mult", dir: -1 }] : defaultSort();
    const val = (r, k) => (k === "name" ? r.st.n || "" : r[k] ?? -Infinity);
    return rows.sort((a, b) => {
      for (const { k, dir } of keys) {
        const x = val(a, k), y = val(b, k);
        const c = typeof x === "string" ? x.localeCompare(y, "ko") : x - y;
        if (c) return c * dir;
      }
      return 0;
    });
  }

  function candleSVG(k) {
    if (!k || k.length < 2) return "";
    const W = 140, H = 34, n = k.length, step = W / n, bw = Math.max(1, step * 0.62);
    let lo = Infinity, hi = -Infinity;
    for (const [, h, l] of k) { if (l > 0) lo = Math.min(lo, l); hi = Math.max(hi, h); }
    const y = (v) => (hi === lo ? H / 2 : 1 + (H - 2) * (1 - (v - lo) / (hi - lo)));
    const g = k.map(([o, h, l, c], i) => {
      const x = i * step + step / 2, col = c >= o ? "var(--up)" : "var(--down)";
      const top = y(Math.max(o, c)), bot = y(Math.min(o, c));
      return `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${y(h).toFixed(1)}" y2="${y(l).toFixed(1)}" stroke="${col}" stroke-width="0.8"/>` +
        `<rect x="${(x - bw / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.8, bot - top).toFixed(1)}" fill="${col}"/>`;
    }).join("");
    return `<svg class="candle" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="최근 3개월 일봉">${g}</svg>`;
  }

  function renderTable(doc) {
    let rows = buildRows(doc);
    if (state.mkt) rows = rows.filter((r) => r.st.m === state.mkt);
    sortRows(rows);

    $("thead").innerHTML = COLS.map((c) => {
      const s = state.sort && state.sort.k === c.k ? (state.sort.dir > 0 ? "asc" : "desc") : "";
      return `<th data-k="${c.k}" class="${c.sort ? "sort" : ""} ${c.r ? "r" : ""} ${s}">${c.t}</th>`;
    }).join("");

    const all4 = rows.filter((r) => r.cnt === SLOTS.length).length;
    $("summary").innerHTML = `${LABEL[state.slot]} 포착 <b>${rows.length}</b>종목` +
      (state.slot === "all" ? ` · 네 시각 모두 <b>${all4}</b>` : "") +
      (state.slot !== "all" && doc.slots?.[state.slot]?.t ? ` · 수집 ${esc(doc.slots[state.slot].t.slice(11))}` : "");
    $("note").hidden = !doc.note;
    $("note").textContent = doc.note || "";

    $("empty").hidden = rows.length > 0;
    $("empty").textContent = "이 조건에 잡힌 종목이 없다.";
    $("tbody").innerHTML = rows.map((r, i) => {
      const st = r.st, nw = st.news;
      const dots = SLOTS.map((s) => `<i class="${r.on.includes(s) ? "" : "off"}"></i>`).join("");
      const news = nw ? `<a class="news" href="${esc(nw[2])}" target="_blank" rel="noopener" title="${esc(nw[0])} — ${esc(nw[1])}">${esc(nw[0])}</a>` : "";
      return `<tr>
        <td class="idx">${i + 1}</td>
        <td><span class="dots" title="${r.on.map((s) => LABEL[s]).join(" · ")}">${dots}</span></td>
        <td><span class="stars ${r.grade ? "" : "none"}">${r.grade ? "★".repeat(r.grade) : "–"}</span></td>
        <td class="name"><a class="nm" href="https://finance.naver.com/item/main.naver?code=${r.code}" target="_blank" rel="noopener">${esc(st.n)}</a><span class="cd">${r.code}</span><span class="mk">${st.m === "K" ? "코스피" : "코스닥"}</span>${news}</td>
        <td>${candleSVG(st.k)}</td>
        <td class="r mult">${fmt(r.mult, 1)}배</td>
        <td class="r">${fmt(r.price)}</td>
        <td class="r ${cls(r.chg)}">${r.chg > 0 ? "+" : ""}${fmt(r.chg, 2)}%</td>
        <td class="r">${fmt(r.cap)}</td>
        <td class="r">${fmt(r.value, 1)}</td>
        <td class="r">${fmt(r.turn, 1)}%<span class="basis">시총</span></td>
      </tr>`;
    }).join("");
  }

  // ── 투신 수급 ─────────────────────────────────────────────────────────
  const FTABS = { t: "오늘 많이 산", k: "연속 순매수" };

  function renderFlowRules(c) {
    const eok = (w) => fmt(w / 1e8);
    $("flow-rules").innerHTML = `
      <p>${universe(c.max_mcap)}만 본다. 투신 순매수는 KRX 투자자별
        순매수(기관 중 투자신탁)의 장 마감 뒤 확정치다.</p>
      <p><b>오늘 많이 산</b> — 기준일 투신 순매수가 시가총액의 <b>${c.min_pct}%</b> 이상.</p>
      <p><b>연속 순매수</b> — 기준일까지 <b>${c.streak}일</b> 이상 연속 순매수, 또는 최근 <b>${c.days}거래일</b> 중
        <b>${c.buy_days}일</b> 이상 순매수(그 기간 누적도 순매수).</p>
      <p>막대는 최근 ${c.days}거래일 투신 순매수 — 위로 빨강은 순매수, 아래로 파랑은 순매도.
        시총 대비는 <span class="pill p1">${c.box_pct ?? 0.3}%</span> <span class="pill p2">${PILL[0]}%</span>
        <span class="pill p3">${PILL[1]}%</span> 이상으로 나눠 진하게.</p>`;
  }

  // 투신·기관 탭 대상 — 시장별 시총 상한(null이면 전부)
  function universe(m) {
    const one = (k, t) => m?.[k] ? `${t} 시총 <b>${fmt(m[k] / 1e12)}조</b> 미만` : `${t} <b>전 종목</b>`;
    return m && typeof m === "object" ? `${one("Q", "코스닥")} · ${one("K", "코스피")}` : "대상 종목";
  }

  function flowBars(s) {
    if (!s || !s.length) return "";
    const W = 90, H = 26, n = s.length, step = W / n, bw = Math.max(2, step * 0.66);
    const m = Math.max(...s.map(Math.abs)) || 1, mid = H / 2;
    const g = s.map((v, i) => {
      const h = Math.max(v ? 1 : 0, Math.abs(v) / m * (mid - 1)), x = i * step + (step - bw) / 2;
      const col = v > 0 ? "var(--up)" : "var(--down)";
      return `<rect x="${x.toFixed(1)}" y="${(v > 0 ? mid - h : mid).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" fill="${col}"/>`;
    }).join("");
    return `<svg class="flowbars" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="최근 투신 순매수">` +
      `<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="var(--line)" stroke-width="1"/>${g}</svg>`;
  }

  const FCOLS = [
    { k: "idx", t: "#" },
    { k: "name", t: "종목", sort: true },
    { k: "bars", t: "투신 순매수 추이" },
    { k: "chart", t: "3개월 일봉" },
    { k: "net", t: "순매수(억)", sort: true, r: true },
    { k: "pct", t: "시총 대비", sort: true, r: true },
    { k: "bd", t: "매수일", sort: true, r: true },
    { k: "st", t: "연속", sort: true, r: true },
    { k: "sum", t: "누적(억)", sort: true, r: true },
    { k: "p", t: "종가", sort: true, r: true },
    { k: "c", t: "등락률", sort: true, r: true },
    { k: "cap", t: "시총(억)", sort: true, r: true },
  ];

  function renderFlowDays() {
    $("fdays").innerHTML = state.fidx.days.map((x) => {
      const wd = WD[new Date(x.d + "T12:00:00Z").getUTCDay()];
      return `<button data-d="${x.d}" class="${x.d === state.fday ? "on" : ""}">
        <span class="d">${x.d.slice(5)} <span class="w">${wd}</span></span>
        <span class="n">${x[state.ftab] ?? 0}</span></button>`;
    }).join("");
    const on = $("fdays").querySelector(".on");
    if (on) on.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  // 시총 대비 단계 — box_pct(설정) 이상 p1, PILL[0] p2, PILL[1] p3
  const PILL = [0.5, 1];
  function pill(p, box) {
    p = Math.round(p * 100) / 100;          // 보이는 숫자(소수 둘째)로 단계를 정한다 — 0.4996이 0.50%인데 연하면 어색
    const t = p >= PILL[1] ? 3 : p >= PILL[0] ? 2 : p >= box ? 1 : 0;
    return t ? `<span class="pill p${t}">${fmt(p, 2)}%</span>` : `${fmt(p, 2)}%`;
  }

  function renderFlowTabs() {
    const st = Object.values(state.flow.stocks);
    $("ftabs").innerHTML = Object.entries(FTABS).map(([k, t]) =>
      `<button data-f="${k}" class="${k === state.ftab ? "on" : ""}">${t}<span class="n">${st.filter((x) => x[k]).length}</span></button>`).join("");
  }

  function renderFlow() {
    const f = state.flow, nd = f.days.length;
    let rows = Object.entries(f.stocks).filter(([, x]) => x[state.ftab]).map(([code, x]) => ({ code, ...x }));
    if (state.mkt) rows = rows.filter((r) => r.m === state.mkt);
    // 두 목록 모두 기본은 시총 대비 순매수 큰 순
    const keys = state.sort ? [state.sort, { k: "pct", dir: -1 }] : [{ k: "pct", dir: -1 }];
    const boxPct = f.criteria.box_pct ?? 0.3;
    rows.sort((a, b) => {
      for (const { k, dir } of keys) {
        const x = k === "name" ? a.n : a[k], y = k === "name" ? b.n : b[k];
        const c = typeof x === "string" ? x.localeCompare(y, "ko") : x - y;
        if (c) return c * dir;
      }
      return 0;
    });

    $("thead").innerHTML = FCOLS.map((c) => {
      const s = state.sort && state.sort.k === c.k ? (state.sort.dir > 0 ? "asc" : "desc") : "";
      return `<th data-k="${c.k}" class="${c.sort ? "sort" : ""} ${c.r ? "r" : ""} ${s}">${c.t}</th>`;
    }).join("");
    const wd = WD[new Date(f.d + "T12:00:00Z").getUTCDay()];
    $("summary").innerHTML = `${FTABS[state.ftab]} <b>${rows.length}</b>종목 · 기준일 ${f.d.slice(5)} (${wd}) 장 마감 뒤 확정치`;
    $("note").hidden = nd >= f.criteria.days;
    $("note").textContent = `아직 ${nd}거래일치만 모였다 — 매수일·연속일은 ${nd}일 안에서 센 값이다.`;
    $("empty").hidden = rows.length > 0;
    $("empty").textContent = "이 조건에 해당하는 종목이 없다.";
    $("tbody").innerHTML = rows.map((r, i) => `<tr>
        <td class="idx">${i + 1}</td>
        <td class="name"><a class="nm" href="https://finance.naver.com/item/main.naver?code=${r.code}" target="_blank" rel="noopener">${esc(r.n)}</a><span class="cd">${r.code}</span><span class="mk">${r.m === "K" ? "코스피" : "코스닥"}</span></td>
        <td title="${f.days.map((d, j) => `${d.slice(5)} ${fmt(r.s[j], 1)}억`).join("\n")}">${flowBars(r.s)}</td>
        <td>${candleSVG(r.ohlc)}</td>
        <td class="r ${cls(r.net)} strong">${r.net > 0 ? "+" : ""}${fmt(r.net, 1)}</td>
        <td class="r ${r.pct >= boxPct ? "" : cls(r.pct)}">${pill(r.pct, boxPct)}</td>
        <td class="r">${r.bd}<span class="sub">/${nd}</span></td>
        <td class="r ${r.st ? "strong" : ""}">${r.st ? r.st + "일" : "–"}</td>
        <td class="r ${cls(r.sum)}">${r.sum > 0 ? "+" : ""}${fmt(r.sum, 1)}</td>
        <td class="r">${fmt(r.p)}</td>
        <td class="r ${cls(r.c)}">${r.c > 0 ? "+" : ""}${fmt(r.c, 2)}%</td>
        <td class="r">${fmt(r.cap)}</td>
      </tr>`).join("");
  }

  async function showFlow() {
    if (!state.fidx) {
      $("tbody").innerHTML = "";
      $("summary").textContent = "불러오는 중…";
      try {
        state.fidx = await getJSON(`data/flow/index.json?t=${Date.now()}`);
      } catch (e) { state.fidx = { days: [] }; }
      if (state.view === "flow" && state.fidx.updated) $("updated").textContent = `갱신 ${state.fidx.updated}`;
    }
    if (!state.fidx.days.length) {
      $("thead").innerHTML = ""; $("tbody").innerHTML = ""; $("summary").textContent = ""; $("note").hidden = true;
      $("empty").hidden = false; $("empty").textContent = "투신 수급 데이터가 아직 없다.";
      return;
    }
    if (!state.fidx.days.some((x) => x.d === state.fday)) state.fday = state.fidx.days[0].d;
    renderFlowDays();
    let doc = state.fdocs[state.fday];
    if (!doc) {
      $("tbody").innerHTML = "";
      $("summary").textContent = "불러오는 중…";
      doc = state.fdocs[state.fday] = await getJSON(`data/flow/${state.fday}.json?v=${encodeURIComponent(state.fidx.updated)}`);
    }
    state.flow = doc;
    renderFlowRules(doc.criteria);
    renderFlowTabs();
    renderFlow();
    history.replaceState(null, "", `#flow/${state.ftab}/${state.fday}`);
  }

  // ── 기관 수급 ─────────────────────────────────────────────────────────
  const ITABS = { pow: "매수강도", s: "3기관", t: "투신", p: "사모", y: "연기금" };
  const MKT = { K: "코스피", Q: "코스닥" };
  const signed = (v, d = 1) => `${v > 0 ? "+" : ""}${fmt(v, d)}`;

  function renderInstRules(c) {
    const eok = (w) => fmt(w / 1e8);
    $("inst-rules").innerHTML = `
      <p>${universe(c.max_mcap)}만 본다. 3기관 = 투신 + 사모 + 연기금. KRX 투자자별 순매수의 장 마감 뒤 확정치다.</p>
      <p><b>매수강도</b> = 그날 순매수 ÷ 시가총액(%). 순매수 <b>${eok(c.pow_min_net)}억</b>·시총 <b>${eok(c.pow_min_mcap)}억</b>
        이상에서 상위 ${c.top}. <span class="hl-mint">민트</span>는 투신·사모·연기금 상위 ${c.top} 중 두 곳 이상에 든 종목,
        굵게는 <b>${c.hl_pct}%</b> 이상.</p>
      <p><b>3기관·투신·사모·연기금</b> — 그날 순매수 금액 큰 순 ${c.top}. 괄호는 시총 대비 %.
        연속 순매수는 기준일까지 며칠 연달아 순매수였는지(최근 ${c.streak_days}거래일)와 그 기간 누적.</p>
      <p><span class="hl-yel">노랑</span> = 순매수가 시총의 ${c.hl_pct}% 이상(순매수 칸)${c.cap_hl.Q ? ` · 코스닥 시총 ${fmt(c.cap_hl.Q / 1e12)}조 미만(시총 칸)` : ""},
        <span class="hl-pur">보라</span> = 투신 2일 이상 연속 순매수.</p>`;
  }

  function renderInstDays() {
    $("idays").innerHTML = state.iidx.days.map((d) => {
      const wd = WD[new Date(d + "T12:00:00Z").getUTCDay()];
      return `<button data-d="${d}" class="${d === state.iday ? "on" : ""}">
        <span class="d">${d.slice(5)} <span class="w">${wd}</span></span></button>`;
    }).join("");
    const on = $("idays").querySelector(".on");
    if (on) on.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  function renderInstTabs() {
    $("itabs").innerHTML = Object.entries(ITABS).map(([k, t]) =>
      `<button data-i="${k}" class="${k === state.itab ? "on" : ""}">${t}</button>`).join("");
    $("imkt").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.m === state.imkt));
  }

  const nameCell = (code, r) => `<a class="nm" href="https://finance.naver.com/item/main.naver?code=${code}" target="_blank" rel="noopener">${esc(r.n)}</a>`;
  const chgCell = (c) => `<td class="r ${cls(c)}">${signed(c)}%</td>`;

  function renderInst() {
    const f = state.inst, m = f.mk[state.imkt], c = f.criteria, wd = WD[new Date(f.d + "T12:00:00Z").getUTCDay()];
    const pow = state.itab === "pow";
    $("igrid").hidden = !pow; $("twrap").hidden = pow;
    $("summary").innerHTML = `${MKT[state.imkt]} ${ITABS[state.itab]} 상위 <b>${c.top}</b> · 기준일 ${f.d.slice(5)} (${wd}) 장 마감 뒤 확정치`;
    $("note").hidden = f.win >= c.streak_days;
    $("note").textContent = `연속 순매수는 최근 ${f.win}거래일 안에서 센 값이다(원자료가 아직 ${c.streak_days}일치 모이지 않았다).`;
    $("empty").hidden = true;
    if (pow) {
      const hot = {};
      for (const k of ["t", "p", "y"]) for (const code of m.pow[k]) hot[code] = (hot[code] || 0) + 1;
      $("igrid").innerHTML = ["s", "t", "p", "y"].map((k) => `<section class="icard">
          <h3>${k === "s" ? "3기관 합" : ITABS[k]} 상위 ${c.top}</h3>
          <table><thead><tr><th>#</th><th>종목</th><th class="r">매수강도</th><th class="r">등락률</th></tr></thead><tbody>
          ${m.pow[k].map((code, i) => {
            const r = m.stocks[code], mint = hot[code] >= 2 ? "hl-mint" : "";
            return `<tr><td class="idx">${i + 1}</td><td class="${mint}">${nameCell(code, r)}</td>
              <td class="r ${mint} ${r[k][1] >= c.hl_pct ? "strong" : ""}">${fmt(r[k][1], 2)}</td>${chgCell(r.c)}</tr>`;
          }).join("") || `<tr><td colspan="4" class="sub">없음</td></tr>`}
          </tbody></table></section>`).join("");
      return;
    }
    const k = state.itab, others = ["t", "p", "y"].filter((x) => x !== k);
    $("thead").innerHTML = [["#", ""], ["종목", ""], ["시총", "r"], ["등락률", "r"],
      [`${k === "s" ? "3기관 합산" : ITABS[k]} 순매수 (시총 대비)`, "r key"], ["연속 순매수", "r key"],
      ...others.map((o) => [ITABS[o], "r"])].map(([t, x], i) => `<th class="${x}" ${i === 1 ? 'data-k="name"' : ""}>${t}</th>`).join("");
    const capHl = c.cap_hl[state.imkt];
    const streak = (st, sum) => st >= 2 ? `${st}일(${signed(sum, 0)}억)` : `${st}일`;
    $("tbody").innerHTML = m.top[k].map((code, i) => {
      const r = m.stocks[code], [net, pct, st, sum] = r[k];
      const ostr = others.map((o) => {
        const [n, , s2, sm] = r[o], pur = o === "t" && s2 >= 2;
        return `<td class="r ${cls(n)} ${pur ? "hl-pur strong" : ""}">${signed(n)}${pur ? ` (${streak(s2, sm)})` : ""}</td>`;
      }).join("");
      return `<tr>
        <td class="idx">${i + 1}</td>
        <td class="name">${nameCell(code, r)}</td>
        <td class="r ${capHl && r.cap < capHl / 1e8 ? "hl-yel strong" : ""}">${fmt(r.cap)}억</td>
        ${chgCell(r.c)}
        <td class="r strong ${pct >= c.hl_pct ? "hl-yel" : "up tint"}">${signed(net)}억 (${signed(pct, 2)}%)</td>
        <td class="r ${k === "t" && st >= 2 ? "hl-pur" : ""} ${st >= 3 ? "up strong" : st === 2 ? "strong" : ""}">${streak(st, sum)}</td>
        ${ostr}</tr>`;
    }).join("");
    $("empty").hidden = m.top[k].length > 0;
    $("empty").textContent = "순매수 종목이 없다.";
  }

  async function showInst() {
    if (!state.iidx) {
      $("tbody").innerHTML = "";
      $("summary").textContent = "불러오는 중…";
      try {
        state.iidx = await getJSON(`data/inst/index.json?t=${Date.now()}`);
      } catch (e) { state.iidx = { days: [] }; }
      if (state.view === "inst" && state.iidx.updated) $("updated").textContent = `갱신 ${state.iidx.updated}`;
    }
    if (!state.iidx.days.length) {
      $("igrid").hidden = true; $("twrap").hidden = false;
      $("thead").innerHTML = ""; $("tbody").innerHTML = ""; $("summary").textContent = ""; $("note").hidden = true;
      $("empty").hidden = false; $("empty").textContent = "기관 수급 데이터를 모으는 중이다 — 처음엔 하루쯤 걸린다.";
      return;
    }
    if (!state.iidx.days.includes(state.iday)) state.iday = state.iidx.days[0];
    renderInstDays();
    let doc = state.idocs[state.iday];
    if (!doc) {
      $("summary").textContent = "불러오는 중…";
      doc = state.idocs[state.iday] = await getJSON(`data/inst/${state.iday}.json?v=${encodeURIComponent(state.iidx.updated)}`);
    }
    state.inst = doc;
    renderInstRules(doc.criteria);
    renderInstTabs();
    renderInst();
    history.replaceState(null, "", `#inst/${state.itab}/${state.imkt}/${state.iday}`);
  }

  function render() {
    if (state.view === "flow") renderFlow();
    else if (state.view === "inst") renderInst();
    else renderTable(state.docs[state.day]);
  }

  function setView(v) {
    state.view = v; state.sort = null;
    $("views").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.v === v));
    $("v-surge").hidden = v !== "surge";
    $("v-flow").hidden = v !== "flow";
    $("v-inst").hidden = v !== "inst";
    $("mkt").hidden = v === "inst"; $("imkt").hidden = v !== "inst";
    if (v !== "inst") { $("igrid").hidden = true; $("twrap").hidden = false; }
    const src = { flow: state.fidx, inst: state.iidx }[v] ?? state.idx;
    $("updated").textContent = src ? `갱신 ${src.updated}` : "";
    if (v === "inst") return showInst().catch((e) => { $("summary").textContent = `불러오기 실패: ${e.message}`; });
    if (v === "flow") return showFlow().catch((e) => { $("summary").textContent = `불러오기 실패: ${e.message}`; });
    if (!state.idx || !state.day) {
      $("thead").innerHTML = ""; $("tbody").innerHTML = ""; $("summary").textContent = ""; $("note").hidden = true;
      $("empty").hidden = false; $("empty").textContent = "아직 수집된 데이터가 없다.";
      return;
    }
    show().catch((e) => { $("summary").textContent = `불러오기 실패: ${e.message}`; });
  }

  // ── 흐름 ──────────────────────────────────────────────────────────────
  async function show() {
    renderDays();
    let doc = state.docs[state.day];
    if (!doc) {
      $("tbody").innerHTML = "";
      $("summary").textContent = "불러오는 중…";
      doc = state.docs[state.day] = await getJSON(`data/days/${state.day}.json?v=${encodeURIComponent(state.idx.updated)}`);
    }
    if (state.slot !== "all" && !doc.slots?.[state.slot]) state.slot = "all";
    renderSlots(doc);
    renderTable(doc);
    history.replaceState(null, "", `#${state.day}/${state.slot}`);
  }

  function bind() {
    $("views").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b || b.dataset.v === state.view) return;
      setView(b.dataset.v);
    });
    $("ftabs").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.ftab = b.dataset.f; state.sort = null; showFlow();
    });
    $("fdays").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.fday = b.dataset.d; state.sort = null; showFlow();
    });
    $("itabs").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.itab = b.dataset.i; showInst();
    });
    $("idays").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.iday = b.dataset.d; showInst();
    });
    $("imkt").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.imkt = b.dataset.m; showInst();
    });
    $("days").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.day = b.dataset.d; state.sort = null; show();
    });
    $("slots").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b || b.disabled) return;
      state.slot = b.dataset.s; state.sort = null; show();
    });
    $("mkt").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      state.mkt = b.dataset.m;
      $("mkt").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      render();
    });
    $("thead").addEventListener("click", (e) => {
      const th = e.target.closest("th.sort"); if (!th) return;
      const k = th.dataset.k;
      const cur = state.sort && state.sort.k === k ? state.sort.dir : 0;
      // 첫 클릭은 큰 값부터(이름만 가나다순), 다시 누르면 뒤집는다.
      state.sort = { k, dir: cur ? -cur : (k === "name" ? 1 : -1) };
      render();
    });
  }

  async function init() {
    bind();
    const [d, s, x, y] = decodeURIComponent(location.hash.slice(1)).split("/");
    try {
      state.idx = await getJSON(`data/index.json?t=${Date.now()}`);
      renderRules(state.idx.criteria);
      state.day = state.idx.days.some((x) => x.d === d) ? d : state.idx.days[0]?.d;
      state.slot = LABEL[s] ? s : "all";
    } catch (e) { /* 급증 데이터가 없어도 투신 탭은 볼 수 있게 */ }
    if (d === "flow") { state.ftab = FTABS[s] ? s : "t"; state.fday = x || null; }
    if (d === "inst") { state.itab = ITABS[s] ? s : "pow"; state.imkt = MKT[x] ? x : "Q"; state.iday = y || null; }
    setView(d === "flow" || d === "inst" ? d : "surge");
  }

  // 주소의 #일자/시각(또는 #flow/목록/일자, #inst/표/시장/일자)만 바꿔 들어와도(뒤로 가기·링크) 그 화면으로
  window.addEventListener("hashchange", () => {
    const [d, s, x, y] = decodeURIComponent(location.hash.slice(1)).split("/");
    if (d === "inst") {
      const t = ITABS[s] ? s : "pow", mk = MKT[x] ? x : "Q", day = y || state.iday;
      if (state.view === "inst" && t === state.itab && mk === state.imkt && day === state.iday) return;
      Object.assign(state, { itab: t, imkt: mk, iday: day });
      return setView("inst");
    }
    if (d === "flow") {
      const t = FTABS[s] ? s : "t", day = x || state.fday;
      if (state.view === "flow" && t === state.ftab && day === state.fday) return;
      state.ftab = t; state.fday = day;
      return setView("flow");
    }
    if (!state.idx) return;
    if (state.view === "surge" && d === state.day && s === state.slot) return;
    if (state.idx.days.some((x) => x.d === d)) state.day = d;
    state.slot = LABEL[s] ? s : "all";
    setView("surge");
  });

  init();
})();
