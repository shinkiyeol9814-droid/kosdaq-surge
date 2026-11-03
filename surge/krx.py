"""
KRX 정보데이터시스템 — 투신 순매수(전 종목)와 전종목 시세. pykrx를 거친다.

2026년부터 KRX가 로그인을 요구해(비로그인 요청은 400 "LOGOUT") pykrx가 환경변수 KRX_ID / KRX_PW로
로그인한다 — Actions Secrets에만 있다. pykrx는 import만으로도 로그인 메시지를 찍으므로 필요할 때만
함수 안에서 불러온다.
"""
import os

MARKETS = (("KOSPI", "STK", "K"), ("KOSDAQ", "KSQ", "Q"))


def has_login() -> bool:
    return bool(os.environ.get("KRX_ID") and os.environ.get("KRX_PW"))


def _num(s) -> float:
    s = str(s).replace(",", "").strip()
    try:
        return float(s) if s not in ("", "-") else 0.0
    except ValueError:
        return 0.0


def net_buy(day: str) -> dict:
    """{코드: 투신 순매수거래대금(원)} — 코스피+코스닥. day 'YYYYMMDD'. 휴장일이면 빈 dict."""
    from pykrx import stock
    out = {}
    for market, _, _ in MARKETS:
        df = stock.get_market_net_purchases_of_equities_by_ticker(day, day, market, "투신")
        if df is None or df.empty:
            continue
        for code, v in df["순매수거래대금"].items():
            out[str(code)] = float(v)
    return out


def listing(day: str) -> dict:
    """{코드: [이름, 시장 K/Q, 종가, 등락률, 시가총액(원)]} — 전종목 시세 [12001]."""
    from pykrx.website.krx.market.core import 전종목시세
    out = {}
    for _, mkt_id, tag in MARKETS:
        df = 전종목시세().fetch(day, mkt_id)
        if df is None or df.empty:
            continue
        for r in df.to_dict("records"):
            out[str(r["ISU_SRT_CD"])] = [r["ISU_ABBRV"], tag, _num(r["TDD_CLSPRC"]),
                                         _num(r["FLUC_RT"]), _num(r["MKTCAP"])]
    return out
