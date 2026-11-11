"""
저장 위치.

  data/snap/{YYYY-MM-DD}/{slot}.json   시장 전체 스냅샷 — 중앙값 계산용(화면엔 안 나감)
  docs/data/days/{YYYY-MM-DD}.json     그날 포착 결과 — 화면이 읽는다(GitHub Pages)
  docs/data/index.json                 일자 목록과 시각별 건수
  data/flow/{YYYY-MM-DD}.json          그날 투신 순매수 — 연속일 계산용(화면엔 안 나감)
  docs/data/flow/{YYYY-MM-DD}.json     그날 투신 두 목록 — 투신 탭이 읽는다
  docs/data/flow/index.json            투신 일자 목록과 목록별 건수
  data/inst/{YYYY-MM-DD}.json          그날 투신·사모·연기금 순매수 — 연속일 계산용(화면엔 안 나감)
  docs/data/inst/{YYYY-MM-DD}.json     그날 종합 수급 표(코스피·코스닥) — 종합 수급 탭이 읽는다
  docs/data/inst/index.json            종합 수급 일자 목록

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
FLOW_DIR = os.path.join(ROOT, "data", "flow")
FLOW_OUT_DIR = os.path.join(ROOT, "docs", "data", "flow")
FLOW_INDEX = os.path.join(FLOW_OUT_DIR, "index.json")
INST_DIR = os.path.join(ROOT, "data", "inst")
INST_OUT_DIR = os.path.join(ROOT, "docs", "data", "inst")
INST_INDEX = os.path.join(INST_OUT_DIR, "index.json")


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


def save_flow_day(day: str, values: dict, closed: bool = False):
    """values: {코드: 투신 순매수(원)} — 백만원 단위, 0은 뺀다. closed면 KRX가 빈 표를 준 날(휴장)."""
    slim = {c: int(round(v / 1e6)) for c, v in sorted(values.items()) if round(v / 1e6)}
    _write_json(os.path.join(FLOW_DIR, f"{day}.json"), {"x": "휴장"} if closed else {"v": slim})


def load_flow_day(day: str):
    try:
        with open(os.path.join(FLOW_DIR, f"{day}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def flow_days() -> list:
    if not os.path.isdir(FLOW_DIR):
        return []
    return sorted(f[:10] for f in os.listdir(FLOW_DIR) if f.endswith(".json"))


def load_flow_index() -> dict:
    try:
        with open(FLOW_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_flow_index(obj: dict):
    _write_json(FLOW_INDEX, obj)


def flow_result_days() -> list:
    if not os.path.isdir(FLOW_OUT_DIR):
        return []
    return sorted(f[:10] for f in os.listdir(FLOW_OUT_DIR) if f.endswith(".json") and f[:4].isdigit())


def load_flow_result(day: str) -> dict:
    try:
        with open(os.path.join(FLOW_OUT_DIR, f"{day}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_flow_result(day: str, obj: dict):
    _write_json(os.path.join(FLOW_OUT_DIR, f"{day}.json"), obj)


# ── 기관 수급 ──
def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _dated(folder) -> list:
    if not os.path.isdir(folder):
        return []
    return sorted(f[:10] for f in os.listdir(folder) if f.endswith(".json") and f[:4].isdigit())


def save_inst_day(day: str, values: dict):
    """values {종류: {코드: 원}} — 백만원 정수로, 0은 뺀다. 전부 비면(휴장) {"x": "휴장"}."""
    obj = {k: {c: round(v / 1e6) for c, v in vs.items() if round(v / 1e6)} for k, vs in values.items()}
    _write_json(os.path.join(INST_DIR, f"{day}.json"), obj if any(obj.values()) else {"x": "휴장"})


def load_inst_day(day: str):
    return _load(os.path.join(INST_DIR, f"{day}.json"))


def inst_days() -> list:
    return _dated(INST_DIR)


def load_inst_index() -> dict:
    return _load(INST_INDEX) or {}


def save_inst_index(obj: dict):
    _write_json(INST_INDEX, obj)


def inst_result_days() -> list:
    return _dated(INST_OUT_DIR)


def save_inst_result(day: str, obj: dict):
    _write_json(os.path.join(INST_OUT_DIR, f"{day}.json"), obj)
