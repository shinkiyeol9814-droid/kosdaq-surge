// 거래대금 급증 스크리너 — data/index.json과 data/days/{일자}.json을 읽어 그린다.
// 일자 파일 구조는 surge/screen.py 머리말 참고.
(() => {
  const SLOTS = ["1005", "1205", "1405", "close"];
  const LABEL = { all: "종합", "1005": "10:05", "1205": "12:05", "1405": "14:05", close: "종가" };
  const WD = "일월화수목금토";
  const $ = (id) => document.getElementById(id);

  const state = { idx: null, docs: {}, day: null, slot: "all", mkt: "", sort: null };

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
      renderTable(state.docs[state.day]);
    });
    $("thead").addEventListener("click", (e) => {
      const th = e.target.closest("th.sort"); if (!th) return;
      const k = th.dataset.k;
      const cur = state.sort && state.sort.k === k ? state.sort.dir : 0;
      // 첫 클릭은 큰 값부터(이름만 가나다순), 다시 누르면 뒤집는다.
      state.sort = { k, dir: cur ? -cur : (k === "name" ? 1 : -1) };
      renderTable(state.docs[state.day]);
    });
  }

  async function init() {
    bind();
    try {
      state.idx = await getJSON(`data/index.json?t=${Date.now()}`);
    } catch (e) {
      $("empty").hidden = false;
      $("empty").textContent = "아직 수집된 데이터가 없다.";
      return;
    }
    $("updated").textContent = `갱신 ${state.idx.updated}`;
    renderRules(state.idx.criteria);
    const [d, s] = decodeURIComponent(location.hash.slice(1)).split("/");
    state.day = state.idx.days.some((x) => x.d === d) ? d : state.idx.days[0]?.d;
    state.slot = LABEL[s] ? s : "all";
    if (!state.day) { $("empty").hidden = false; $("empty").textContent = "아직 수집된 데이터가 없다."; return; }
    show().catch((e) => { $("summary").textContent = `불러오기 실패: ${e.message}`; });
  }

  // 주소의 #일자/시각만 바꿔 들어와도(뒤로 가기·링크) 그 화면으로
  window.addEventListener("hashchange", () => {
    if (!state.idx) return;
    const [d, s] = decodeURIComponent(location.hash.slice(1)).split("/");
    if (d === state.day && s === state.slot) return;
    if (state.idx.days.some((x) => x.d === d)) state.day = d;
    state.slot = LABEL[s] ? s : "all";
    state.sort = null;
    show();
  });

  init();
})();
