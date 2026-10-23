"""
KRX 개장일 판정 — cron-job.org는 요일·공휴일을 모르고 부르므로 휴장일엔 수집을 건너뛴다.

규칙: 주말 + holidays.KR(지방선거일·제헌절 포함) + 12/31 연말 휴장.
확인이 실패하면 개장일로 간주한다 — 평일 수집이 통째로 멈추는 쪽이 더 나쁘다.
"""
from datetime import date, timedelta

EXTRA_CLOSED: dict = {}     # 라이브러리가 모르는 임시공휴일 {date(YYYY, M, D): "사유"}
EXTRA_OPEN: set = set()


def closed_reason(d: date):
    if d in EXTRA_OPEN:
        return None
    if d in EXTRA_CLOSED:
        return EXTRA_CLOSED[d]
    if d.weekday() >= 5:
        return "주말"
    if (d.month, d.day) == (12, 31):
        return "연말 휴장"
    try:
        import holidays
        return holidays.KR(years=d.year).get(d) or None
    except Exception as e:
        print(f"공휴일 달력 확인 실패 — 개장일로 간주: {type(e).__name__}: {e}")
        return None


def is_open(d: date) -> bool:
    return closed_reason(d) is None


def open_days_before(d: date, n: int) -> list:
    """d 이전(당일 제외) 개장일 n개, 오래된 순."""
    out, p = [], d
    while len(out) < n:
        p -= timedelta(days=1)
        if is_open(p):
            out.append(p)
    return out[::-1]
