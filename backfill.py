"""
운영 첫날용 — 네이버 5분봉(최근 약 7거래일)으로 지난 날들의 시각별 누적거래대금을 재구성한다.

  python backfill.py            # 최근 개장일들(마감 뒤면 오늘 포함), 이미 있는 스냅샷은 건너뜀

거래대금 = Σ(5분 거래량 × 그 봉의 (고+저+종)/3). 실제 체결가 합과 1~2% 안쪽으로 맞는다.
중앙값엔 과거 5일 이상이 필요해서, 6일을 채우면 마지막 하루만 포착 결과가 나온다.
기준선이 20일을 다 채우는 건 실제 운영 4주 뒤다.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor

from surge import config as C
from surge import krxcal, naver, screen, store

CUTS = {"1005": "1005", "1205": "1205", "1405": "1405", "close": "9999"}


def main():
    now = store.now_kst()
    days = [d.strftime("%Y-%m-%d") for d in krxcal.open_days_before(now.date(), 6)]   # 오늘 포함 7일 중 지난 6일
    # 장 마감 뒤라면 오늘도 분봉으로 채운다(오늘 종가 슬롯 실행을 놓쳤을 때도 이걸로 메운다).
    if krxcal.is_open(now.date()) and now.strftime("%H%M") >= "1540":
        days.append(now.strftime("%Y-%m-%d"))
    todo = [d for d in days if not all(store.load_snapshot(d, s) for s in C.SLOTS)]
    if not todo:
        print("채울 날이 없다")
        return
    print("대상:", ", ".join(todo))

    rows_now = {}
    for market, tag in (("KOSPI", "K"), ("KOSDAQ", "Q")):
        for code, (name, price, chg, value, mcap) in naver.market_snapshot(market).items():
            rows_now[code] = [name, tag, price, chg, value, mcap]
    universe = [c for c, r in rows_now.items() if r[5] >= C.MIN_MCAP * 0.6]
    start, end = days[0].replace("-", ""), days[-1].replace("-", "")

    print(f"종목 {len(universe)}개 5분봉")

    def fetch(code):
        try:
            return code, naver.minute5_bars(code, start, end)
        except Exception:
            return code, None

    # 2500종목 × 120KB라 다시 받기 아깝다 — 같은 기간이면 로컬 캐시(.cache/, gitignore)를 쓴다.
    cache = os.path.join(store.ROOT, ".cache", f"bars_{start}_{end}.json")
    bars = {}
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            bars = json.load(f)
    else:
        with ThreadPoolExecutor(max_workers=10) as ex:
            for i, (code, b) in enumerate(ex.map(fetch, universe), 1):
                if b:
                    bars[code] = b
                if i % 300 == 0:
                    print(f"  {i}/{len(universe)}")
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(bars, f)
    print(f"분봉 {len(bars)}/{len(universe)}종목")

    # 날짜·시각별 [누적대금, 그 시각 종가], 그리고 전일 종가
    for di, day in enumerate(days):
        if day not in todo:
            continue
        ymd = day.replace("-", "")
        prev = days[di - 1].replace("-", "") if di else None
        per_slot = {s: {} for s in C.SLOTS}
        for code, b in bars.items():
            if code not in rows_now:     # 캐시 이후 목록에서 빠진 종목(거래정지 등)
                continue
            today = [x for x in b if x[0][:8] == ymd]
            if not today:
                continue
            prev_close = next((x[3] for x in reversed(b) if prev and x[0][:8] == prev), None)
            for slot, cut in CUTS.items():
                part = [x for x in today if x[0][8:12] < cut]
                if not part:
                    continue
                value = sum(x[1] * x[2] for x in part)
                price = part[-1][3]
                chg = (price / prev_close - 1) * 100 if prev_close else 0.0
                name, tag, p_now, _, _, cap_now = rows_now[code]
                mcap = cap_now * price / p_now if p_now else cap_now
                per_slot[slot][code] = [name, tag, price, chg, value, mcap]
        enough = len([d for d in store.snapshot_days() if d < day]) >= C.MIN_BASE_DAYS
        for slot in C.SLOTS:
            rows = per_slot[slot]
            taken = f"{day} {C.SLOT_LABEL[slot] if slot != 'close' else '15:30'}"
            store.save_snapshot(day, slot, taken, {c: r[4] for c, r in rows.items()})
            hits = screen.find_hits(day, slot, rows)
            if enough:
                # 뉴스는 '지금' 최신 기사라 지난 날에 붙이면 엉뚱하다 — 오늘만 붙인다.
                is_today = day == now.strftime("%Y-%m-%d")
                screen.update_day(day, slot, taken, rows, hits, with_news=is_today,
                                  note="5분봉으로 재구성한 날 — 거래대금은 근사치"
                                       + ("" if is_today else ", 뉴스 없음"))
            print(f"{day} {C.SLOT_LABEL[slot]}: {len(rows)}종목, 포착 {len(hits)}")
    if os.path.isdir(store.DAYS_DIR):
        screen.rebuild_index()


if __name__ == "__main__":
    main()
