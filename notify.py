"""
방금 수집한 시각의 포착 결과를 텔레그램으로 보낸다 — 워크플로우가 run.py 뒤에 부른다.

  python notify.py --slot 1005|1205|1405|close [--day YYYY-MM-DD] [--dry-run]

자매 프로젝트 stockapp2(batch_surge_alert.py)와 같은 방식: Telethon으로 **내 계정**이 보낸다.
환경변수(Actions Secrets) — 비어 있으면 보내지 않고 notice만 남기고 끝난다:
  TELEGRAM_API_ID / TELEGRAM_API_HASH   my.telegram.org에서 받은 앱 키
  TELEGRAM_SESSION                      StringSession 문자열(계정 전체 권한 — 절대 코드·로그에 남기지 말 것)
  SURGE_ALERT_CHAT                      보낼 곳: 초대 링크(t.me/+…) / @유저네임 / 채널 ID(-100…)
리포가 공개라서 보낼 곳(특히 비공개 초대 링크)도 시크릿으로만 받는다.

등급(★) ALERT_MIN_GRADE 이상만 한 줄씩 적고, 나머지는 건수와 사이트 링크로 대신한다(한 시각 100종목 남짓).
그날 앞 시각에 안 잡혔던 종목엔 🆕를 붙인다.
"""
import argparse
import asyncio
import html
import os
import re
import sys

from surge import config as C
from surge import store

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


def _invite_hash(chat: str):
    m = re.search(r"(?:t\.me/\+|t\.me/joinchat/|^\+)([A-Za-z0-9_-]+)", chat)
    return m.group(1) if m else None


async def send(texts, api_id, api_hash, session, chat):
    from telethon import TelegramClient
    from telethon.errors import UserAlreadyParticipantError
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import ImportChatInviteRequest

    client = TelegramClient(StringSession(session), api_id, api_hash, connection_retries=5, timeout=20)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("TELEGRAM_SESSION이 만료됐다 — 세션 문자열을 새로 만들어 시크릿을 바꿔야 한다")
        entity = None
        invite = _invite_hash(chat)
        if invite:   # 비공개 그룹: 아직 안 들어가 있으면 초대 해시로 입장
            try:
                updates = await client(ImportChatInviteRequest(invite))
                entity = updates.chats[0] if updates.chats else None
            except UserAlreadyParticipantError:
                pass
        if entity is None:
            entity = await client.get_entity(int(chat) if re.fullmatch(r"-?\d+", chat) else chat)
        for t in texts:
            await client.send_message(entity, t, parse_mode="html", link_preview=False)
    finally:
        await client.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True, choices=C.SLOTS)
    ap.add_argument("--day", default=store.now_kst().strftime("%Y-%m-%d"))
    ap.add_argument("--dry-run", action="store_true", help="보내지 않고 메시지만 출력")
    args = ap.parse_args()

    msgs = build_messages(args.day, args.slot)
    if not msgs:
        print(f"{args.day} {args.slot} 결과 없음 — 보낼 것 없음")
        return 0
    if args.dry_run:
        print("\n\n──────────\n\n".join(msgs))
        return 0

    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    session = os.environ.get("TELEGRAM_SESSION", "").strip()
    chat = os.environ.get("SURGE_ALERT_CHAT", "").strip()
    if not (api_id and api_hash and session and chat):
        print("::notice title=텔레그램::시크릿(TELEGRAM_API_ID/HASH/SESSION, SURGE_ALERT_CHAT)이 없어 보내지 않았다")
        return 0
    asyncio.run(send(msgs, int(api_id), api_hash, session, chat))
    print(f"::notice title=텔레그램::{C.SLOT_LABEL[args.slot]} 메시지 {len(msgs)}건 보냄")
    return 0


if __name__ == "__main__":
    sys.exit(main())
