"""
저장 위치.

  data/snap/{YYYY-MM-DD}/{slot}.json   시장 전체 스냅샷 — 중앙값 계산용(화면엔 안 나감)
  docs/data/days/{YYYY-MM-DD}.json     그날 포착 결과 — 화면이 읽는다(GitHub Pages)
  docs/data/index.json                 일자 목록과 시각별 건수

스냅샷엔 중앙값 계산에 필요한 누적거래대금만 백만원 단위 정수로 남긴다 — 하루 4번 × 약 4천 종목이
커밋되므로 이름·가격까지 넣으면 리포지토리가 금방 불어난다.
"""
import json
import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(ROOT, "data", "snap")
DAYS_DIR = os.path.join(ROOT, "docs", "data", "days")
INDEX = os.path.join(ROOT, "docs", "data", "index.json")


def now_kst():
    return datetime.now(KST)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def save_snapshot(day: str, slot: str, taken_at: str, values: dict):
    """values: {코드: 누적거래대금(원)} — 백만원 단위로 줄여 저장."""
    slim = {c: int(round(v / 1e6)) for c, v in sorted(values.items())}
    _write_json(os.path.join(SNAP_DIR, day, f"{slot}.json"), {"t": taken_at, "v": slim})


def load_snapshot(day: str, slot: str):
    try:
        with open(os.path.join(SNAP_DIR, day, f"{slot}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def snapshot_values(day: str, slot: str) -> dict:
    """{코드: 누적거래대금(원)} — 없으면 빈 dict."""
    snap = load_snapshot(day, slot)
    return {c: v * 1e6 for c, v in (snap or {}).get("v", {}).items()}


def snapshot_days() -> list:
    if not os.path.isdir(SNAP_DIR):
        return []
    return sorted(d for d in os.listdir(SNAP_DIR) if len(d) == 10)


def load_day(day: str) -> dict:
    try:
        with open(os.path.join(DAYS_DIR, f"{day}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_day(day: str, obj: dict):
    _write_json(os.path.join(DAYS_DIR, f"{day}.json"), obj)


def save_index(obj: dict):
    _write_json(INDEX, obj)
