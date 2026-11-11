"""
종합 수급 — 투신·사모·연기금과 그 합(3기관)의 순매수 표를 시장(코스피·코스닥)별로 만든다.
대상은 투신 탭과 같다(코스닥 전부, 코스피 3조 미만 — config.FLOW_MAX_MCAP).

  순매수 상위   종류마다 그날 순매수 금액 큰 순 INST_TOP 종목
  매수강도 상위 종류마다 순매수 ÷ 시총(%) 큰 순 INST_TOP 종목 — 순매수 1억·시총 500억 이상만

연속 순매수는 기준일까지 며칠 연달아 순매수였는지(최대 INST_STREAK_DAYS일)와 그 기간 누적이다.

docs/data/inst/{기준일}.json — 하루 하나, INST_SHOW_DAYS 보관. 목록은 docs/data/inst/index.json
  d 기준일, win 연속일을 센 거래일 수(처음 채운 날들은 60보다 짧다), criteria
  mk.{K|Q}.top.{s|t|p|y}   순매수 상위 종목코드, 순서대로
  mk.{K|Q}.pow.{s|t|p|y}   매수강도 상위 종목코드, 순서대로
  mk.{K|Q}.stocks.{코드} = {n 이름, c 등락률, cap 시총(억),
                            s|t|p|y [순매수(억), 시총 대비(%), 연속일, 연속 기간 누적(억)]}
  ver 이 구조의 판 — index.json의 ver가 VERSION과 다르면 flows.py가 모든 일자를 다시 만든다
"""
from surge import config as C
from surge import store
from surge.flow import in_universe

VERSION = 2                      # 2: 코스피도 시총 1조 미만 노란 칸
KINDS = [k for k, _ in C.INST_KINDS]


def build(days: list, listing: dict, updated: str) -> dict:
    """days: 오래된 순 거래일(휴장 제외), 마지막이 기준일. listing은 krx.listing 결과."""
    raw = [store.load_inst_day(d) or {} for d in days]
    out = {}
    for mkt in ("K", "Q"):
        rows = {}
        for code, (name, m, _price, chg, cap) in listing.items():
            if m != mkt or not in_universe(m, cap):
                continue
            per = {k: [r.get(k, {}).get(code, 0) / 100 for r in raw] for k in KINDS}   # 백만원 → 억
            per["s"] = [sum(x) for x in zip(*per.values())]
            f = {}
            for k, s in per.items():
                st, tot = 0, 0.0
                for x in reversed(s):
                    if x <= 0:
                        break
                    st += 1
                    tot += x
                net = s[-1]
                f[k] = [round(net, 1), round(net * 1e8 / cap * 100, 3), st, round(tot)]
            rows[code] = {"n": name, "c": chg, "cap": round(cap / 1e8), **f}

        top, pow_ = {}, {}
        for k in ["s"] + KINDS:
            buy = [c for c, r in rows.items() if r[k][0] > 0]
            top[k] = sorted(buy, key=lambda c: -rows[c][k][0])[:C.INST_TOP]
            ok = [c for c in buy if rows[c][k][0] * 1e8 >= C.INST_POWER_MIN_NET
                  and rows[c]["cap"] * 1e8 >= C.INST_POWER_MIN_MCAP]
            pow_[k] = sorted(ok, key=lambda c: -rows[c][k][1])[:C.INST_TOP]
        keep = {c for v in (*top.values(), *pow_.values()) for c in v}
        out[mkt] = {"top": top, "pow": pow_, "stocks": {c: rows[c] for c in sorted(keep)}}

    return {"ver": VERSION, "updated": updated, "d": days[-1], "win": len(days), "mk": out,
            "criteria": {"kinds": dict(C.INST_KINDS), "top": C.INST_TOP, "streak_days": C.INST_STREAK_DAYS,
                         "cap_hl": C.INST_CAP_HL, "max_mcap": C.FLOW_MAX_MCAP, "hl_pct": C.INST_HL_PCT,
                         "pow_min_net": C.INST_POWER_MIN_NET, "pow_min_mcap": C.INST_POWER_MIN_MCAP}}
