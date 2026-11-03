"""
투신 수급 — 시총 300억~1조 종목에서 두 목록을 뽑는다.

  오늘 많이 산    그날 투신 순매수 ÷ 시가총액 ≥ FLOW_MIN_PCT
  연속 순매수     연속 FLOW_STREAK일 이상, 또는 최근 FLOW_DAYS일 중 FLOW_BUY_DAYS일 이상(누적도 순매수)

docs/data/flow.json
  d 기준일, days 최근 FLOW_DAYS 거래일, criteria
  stocks.{코드} = {n 이름, m 시장, p 종가, c 등락률, cap 시총(억), net 그날 순매수(억), pct 시총 대비(%),
                   bd 매수일 수, st 연속 매수일, sum 누적 순매수(억), s 일별 순매수(억) 오래된 순,
                   t 1이면 '오늘 많이 산', k 1이면 '연속 순매수', ohlc 3개월 일봉 [[시,고,저,종]...]}
  ver 이 구조의 판 — VERSION과 다르면 flows.py가 기준일이 같아도 다시 만든다
"""
from surge import config as C
from surge import screen, store

VERSION = 2                      # flow.json 구조를 바꾸면 올린다(2: 3개월 일봉 추가)


def build(days: list, listing: dict, updated: str) -> dict:
    """days: 오래된 순 거래일(YYYY-MM-DD, 휴장 제외). 마지막 날이 기준일."""
    series = [(store.load_flow_day(d) or {}).get("v", {}) for d in days]
    stocks = {}
    for code, (name, mkt, price, chg, cap) in listing.items():
        if not (C.FLOW_MIN_MCAP <= cap <= C.FLOW_MAX_MCAP):
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
            "criteria": {"min_mcap": C.FLOW_MIN_MCAP, "max_mcap": C.FLOW_MAX_MCAP,
                         "min_pct": C.FLOW_MIN_PCT, "box_pct": C.FLOW_BOX_PCT, "days": C.FLOW_DAYS,
                         "streak": C.FLOW_STREAK, "buy_days": C.FLOW_BUY_DAYS}}
