"""
투신 수급 수집 — KRX 확정치를 받아 data/flow에 쌓고 일자별 결과(docs/data/flow/{일자}.json)를 만든다.

  python flows.py

워크플로우가 매 실행마다 부른다(평일 18:35 schedule + cron-job.org 장중 호출). 할 일이 없으면
로그인도 하지 않고 끝난다. 기준일은 18:00 이후면 오늘, 그 전이면 직전 개장일 — 장중 호출은
어제 것을 놓쳤을 때 메우는 용도다.

KRX는 과거 일자도 주므로 빠진 날은 언제든 채울 수 있다. 화면에 둘 FLOW_SHOW_DAYS일 + 그 앞
FLOW_DAYS일(연속일 계산용) 원자료 중 빠진 날을 받고, 결과가 없는 일자를 만든다. 결과 구조
(flow.VERSION)가 바뀌면 모든 일자를 다시 만든다.
"""
import os
import sys
import time
from datetime import timedelta

from surge import config as C
from surge import flow, krx, krxcal, store


def target_day(now):
    d = now.date()
    if krxcal.is_open(d) and now.strftime("%H%M") >= C.FLOW_FINAL_HHMM:
        return d
    p = d - timedelta(days=1)
    while not krxcal.is_open(p):
        p -= timedelta(days=1)
    return p


def _open_raw_days(upto: str) -> list:
    """upto 이하 원자료가 있는(휴장 표시 아닌) 날, 오래된 순."""
    return [d for d in store.flow_days() if d <= upto and "v" in (store.load_flow_day(d) or {})]


def main():
    now = store.now_kst()
    latest = target_day(now)
    span = C.FLOW_SHOW_DAYS + C.FLOW_DAYS + 2
    want = [d.isoformat() for d in krxcal.open_days_before(latest, span - 1)] + [latest.isoformat()]
    have = set(store.flow_days())
    missing = [d for d in want if d not in have]
    show = want[-C.FLOW_SHOW_DAYS:]
    idx = store.load_flow_index()
    fresh = idx.get("ver") == flow.VERSION
    built = set(store.flow_result_days()) if fresh else set()
    # KRX가 빈 표를 준 날(휴장 표시)은 결과가 없으니 매번 다시 하지 않는다
    todo = [d for d in show if d not in built and "x" not in (store.load_flow_day(d) or {})]
    if not missing and not todo:
        print(f"투신 수급 {latest} 이미 있음")
        return 0
    if not krx.has_login():
        print("::error title=투신 수급::KRX_ID / KRX_PW 가 없다 — Actions Secrets 확인")
        return 1

    for d in missing:
        v = krx.net_buy(d.replace("-", ""))
        store.save_flow_day(d, v, closed=not v)
        print(f"{d} 투신 {'휴장' if not v else f'{len(v)}종목'}")
        time.sleep(0.5)                                     # KRX 부하 배려

    stamp = now.strftime("%Y-%m-%d %H:%M")
    made = []
    for d in todo:
        days = _open_raw_days(d)[-C.FLOW_DAYS:]
        if not days or days[-1] != d:                       # 휴장(KRX가 빈 표)이면 결과 없음
            continue
        rows = krx.listing(d.replace("-", ""))
        time.sleep(0.5)
        if len(rows) < 1500:
            print(f"::warning title=투신 수급::{d} 시세가 {len(rows)}종목뿐 — 건너뜀")
            continue
        store.save_flow_result(d, flow.build(days, rows, stamp))
        made.append(d)

    # 보관 기간 정리 — 결과는 FLOW_SHOW_DAYS, 원자료는 FLOW_KEEP_DAYS
    results = store.flow_result_days()
    for d in results[:-C.FLOW_SHOW_DAYS]:
        os.remove(os.path.join(store.FLOW_OUT_DIR, f"{d}.json"))
    for d in store.flow_days()[:-C.FLOW_KEEP_DAYS]:
        os.remove(os.path.join(store.FLOW_DIR, f"{d}.json"))
    legacy = os.path.join(store.ROOT, "docs", "data", "flow.json")   # 일자별 파일 이전의 단일 파일
    if os.path.exists(legacy):
        os.remove(legacy)

    out = []
    for d in reversed(store.flow_result_days()):
        st = store.load_flow_result(d).get("stocks", {}).values()
        out.append({"d": d, "t": sum(s["t"] for s in st), "k": sum(s["k"] for s in st)})
    store.save_flow_index({"ver": flow.VERSION, "updated": stamp, "days": out})
    top = out[0] if out else {"d": "-", "t": 0, "k": 0}
    print(f"::notice title=투신 수급::{len(made)}일 만듦 · 최신 {top['d']} 많이 산 {top['t']} · 연속 {top['k']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
