"""
방금 수집한 시각의 포착 결과를 텔레그램으로 보낸다 — 워크플로우가 run.py 뒤에 부른다.

  python notify.py --slot 1005|1205|1405|close|latest [--day YYYY-MM-DD] [--dry-run]

latest는 그날 마지막으로 수집한 시각(수동 '알림 테스트' 실행용). 보내는 방법·시크릿은 surge/tg.py.

등급(★) ALERT_MIN_GRADE 이상만 한 줄씩 적고, 나머지는 건수와 사이트 링크로 대신한다(한 시각 100종목 남짓).
그날 앞 시각에 안 잡혔던 종목엔 🆕를 붙인다.
"""
import argparse
import html
import sys

from surge import config as C
from surge import store, tg

SITE = "https://shinkiyeol9814-droid.github.io/kosdaq-surge/"
MSG_LIMIT = 3500        # 텔레그램 4096자 제한에 여유를 두고 나눈다
MARKETS = (("K", "코스피"), ("Q", "코스닥"))


def build_messages(day: str, slot: str) -> list:
    doc = store.load_day(day)
    cur = doc.get("slots", {}).get(slot)
    if not cur:
        return []
    hits, stocks = cur["hits"], doc.get("stocks", {})
    earlier = {c for s in C.SLOTS[:C.SLOTS.index(slot)] for c in doc["slots"].get(s, {}).get("hits", {})}
    shown = {c: h for c, h in hits.items() if h[2] >= C.ALERT_MIN_GRADE}

    head = (f"📈 <b>거래대금 급증 · {day[5:].replace('-', '/')} {C.SLOT_LABEL[slot]}</b>\n"
            f"포착 {len(hits)}종목 · ★{C.ALERT_MIN_GRADE} 이상 {len(shown)}")
    blocks = []
    for mkt, label in MARKETS:
        codes = sorted((c for c in shown if stocks.get(c, {}).get("m") == mkt),
                       key=lambda c: (-shown[c][2], -shown[c][0]))
        if not codes:
            continue
        lines = [f"<b>[{label}]</b>"]
        for c in codes:
            mult, _rank, g, _price, chg, value, turn = shown[c]
            name = html.escape(stocks[c].get("n", c))
            dot = "🔴" if chg > 0 else "🔵" if chg < 0 else "⚪"
            new = " 🆕" if c not in earlier else ""
            lines.append(f"{'★' * g} <b>{name}</b> {mult:g}배{new}\n"
                         f"   {dot} {chg:+.2f}% · {value:,.0f}억 · 회전 {turn:g}%")
        blocks.append("\n".join(lines))
    rest = len(hits) - len(shown)
    tail = (f"그 밖 {rest}종목 · " if rest else "") + f'<a href="{SITE}#{day}/{slot}">사이트에서 보기</a>'
    blocks.append(tail)

    msgs, buf = [], head
    for b in blocks:
        if len(buf) + 2 + len(b) > MSG_LIMIT and buf != head:
            msgs.append(buf)
            buf = head + " (이어서)"
        buf += "\n\n" + b
    msgs.append(buf)
    return msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True, choices=C.SLOTS + ["latest"])
    ap.add_argument("--day", default=store.now_kst().strftime("%Y-%m-%d"))
    ap.add_argument("--dry-run", action="store_true", help="보내지 않고 메시지만 출력")
    args = ap.parse_args()

    if args.slot == "latest":
        done = store.load_day(args.day).get("slots", {})
        args.slot = next((s for s in reversed(C.SLOTS) if s in done), None)
        if not args.slot:
            print(f"::notice title=텔레그램::{args.day} 수집 결과가 없어 급등 알림은 건너뜀")
            return 0
    msgs = build_messages(args.day, args.slot)
    if not msgs:
        print(f"{args.day} {args.slot} 결과 없음 — 보낼 것 없음")
        return 0
    if args.dry_run:
        print("\n\n──────────\n\n".join(msgs))
        return 0

    cfg = tg.settings()
    if not cfg:
        print(f"::notice title=텔레그램::{tg.NO_SECRETS}")
        return 0
    tg.send_texts(cfg, msgs)
    print(f"::notice title=텔레그램::{C.SLOT_LABEL[args.slot]} 메시지 {len(msgs)}건 보냄")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:   # Actions 로그는 로그인해야 보여서 사유를 실행 요약의 주석으로도 남긴다
        print(f"::error title=텔레그램 급등 알림::{type(e).__name__}: {e}".replace(chr(10), " ")[:900])
        raise
