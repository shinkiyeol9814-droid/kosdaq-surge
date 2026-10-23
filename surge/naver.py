"""
네이버 금융 공개 엔드포인트 — 시장 전체 스냅샷, 분봉(백필용), 일봉, 뉴스.

시장 전체 스냅샷은 시가총액순 목록(페이지당 100종목)을 끝까지 넘기며 받는다.
코스피 약 25페이지 + 코스닥 약 19페이지, 페이지당 0.15초 안팎이라 몇 초면 끝난다.
"""
import html
import time
from concurrent.futures import ThreadPoolExecutor

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_S = requests.Session()
_S.headers.update(H)


def _get(url, timeout=10, tries=3):
    last = None
    for i in range(tries):
        try:
            r = _S.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:      # 일시적 끊김은 잠깐 쉬고 다시
            last = e
        time.sleep(0.5 * (i + 1))
    raise last


def _num(s, default=0.0):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _one_pass(market: str) -> dict:
    first = _get(f"https://m.stock.naver.com/api/stocks/marketValue/{market}?page=1&pageSize=100")
    total = int(first.get("totalCount") or 0)
    pages = list(range(2, (total + 99) // 100 + 1))
    with ThreadPoolExecutor(max_workers=6) as ex:
        rest = list(ex.map(lambda p: _get(
            f"https://m.stock.naver.com/api/stocks/marketValue/{market}?page={p}&pageSize=100"), pages))
    out = {}
    for page in [first] + rest:
        for s in page.get("stocks", []):
            if s.get("stockEndType") != "stock":
                continue
            out[s["itemCode"]] = [
                s.get("stockName", ""),
                _num(s.get("closePriceRaw")),
                _num(s.get("fluctuationsRatio")),
                _num(s.get("accumulatedTradingValueRaw")),
                _num(s.get("marketValueRaw")),
            ]
    return out


def market_snapshot(market: str) -> dict:
    """
    {코드: [이름, 현재가, 등락률%, 누적거래대금(원), 시가총액(원)]} — 보통주만.
    코스피 목록엔 ETF·ETN이 섞여 있어(stockEndType) 걸러낸다. 우선주는 남긴다.

    시총순 페이지를 따로 받는 사이 순위가 바뀌면 경계의 종목이 빠지거나 겹친다(장 마감 뒤에도
    두 번 받으면 한두 종목씩 달랐다 — pageSize는 100이 상한). 두 번 받아 합친다.
    """
    a = _one_pass(market)
    b = _one_pass(market)
    a.update(b)
    return a


def daily_candles(code: str, start: str, end: str) -> list:
    """[[YYYYMMDD, 시가, 고가, 저가, 종가], ...] — start/end는 YYYYMMDD."""
    rows = _get(f"https://api.stock.naver.com/chart/domestic/item/{code}/day"
                f"?startDateTime={start}0000&endDateTime={end}2359")
    return [[r["localDate"], r["openPrice"], r["highPrice"], r["lowPrice"], r["closePrice"]]
            for r in rows if r.get("closePrice")]


def minute5_bars(code: str, start: str, end: str) -> list:
    """
    5분봉 [[YYYYMMDDHHMM, 대표가격, 거래량, 종가], ...]. 네이버는 최근 약 7거래일만 준다.
    필드 이름은 accumulatedTradingVolume이지만 실제로는 그 봉 하나의 거래량이다(1분봉 합 = 10분봉 값으로
    확인). 시각은 봉의 시작 — "1000" 봉은 10:00~10:05. 대표가격은 (고+저+종)/3.
    """
    rows = _get(f"https://api.stock.naver.com/chart/domestic/item/{code}/minute5"
                f"?startDateTime={start}0900&endDateTime={end}1530", timeout=20)
    out = []
    for r in rows:
        h, l, c = r.get("highPrice") or 0, r.get("lowPrice") or 0, r.get("currentPrice") or 0
        if c:
            out.append([r["localDateTime"][:12], (h + l + c) / 3 if h and l else c,
                        r.get("accumulatedTradingVolume") or 0, c])
    return out


def latest_news(code: str):
    """가장 최근 뉴스 (제목, 언론사, 링크, YYYYMMDDHHMM) 또는 None."""
    try:
        groups = _get(f"https://m.stock.naver.com/api/news/stock/{code}?pageSize=1&page=1", tries=2)
        for g in groups or []:
            for it in g.get("items", []):
                url = f"https://n.news.naver.com/mnews/article/{it['officeId']}/{it['articleId']}"
                # 제목은 이미 HTML 이스케이프돼 온다(&quot; 등) — 화면이 다시 이스케이프하므로 풀어 둔다.
                return [html.unescape(it.get("title", "")), it.get("officeName", ""), url, it.get("datetime", "")]
    except Exception:
        pass
    return None
