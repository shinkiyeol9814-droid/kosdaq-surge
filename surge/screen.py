"""
포착 — 한 시각(슬롯)의 시장 스냅샷을 과거 같은 시각의 누적거래대금 중앙값과 비교한다.

rows: {코드: [이름, 시장(K/Q), 현재가, 등락률%, 누적거래대금(원), 시가총액(원)]}

일자 파일(docs/data/days/YYYY-MM-DD.json):
  slots.{슬롯}.hits.{코드} = [배수, 시장 내 대금순위, 등급, 현재가, 등락률, 거래대금(억), 회전율%]
  stocks.{코드}            = 그날 한 번이라도 잡힌 종목의 마지막 시세·뉴스·3개월 일봉
화면의 '종합'은 브라우저가 slots를 합쳐 만든다.
"""
import os
import shutil
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from . import config as C
from . import naver, store


def _stars(value, tiers, higher_is_better):
    for th, s in tiers:
        if (value <= th) if not higher_is_better else (value >= th):
            return s
    return 0


def grade(rank: int, turnover_pct: float) -> int:
    return max(_stars(rank, C.SCALE_RANKS, False), _stars(turnover_pct, C.TURNOVER_PCT, True))


def baseline(day: str, slot: str) -> dict:
    """{코드: (중앙값, 비교한 날 수)} — day 이전 스냅샷 최대 BASE_DAYS일."""
    past = [d for d in store.snapshot_days() if d < day][-C.BASE_DAYS:]
    series = {}
    for d in past:
        for code, v in store.snapshot_values(d, slot).items():
            series.setdefault(code, []).append(v)
    return {c: (statistics.median(vs), len(vs)) for c, vs in series.items()}


def find_hits(day: str, slot: str, rows: dict) -> dict:
    base = baseline(day, slot)
    rank = {}
    for mkt in ("K", "Q"):
        ordered = sorted((c for c, r in rows.items() if r[1] == mkt), key=lambda c: -rows[c][4])
        rank.update({c: i + 1 for i, c in enumerate(ordered)})
    hits = {}
    for code, (name, mkt, price, chg, value, mcap) in rows.items():
        med, n = base.get(code, (0, 0))
        if n < C.MIN_BASE_DAYS or med <= 0 or mcap < C.MIN_MCAP or value < C.MIN_VALUE[slot]:
            continue
        mult = value / med
        if mult < C.MULTIPLE:
            continue
        turn = value / mcap * 100 if mcap else 0
        hits[code] = [round(mult, 1), rank[code], grade(rank[code], turn),
                      price, round(chg, 2), round(value / 1e8, 1), round(turn, 1)]
    return hits


def _extras(codes, day: str, with_news=True) -> dict:
    """종목별 3개월 일봉([[시,고,저,종]...])과 최신 뉴스. 실패한 종목은 비워 둔다."""
    end = date.fromisoformat(day)
    start = (end - timedelta(days=95)).strftime("%Y%m%d")

    def one(code):
        out = {}
        try:
            out["k"] = [[int(o), int(h), int(l), int(c)]
                        for _, o, h, l, c in naver.daily_candles(code, start, end.strftime("%Y%m%d"))]
        except Exception:
            pass
        if with_news:
            out["news"] = naver.latest_news(code)
        return code, out

    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(ex.map(one, codes))


def update_day(day: str, slot: str, taken_at: str, rows: dict, hits: dict, with_news=True, note=None) -> dict:
    doc = store.load_day(day) or {"date": day, "slots": {}, "stocks": {}}
    doc["slots"][slot] = {"t": taken_at, "hits": hits}
    if note:
        doc["note"] = note
    codes = sorted({c for s in doc["slots"].values() for c in s["hits"]})
    extras = _extras(codes, day, with_news)
    stocks = {}
    for code in codes:
        old = doc["stocks"].get(code, {})
        r = rows.get(code)
        st = dict(old)
        if r:   # 이번 스냅샷의 시세로 갱신(이번 시각엔 안 잡혔어도 '현재가'는 최신으로)
            st.update({"n": r[0], "m": r[1], "p": r[2], "c": round(r[3], 2),
                       "v": round(r[4] / 1e8, 1), "cap": round(r[5] / 1e8),
                       "turn": round(r[4] / r[5] * 100, 1) if r[5] else 0})
        ex = extras.get(code, {})
        if ex.get("k"):
            st["k"] = ex["k"]
        if ex.get("news") or "news" not in st:
            st["news"] = ex.get("news")
        stocks[code] = st
    doc["stocks"] = stocks
    doc["updated"] = taken_at if " " in taken_at else f"{day} {taken_at}"
    store.save_day(day, doc)
    return doc


def rebuild_index():
    days = sorted((f[:-5] for f in os.listdir(store.DAYS_DIR) if f.endswith(".json")), reverse=True)
    for old in days[C.KEEP_DAYS:]:
        os.remove(os.path.join(store.DAYS_DIR, f"{old}.json"))
    out = []
    for d in days[:C.KEEP_DAYS]:
        doc = store.load_day(d)
        n = {s: len(v["hits"]) for s, v in doc.get("slots", {}).items()}
        n["all"] = len({c for v in doc.get("slots", {}).values() for c in v["hits"]})
        out.append({"d": d, "n": n})
    store.save_index({"updated": store.now_kst().strftime("%Y-%m-%d %H:%M"), "days": out,
                      "criteria": {"min_mcap": C.MIN_MCAP, "base_days": C.BASE_DAYS,
                                   "multiple": C.MULTIPLE, "min_value": C.MIN_VALUE,
                                   "scale": C.SCALE_RANKS, "turnover": C.TURNOVER_PCT}})


def prune_snapshots():
    days = store.snapshot_days()
    for old in days[:-C.SNAP_KEEP_DAYS]:
        shutil.rmtree(os.path.join(store.SNAP_DIR, old), ignore_errors=True)
