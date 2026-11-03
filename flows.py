"""
투신 수급 수집 — KRX 확정치를 받아 data/flow에 쌓고 docs/data/flow.json을 만든다.

  python flows.py

워크플로우가 매 실행마다 부른다(평일 18:35 schedule + cron-job.org 장중 호출). 할 일이 없으면
로그인도 하지 않고 끝난다. 기준일은 18:00 이후면 오늘, 그 전이면 직전 개장일 — 장중 호출은
어제 것을 놓쳤을 때 메우는 용도다. 받을 땐 최근 FLOW_DAYS(+여유) 거래일 중 빠진 날을 모두 채운다.
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


def main():
    now = store.now_kst()
    latest = target_day(now)
    want = [d.isoformat() for d in krxcal.open_days_before(latest, C.FLOW_DAYS + 2)] + [latest.isoformat()]
    missing = [d for d in want if d not in store.flow_days()]
    cur = store.load_flow()
    if not missing and cur.get("d") == latest.isoformat() and cur.get("ver") == flow.VERSION:
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

    days = [d for d in store.flow_days() if d <= latest.isoformat()
            and "v" in (store.load_flow_day(d) or {})][-C.FLOW_DAYS:]
    if not days:
        print("::error title=투신 수급::받은 날이 없다")
        return 1
    rows = krx.listing(days[-1].replace("-", ""))
    if len(rows) < 1500:
        print(f"::error title=투신 수급::{days[-1]} 시세가 {len(rows)}종목뿐")
        return 1
    out = flow.build(days, rows, now.strftime("%Y-%m-%d %H:%M"))
    store.save_flow(out)
    for d in store.flow_days()[:-C.FLOW_KEEP_DAYS]:
        os.remove(os.path.join(store.FLOW_DIR, f"{d}.json"))
    t = sum(s["t"] for s in out["stocks"].values())
    k = sum(s["k"] for s in out["stocks"].values())
    print(f"::notice title=투신 수급::{days[-1]} 기준 · 많이 산 {t} · 연속 {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
