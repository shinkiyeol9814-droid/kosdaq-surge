"""
한 시각의 수집·포착 — cron-job.org가 repository_dispatch로 하루 4번 부른다.

  python run.py --slot 1005|1205|1405|close
  python run.py --slot auto      # 지금 시각으로 슬롯을 고른다(맞는 슬롯이 없으면 그냥 끝)

auto는 cron-job.org에 잡 하나만 두려고 있다. 그쪽 Custom 일정은 '시 × 분' 조합이라
시 {10,12,14,15} × 분 {5,35}로 걸면 하루 8번 불리는데, 10:35·12:35·14:35·15:05 네 번은
AUTO_WINDOW 밖이라 아무것도 안 하고 끝난다.

휴장일엔 아무것도 안 하고 끝난다(수동 실행·FORCE_RUN=1은 예외).
"""
import argparse
import os
import sys

from surge import config as C
from surge import krxcal, naver, screen, store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True, choices=C.SLOTS + ["auto"])
    args = ap.parse_args()
    slot = args.slot

    now = store.now_kst()
    if slot == "auto":
        m = now.hour * 60 + now.minute
        slot = next((s for s, (a, b) in AUTO_WINDOW.items() if a <= m < b), None)
        if not slot:
            print(f"{now:%H:%M} — 수집 시각 아님, 건너뜀")
            return 0
        print(f"{now:%H:%M} → {C.SLOT_LABEL[slot]} 슬롯")
    forced = os.environ.get("FORCE_RUN") == "1" or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    reason = krxcal.closed_reason(now.date())
    if reason and not forced:
        print(f"{now:%Y-%m-%d} {reason} — 건너뜀")
        print(f"::notice title=휴장::{slot} 건너뜀 — {now:%Y-%m-%d} {reason}")
        return 0
    # 종가 슬롯이 장 마감 전에 돌면 누적값이 덜 찬 상태로 '종가'에 섞인다.
    if slot == "close" and now.strftime("%H%M") < "1531" and not forced:
        print(f"::warning title=이른 실행::종가 슬롯이 {now:%H:%M}에 불렸다 — 건너뜀")
        return 0
    # 장중 슬롯은 시각이 곧 기준이다 — 늦게 받은 누적값을 같은 시각 중앙값과 비교하면 배수가
    # 부풀고, 그 스냅샷이 다음 20일의 기준선까지 오염시킨다. 이르거나 30분 넘게 늦으면 버린다.
    hhmm = SLOT_TIME.get(slot)
    if hhmm and not forced:
        mins = (now.hour * 60 + now.minute) - (int(hhmm[:2]) * 60 + int(hhmm[2:]))
        if mins < 0 or mins > 30:
            print(f"::warning title=시각 벗어남::{slot} 슬롯이 {now:%H:%M}에 불렸다 — 건너뜀")
            return 0

    rows = {}
    for market, tag in (("KOSPI", "K"), ("KOSDAQ", "Q")):
        for code, (name, price, chg, value, mcap) in naver.market_snapshot(market).items():
            rows[code] = [name, tag, price, chg, value, mcap]
    if len(rows) < 1500:
        print(f"::error title=스냅샷 부족::{len(rows)}종목만 받았다")
        return 1

    day = now.strftime("%Y-%m-%d")
    taken = now.strftime("%Y-%m-%d %H:%M")
    store.save_snapshot(day, slot, taken, {c: r[4] for c, r in rows.items()})
    hits = screen.find_hits(day, slot, rows)
    screen.update_day(day, slot, taken, rows, hits)
    screen.rebuild_index()
    screen.prune_snapshots()
    late = ""
    if hhmm:
        mins = (now.hour * 60 + now.minute) - (int(hhmm[:2]) * 60 + int(hhmm[2:]))
        late = f" · {mins}분 늦음" if mins >= 10 else ""
    print(f"::notice title={C.SLOT_LABEL[slot]}::{len(rows)}종목 스냅샷 · 포착 {len(hits)}{late}")
    return 0


SLOT_TIME = {"1005": "1005", "1205": "1205", "1405": "1405"}
# auto가 슬롯으로 인정하는 시각 [시작, 끝) — 자정부터 분. 정시 호출 + GitHub 대기열 지연 여유.
AUTO_WINDOW = {"1005": (10 * 60 + 5, 10 * 60 + 30), "1205": (12 * 60 + 5, 12 * 60 + 30),
               "1405": (14 * 60 + 5, 14 * 60 + 30), "close": (15 * 60 + 31, 16 * 60)}

if __name__ == "__main__":
    sys.exit(main())
