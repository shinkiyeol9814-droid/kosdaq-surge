"""
투신 수급 — 코스닥 전 종목·코스피 시총 3조 미만(config.FLOW_MAX_MCAP)에서 두 목록을 뽑는다.

  오늘 많이 산    그날 투신 순매수 ÷ 시가총액 ≥ FLOW_MIN_PCT
  연속 순매수     연속 FLOW_STREAK일 이상, 또는 최근 FLOW_DAYS일 중 FLOW_BUY_DAYS일 이상(누적도 순매수)

docs/data/flow/{기준일}.json — 하루 하나, FLOW_SHOW_DAYS 보관. 목록은 docs/data/flow/index.json
  d 기준일, days 최근 FLOW_DAYS 거래일, criteria
  stocks.{코드} = {n 이름, m 시장, p 종가, c 등락률, cap 시총(억), net 그날 순매수(억), pct 시총 대비(%),
                   bd 매수일 수, st 연속 매수일, sum 누적 순매수(억), s 일별 순매수(억) 오래된 순,
                   t 1이면 '오늘 많이 산', k 1이면 '연속 순매수', ohlc 3개월 일봉 [[시,고,저,종]...]}
  ver 이 구조의 판 — index.json의 ver가 VERSION과 다르면 flows.py가 모든 일자를 다시 만든다
"""
from surge import config as C
from surge import screen, store

VERSION = 4                      # 일자 파일 구조를 바꾸면 올린다(2: 3개월 일봉, 3: 일자별 파일, 4: 코스닥 전부·코스피 3조 미만)


def in_universe(mkt: str, cap: float) -> bool:
    """투신·기관 탭 대상 — config.FLOW_MAX_MCAP의 시장별 상한 미만."""
    top = C.FLOW_MAX_MCAP.get(mkt)
    return cap > 0 and (top is None or cap < top)


def build(days: list, listing: dict, updated: str) -> dict:
    """days: 오래된 순 거래일(YYYY-MM-DD, 휴장 제외). 마지막 날이 기준일."""
    series = [(store.load_flow_day(d) or {}).get("v", {}) for d in days]
    stocks = {}
    for code, (name, mkt, price, chg, cap) in listing.items():
        if not in_universe(mkt, cap):
            continue
        s = [v.get(code, 0) / 100 for v in series]          # 백만원 → 억
        net = s[-1]
        pct = net * 1e8 / cap * 100
        bd = sum(1 for x in s if x > 0)
        st = 0
        for x in reversed(s):
            if x <= 0:
                break
            st += 1
        total = sum(s)
        today = net > 0 and pct >= C.FLOW_MIN_PCT
        streak = st >= C.FLOW_STREAK or (bd >= C.FLOW_BUY_DAYS and total > 0)
        if not (today or streak):
            continue
        stocks[code] = {"n": name, "m": mkt, "p": price, "c": chg, "cap": round(cap / 1e8),
                        "net": round(net, 1), "pct": round(pct, 3), "bd": bd, "st": st,
                        "sum": round(total, 1), "s": [round(x, 1) for x in s],
                        "t": int(today), "k": int(streak)}
    # 3개월 일봉은 거래대금 탭과 같은 네이버 일봉 — 실패한 종목은 비워 둔다
    for code, ex in screen._extras(list(stocks), days[-1], with_news=False).items():
        if ex.get("k"):
            stocks[code]["ohlc"] = ex["k"]
    return {"ver": VERSION, "updated": updated, "d": days[-1], "days": days, "stocks": stocks,
            "criteria": {"max_mcap": C.FLOW_MAX_MCAP,
                         "min_pct": C.FLOW_MIN_PCT, "box_pct": C.FLOW_BOX_PCT, "days": C.FLOW_DAYS,
                         "streak": C.FLOW_STREAK, "buy_days": C.FLOW_BUY_DAYS}}
