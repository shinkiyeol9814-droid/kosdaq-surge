"""
텔레그램 보내기 — stockapp2(batch_surge_alert.py)와 같은 방식: Telethon으로 **내 계정**이 보낸다.

환경변수(Actions Secrets) — 하나라도 비면 settings()가 None을 돌려주고 부르는 쪽은 보내지 않는다:
  TELEGRAM_API_ID / TELEGRAM_API_HASH   my.telegram.org에서 받은 앱 키
  TELEGRAM_SESSION                      StringSession 문자열(계정 전체 권한 — 절대 코드·로그에 남기지 말 것)
  SURGE_ALERT_CHAT                      보낼 곳: 초대 링크(t.me/+…) / @유저네임 / 채널 ID(-100…)
리포가 공개라서 보낼 곳(특히 비공개 초대 링크)도 시크릿으로만 받는다.
"""
import asyncio
import os
import re

NO_SECRETS = "시크릿(TELEGRAM_API_ID/HASH/SESSION, SURGE_ALERT_CHAT)이 없어 보내지 않았다"


def settings():
    v = {k: os.environ.get(k, "").strip()
         for k in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION", "SURGE_ALERT_CHAT")}
    return v if all(v.values()) else None


def _invite_hash(chat: str):
    m = re.search(r"(?:t\.me/\+|t\.me/joinchat/|^\+)([A-Za-z0-9_-]+)", chat)
    return m.group(1) if m else None


async def _run(cfg, job):
    from telethon import TelegramClient
    from telethon.errors import UserAlreadyParticipantError
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import ImportChatInviteRequest

    client = TelegramClient(StringSession(cfg["TELEGRAM_SESSION"]), int(cfg["TELEGRAM_API_ID"]),
                            cfg["TELEGRAM_API_HASH"], connection_retries=5, timeout=20)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("TELEGRAM_SESSION이 만료됐다 — 세션 문자열을 새로 만들어 시크릿을 바꿔야 한다")
        chat, entity = cfg["SURGE_ALERT_CHAT"], None
        invite = _invite_hash(chat)
        if invite:   # 비공개 그룹: 아직 안 들어가 있으면 초대 해시로 입장
            try:
                updates = await client(ImportChatInviteRequest(invite))
                entity = updates.chats[0] if updates.chats else None
            except UserAlreadyParticipantError:
                pass
        if entity is None:
            entity = await client.get_entity(int(chat) if re.fullmatch(r"-?\d+", chat) else chat)
        await job(client, entity)
    finally:
        await client.disconnect()


def send_texts(cfg, texts):
    async def job(client, entity):
        for t in texts:
            await client.send_message(entity, t, parse_mode="html", link_preview=False)
    asyncio.run(_run(cfg, job))


def send_albums(cfg, albums):
    """albums: [(캡션, [이미지 경로...])] — 하나가 사진 묶음 한 건(최대 10장), 캡션은 첫 장에."""
    async def job(client, entity):
        for caption, files in albums:
            await client.send_file(entity, files, caption=[caption] + [""] * (len(files) - 1),
                                   parse_mode="html")
    asyncio.run(_run(cfg, job))
