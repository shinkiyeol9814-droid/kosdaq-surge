"""
업종 분류 — 종합 수급의 '3기관 매수강도 상위 30'(시장마다)을 업종별로 묶는 데 쓰는 종목별 업종 이름.

네이버 업종(약 80개, m.stock.naver.com/api/stock/{코드}/integration 의 industryCode → /api/stocks/industry/{번호}
의 groupInfo.name)을 config.SECTOR_MERGE로 묶고, config.SECTOR_THEME(코드 → 테마)로 덮는다.
결과는 docs/data/inst/{일자}.json의 mk.{K|Q}.sec = {코드: 업종} — 화면(app.js secSheet)이 2종목 이상인
업종은 한 줄로, 1종목뿐인 업종은 '기타'에 "이름(업종)"으로 모은다. 그 사진이 텔레그램 종합 수급 묶음에 같이 간다.
네이버가 막혀도 수급 결과는 나가야 하므로 실패는 경고만 남기고 sec 없이 둔다(그날 업종 표만 빠진다).
"""
from concurrent.futures import ThreadPoolExecutor

from surge import config as C
from surge import naver

_MERGE = {n: label for label, names in C.SECTOR_MERGE.items() for n in names}
_THEME = {code: label for label, codes in C.SECTOR_THEME.items() for code in codes}


def _industry_no(code: str):
    return (naver._get(f"https://m.stock.naver.com/api/stock/{code}/integration") or {}).get("industryCode")


def _industry_name(no) -> str:
    g = naver._get(f"https://m.stock.naver.com/api/stocks/industry/{no}?page=1&pageSize=1") or {}
    return (g.get("groupInfo") or {}).get("name", "")


def label(code: str, naver_name: str) -> str:
    if code in _THEME:
        return _THEME[code]
    if not naver_name:
        return "분류 없음"
    return _MERGE.get(naver_name, naver_name.replace(",", "·"))


def lookup(codes) -> dict:
    """{코드: 묶은 업종 이름}."""
    codes = list(dict.fromkeys(codes))
    with ThreadPoolExecutor(max_workers=6) as ex:
        nos = dict(zip(codes, ex.map(lambda c: None if c in _THEME else _industry_no(c), codes)))
    uniq = sorted({n for n in nos.values() if n})
    with ThreadPoolExecutor(max_workers=6) as ex:
        names = dict(zip(uniq, ex.map(_industry_name, uniq)))
    return {c: label(c, names.get(nos[c], "")) for c in codes}


def attach(doc: dict) -> dict:
    """종합 수급 결과(inst.build)에 시장마다 매수강도(3기관) 상위 종목의 업종을 붙인다. 실패하면 그대로 둔다."""
    try:
        for m in doc.get("mk", {}).values():
            m["sec"] = lookup(m["pow"]["s"])
    except Exception as e:
        print(f"::warning title=업종 분류::{type(e).__name__}: {e}"[:500])
        for m in doc.get("mk", {}).values():
            m.pop("sec", None)
    return doc
