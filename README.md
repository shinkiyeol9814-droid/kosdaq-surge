# 거래대금 급증 스크리너

코스피·코스닥에서 **같은 시각** 평소보다 거래대금이 몇 배로 불어난 종목을 하루 네 번(10:05 · 12:05 · 14:05 · 종가) 잡아내는 정적 페이지.
GitHub Actions가 네이버 금융 공개 시세를 받아 `docs/data`에 JSON으로 커밋하고, GitHub Pages가 `docs/`를 그대로 보여준다. 서버가 없다.

## 포착 기준 (`surge/config.py`)

- 시가총액 300억 이상
- 그 시각까지의 누적거래대금 ≥ 최근 20거래일 같은 시각 누적거래대금 **중앙값의 3배**
- 누적거래대금 장중 3억 / 종가 30억 이상
- 등급 = 두 축 중 높은 쪽
  - 규모(같은 시장 안 거래대금 순위): 5위 ★★★ · 15위 ★★ · 50위 ★
  - 손바뀜(거래대금 ÷ 시총): 120% ★★★ · 60% ★★ · 20% ★

중앙값은 과거 5일 이상 쌓인 종목만 계산한다. 운영 첫날은 `backfill.py`가 5분봉으로 최근 약 7거래일을 재구성하므로,
기준선이 20일을 다 채우는 건 실제 운영 약 4주 뒤다(그 전엔 배수가 실제보다 들쭉날쭉할 수 있다).

## 구조

| 경로 | 내용 |
|---|---|
| `run.py --slot 1005\|1205\|1405\|close` | 시장 전체 스냅샷 → 포착 → 일자 파일 갱신 |
| `backfill.py` | 5분봉으로 지난 며칠의 시각별 누적거래대금 재구성(없는 날만) |
| `surge/naver.py` | 시세 목록·일봉·5분봉·뉴스 |
| `surge/screen.py` | 중앙값 기준선, 포착, 등급, 일자/색인 파일 |
| `surge/krxcal.py` | 휴장일 판정(주말·공휴일·연말) |
| `data/snap/{일자}/{시각}.json` | 종목별 누적거래대금(백만원) — 기준선 계산용, 45거래일 보관 |
| `docs/data/days/{일자}.json` | 화면이 읽는 그날의 포착 결과 — 30거래일 보관 |
| `docs/` | 정적 페이지(index.html · app.js · style.css) |

## 실행 일정 (cron-job.org)

잡 하나로 된다 — Custom 일정에서 요일 월~금, 시 **10·12·14·15**, 분 **5·35**, 시간대 Asia/Seoul.
하루 8번 불리고 그중 10:05 · 12:05 · 14:05 · 15:35만 수집하며 나머지 네 번은 바로 끝난다.

```
POST https://api.github.com/repos/<owner>/kosdaq-surge/dispatches
Authorization: Bearer <토큰>          # fine-grained, 이 리포 Contents: Read and write
Accept: application/vnd.github+json
{"event_type": "snapshot", "client_payload": {"slot": "auto"}}
```

장중 슬롯은 정시보다 이르거나 30분 넘게 늦게 돌면 버린다(늦게 받은 누적값은 배수를 부풀리고 이후 20일의 기준선까지 오염시킨다).
종가 슬롯은 15:31~15:59에만 받는다(16시부터 시간외 단일가가 섞인다). 수동 실행(Actions → Snapshot → Run workflow)은 이 검사를 건너뛴다.

로컬: `pip install -r requirements.txt` → `FORCE_RUN=1 python run.py --slot close` → `python -m http.server -d docs`.
