"""
종합 수급 표를 사진으로 텔레그램에 보낸다 — 시장(코스피·코스닥)마다 다섯 장(매수강도 + 3기관·투신·사모·연기금 Top30).

  python inst_alert.py --auto            # 16시 알림: 16:00~16:59 개장일에만, 그날 한 번만
  python inst_alert.py [--day YYYY-MM-DD] # 수동(알림 테스트) — 시각·중복 검사 없이
  ... --check                            # 보낼 차례인지만 GITHUB_OUTPUT go=true|false (브라우저 설치 전에)
  ... --out DIR                          # 보내지 않고 사진만 DIR에 저장

16시는 KRX 확정치(18시 뒤) 전이라 **잠정치**다. 그날 투신·사모·연기금을 KRX에서 받아 메모리에서만 표를
만들고 data/inst엔 저장하지 않는다 — 확정치는 평소대로 18:35 flows.py가 받는다. 기준일 확정 결과
(docs/data/inst/{일자}.json)가 이미 있으면(18시 뒤 수동 테스트) 그걸 그대로 그린다.

그림은 사이트 화면 그대로다: docs/를 임시 폴더에 복사하고 그날 결과만 넣어 띄운 뒤 Playwright(Chromium)로
.sheet 다섯 개를 하나씩 찍는다. 그래서 표 모양을 바꾸려면 app.js·style.css만 고치면 된다.
보낸 날은 data/alert_state.json의 inst에 적어 16:35 호출이 다시 보내지 않게 한다.
"""
import argparse
import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time

from surge import config as C
from surge import inst, krx, krxcal, store, tg

STATE = os.path.join(store.ROOT, "data", "alert_state.json")
WINDOW = ("1600", "1700")          # --auto가 보내는 시각 [시작, 끝) — cron-job.org 16:05·16:35 호출
MARKETS = (("K", "코스피"), ("Q", "코스닥"))


def _state() -> dict:
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def due(now) -> str:
    """--auto에서 보낼 차례가 아니면 그 사유, 맞으면 빈 문자열."""
    if not krxcal.is_open(now.date()):
        return "휴장일"
    if not (WINDOW[0] <= now.strftime("%H%M") < WINDOW[1]):
        return f"{now:%H:%M} — 알림 시각(16시) 아님"
    if _state().get("inst") == now.strftime("%Y-%m-%d"):
        return "오늘 이미 보냄"
    return ""


def make_doc(day: str, now):
    """그날 종합 수급 결과. 확정 결과가 있으면 그것, 없으면 KRX 잠정치로 만든다. 아직 없으면 None."""
    final = store.load_inst_result(day)
    if final.get("mk"):
        return final
    if not krx.has_login():
        raise RuntimeError("KRX_ID / KRX_PW 가 없다 — Actions Secrets 확인")
    raw = {}
    for k, name in C.INST_KINDS:
        raw[k] = {c: round(v / 1e6) for c, v in krx.net_buy(day.replace("-", ""), name).items() if round(v / 1e6)}
        time.sleep(0.5)
    if not any(raw.values()):
        return None                                        # KRX가 아직 그날 표를 안 줬다
    rows = krx.listing(day.replace("-", ""))
    if len(rows) < 1500:
        return None
    opened = [d for d in store.inst_days() if d < day and "x" not in (store.load_inst_day(d) or {})]
    days = opened[-(C.INST_STREAK_DAYS - 1):] + [day]
    doc = inst.build(days, rows, now.strftime("%Y-%m-%d %H:%M"), last=raw)
    doc["pre"] = f"{now:%H:%M} 잠정치"
    return doc


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def shoot(doc: dict, out_dir: str) -> dict:
    """{시장: [사진 경로 5장]} — 사이트 사본을 띄우고 .sheet를 하나씩 찍는다."""
    from playwright.sync_api import sync_playwright

    day = doc["d"]
    site = tempfile.mkdtemp(prefix="inst-site-")
    shutil.copytree(os.path.join(store.ROOT, "docs"), site, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("days", "flow"))
    os.makedirs(os.path.join(site, "data", "inst"), exist_ok=True)
    with open(os.path.join(site, "data", "inst", f"{day}.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    with open(os.path.join(site, "data", "inst", "index.json"), "w", encoding="utf-8") as f:
        json.dump({"ver": doc.get("ver"), "updated": doc.get("updated", ""), "days": [day]}, f)

    handler = functools.partial(_Quiet, directory=site)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.makedirs(out_dir, exist_ok=True)
    shots = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=2,
                                    color_scheme="light")
            for mkt, _ in MARKETS:
                page.goto(f"http://127.0.0.1:{srv.server_port}/#inst/{mkt}/{day}")
                page.wait_for_function("document.querySelectorAll('#igrid .sheet').length === 5")
                page.wait_for_timeout(300)                 # 글꼴 적용
                files = []
                for i, el in enumerate(page.query_selector_all("#igrid .sheet")):
                    path = os.path.join(out_dir, f"{day}-{mkt}-{i + 1}.png")
                    el.screenshot(path=path)
                    files.append(path)
                shots[mkt] = files
            browser.close()
    finally:
        srv.shutdown()
        shutil.rmtree(site, ignore_errors=True)
    return shots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--day")
    ap.add_argument("--out")
    args = ap.parse_args()

    now = store.now_kst()
    day = args.day or now.strftime("%Y-%m-%d")
    why = due(now) if args.auto else ""
    if args.check:
        print(f"종합 수급 사진: {why or '보낼 차례'}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
                f.write(f"go={'false' if why else 'true'}\n")
        return 0
    if why:
        print(f"종합 수급 사진 건너뜀 — {why}")
        return 0

    doc = make_doc(day, now)
    if not doc:
        print(f"::notice title=종합 수급 사진::KRX에 {day} 기관 수급이 아직 없다 — 다음 호출에 다시")
        return 0
    cfg = tg.settings()
    if not cfg and not args.out:
        print(f"::notice title=종합 수급 사진::{tg.NO_SECRETS}")
        return 0
    shots = shoot(doc, args.out or tempfile.mkdtemp(prefix="inst-shots-"))
    if args.out:
        print(f"{sum(len(v) for v in shots.values())}장 저장 → {args.out}")
        return 0

    tag = doc.get("pre") or "확정치"
    tg.send_albums(cfg, [(f"📊 <b>{label} 종합 수급 · {day[5:].replace('-', '/')}</b> ({tag})", shots[mkt])
                         for mkt, label in MARKETS])
    if args.auto:
        st = _state()
        st["inst"] = day
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(st, f)
    print(f"::notice title=종합 수급 사진::{day} {tag} 코스피·코스닥 {sum(len(v) for v in shots.values())}장 보냄")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:   # Actions 로그는 로그인해야 보여서 사유를 실행 요약의 주석으로도 남긴다
        print(f"::error title=종합 수급 사진::{type(e).__name__}: {e}".replace(chr(10), " ")[:900])
        raise
