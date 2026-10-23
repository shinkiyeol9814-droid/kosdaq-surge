# AGENTS.md

AI 코딩 에이전트(Claude Code 등)를 위한 프로젝트 가이드. 코드 수정 전 이 파일부터 읽을 것.

---

## 프로젝트 개요

코스피·코스닥에서 **같은 시각** 평소보다 거래대금이 몇 배로 불어난 종목을 하루 네 번 잡아내는 스크리너.
https://kosdaq-surge.yunhee2368.workers.dev/ 와 같은 기능을 목표로 2026-10-23 새로 만들었다
(화면 디자인·코드는 독자적으로 작성 — 원 사이트의 코드나 브랜딩을 가져오지 말 것).

- **서버 없음.** GitHub Actions가 수집해 JSON을 커밋하고, GitHub Pages가 `docs/`를 그대로 서빙한다.
- 사이트: https://shinkiyeol9814-droid.github.io/kosdaq-surge/
- 리포: `shinkiyeol9814-droid/kosdaq-surge` (**공개** — 비밀값을 코드·데이터에 넣지 말 것)
- 자매 프로젝트: `D:\Claude\Stkapp` (Streamlit 주식 앱, 별도 리포). 코드를 공유하지 않는다.

| 환경 | Python |
|---|---|
| GitHub Actions | 3.12 (워크플로우에 고정) |
| 로컬 | 3.13 |

의존성은 `requests`, `holidays` 둘뿐이다. 프런트엔드는 빌드 도구 없는 순수 HTML/CSS/JS.

---

## ⚠️ 색상 규칙 (한국 증시 관례)

| 상태 | 색 |
|---|---|
| 상승 / 양수 | 빨강 `--up: #ef5350` |
| 하락 / 음수 | 파랑 `--down` (다크 `#4a8ff0`, 라이트 `#1565c0` — 어두운 배경에서 #1565C0는 안 보여서 밝혔다) |
| 보합 | 회색 `--flat: #888888` |

일봉 스파크라인도 같다(양봉 빨강, 음봉 파랑). 초록을 쓰지 말 것.

---

## 파일 구조

| 경로 | 역할 |
|---|---|
| `run.py --slot 1005\|1205\|1405\|close\|auto` | 시장 전체 스냅샷 → 포착 → 일자 파일·색인 갱신 → 오래된 파일 정리 |
| `backfill.py` | 네이버 5분봉으로 최근 약 7거래일 재구성(이미 있는 날은 건너뜀) |
| `surge/config.py` | **포착·등급 기준 숫자** (화면 설명은 `index.json.criteria`로 자동 반영) |
| `surge/naver.py` | 네이버 공개 API — 시총순 목록, 일봉, 5분봉, 뉴스 |
| `surge/screen.py` | 중앙값 기준선, 포착, 등급, 일자 파일, 색인, 보관 기간 정리 |
| `surge/store.py` | 파일 경로·읽기/쓰기 (KST 기준 `now_kst()`) |
| `surge/krxcal.py` | 휴장일 판정 (stdlib `calendar`와 이름이 겹쳐 krxcal로 지었다) |
| `docs/index.html · app.js · style.css` | 정적 화면 |
| `.github/workflows/snapshot.yml` | repository_dispatch(`snapshot`) / 수동 실행 |

### 데이터 레이아웃
```
data/snap/{YYYY-MM-DD}/{slot}.json   {"t": "수집시각", "v": {코드: 누적거래대금(백만원 정수)}}
                                     기준선 계산 전용 — 화면엔 안 나감. 45거래일 보관(SNAP_KEEP_DAYS)
docs/data/days/{YYYY-MM-DD}.json     화면이 읽는 그날 결과. 30거래일 보관(KEEP_DAYS)
  slots.{slot}.hits.{코드} = [배수, 시장 내 대금순위, 등급, 현재가, 등락률, 거래대금(억), 회전율%]
  stocks.{코드} = {n 이름, m 시장 K/Q, p 현재가, c 등락률, v 거래대금(억), cap 시총(억), turn,
                   news [제목, 언론사, URL, YYYYMMDDHHMM], k 3개월 일봉 [[시,고,저,종]...]}
  note = 재구성한 날 등 화면에 띄울 한 줄
docs/data/index.json                 일자 목록·시각별 건수·기준값(criteria), 화면 첫 로딩용
```
'종합' 탭은 저장하지 않는다 — 브라우저가 `slots`를 합쳐 만든다(정렬: 잡힌 시각 수 → 최고 배수).

---

## 포착 기준 (`surge/config.py`)

- 시가총액 ≥ 300억
- 누적거래대금 ≥ 최근 20거래일 **같은 시각** 누적거래대금 **중앙값 × 3**
  - 과거가 5일 미만인 종목은 계산하지 않는다(`MIN_BASE_DAYS`) — 신규 상장·운영 초기
  - 중앙값이 0이면(거래정지 등) 건너뜀
- 누적거래대금 하한: 장중 3억 / 종가 30억
- 등급 = 두 축 중 높은 쪽
  - 규모: 같은 시장 안 거래대금 순위 5위 ★★★ · 15위 ★★ · 50위 ★
  - 손바뀜: 거래대금 ÷ 시총 120% ★★★ · 60% ★★ · 20% ★

기준을 바꾸면 **이후 결과만** 바뀐다. 지난 일자 파일은 다시 계산하지 않는다.

---

## 실행 일정과 시각 규칙

cron-job.org **잡 하나**가 평일 시 {10,12,14,15} × 분 {5,35}(Asia/Seoul)에 다음을 보낸다:
```
POST https://api.github.com/repos/shinkiyeol9814-droid/kosdaq-surge/dispatches
{"event_type": "snapshot", "client_payload": {"slot": "auto"}}
```
토큰은 fine-grained(이 리포만, Contents: Read and write)이고 **cron-job.org에만** 있다.
Actions Secrets는 쓰지 않는다(커밋은 기본 `GITHUB_TOKEN`).

`auto`는 지금 시각으로 슬롯을 고른다(`run.AUTO_WINDOW`):
10:05~10:29 → 1005, 12:05~12:29 → 1205, 14:05~14:29 → 1405, 15:31~15:59 → close. 그 밖(10:35 등)은 그냥 끝.

**시각이 곧 기준이다.** 늦게 받은 누적값을 같은 시각 중앙값과 비교하면 배수가 부풀고, 그 스냅샷이
이후 20일의 기준선까지 오염시킨다. 그래서:
- 장중 슬롯을 직접 지정했을 때도 정시보다 이르거나 30분 넘게 늦으면 버린다.
- 종가 슬롯은 15:31 이전이면 버린다. 15:35를 쓰는 이유: 15:40부터 시간외 종가 거래가 붙는다.
- 휴장일(주말·`holidays.KR`·12/31)은 건너뛴다. 판정 실패 시 개장일로 간주.
- 수동 실행(`workflow_dispatch`)과 로컬 `FORCE_RUN=1`은 위 검사를 모두 건너뛴다 — 장중에 `close`를
  수동으로 돌리면 덜 찬 값이 종가로 저장되니 주의.

---

## 네이버 API에서 알아낸 것 (바꾸기 전에 읽을 것)

- **시총순 목록** `m.stock.naver.com/api/stocks/marketValue/{KOSPI|KOSDAQ}?page&pageSize=100`
  - `pageSize`는 100이 상한(더 주면 JSON이 아닌 응답).
  - 페이지를 따로 받는 사이 순위가 바뀌어 경계 종목이 빠지거나 겹친다 — 장 마감 뒤에도 두 번 받으면
    한두 종목이 달랐다. 그래서 **두 번 받아 합친다**(`market_snapshot`). 합쳐도 2~4초.
  - 코스피 목록엔 ETF·ETN이 섞여 있다 → `stockEndType == "stock"`만. 우선주는 남긴다.
  - 금액 필드는 `...Raw`(원 단위)를 쓴다.
- **분봉** `api.stock.naver.com/chart/domestic/item/{code}/minute5?startDateTime&endDateTime`
  - 1·3·5·10·30·60분봉 모두 **최근 약 7거래일**만 준다. 그 이상 과거는 없다.
  - 필드명이 `accumulatedTradingVolume`이지만 **그 봉 하나의 거래량**이다(1분봉 합 = 10분봉 값 확인).
  - 봉 시각은 시작 시각 — "1000" 봉은 10:00~10:05. 10:05 누적 = 라벨 < "1005"인 봉의 합.
  - 일봉 거래량과 분봉 합은 6% 안팎 차이(시간외 거래). 분봉 재구성 대금은 Σ(거래량 × (고+저+종)/3).
- **일봉** `.../item/{code}/day` — 3개월 스파크라인용.
- **뉴스** `m.stock.naver.com/api/news/stock/{code}` — 제목이 **이미 HTML 이스케이프돼** 온다(`&quot;`).
  `html.unescape` 후 저장한다(화면이 다시 이스케이프하므로 안 풀면 `&amp;quot;`로 보인다).
- 러너(미국)에서도 정상 동작 확인(2026-10-23).

---

## 백필의 한계

분봉이 7거래일뿐이라 첫날 백필로 채운 건 2026-10-15~10-23이다. 기준선 5일이 필요하니 결과가 나온 날은
10/22·10/23뿐이고, **20일 기준선이 다 차는 건 운영 약 4주 뒤**다. 그 전엔 지난주에 이미 거래가 많았던
종목의 배수가 원 사이트보다 낮게 나오거나 빠진다(10/22: 우리 70/85/86/46 vs 원 사이트 81/96/106/57).

- 재구성한 날은 `note`에 표시된다. 뉴스는 '지금' 최신 기사라 지난 날엔 붙이지 않는다(오늘만).
- 분봉 2500종목 × 120KB를 받으므로 `.cache/bars_*.json`(gitignore)에 캐시한다.
- 장 마감 뒤에 돌리면 오늘도 채운다 — 종가 실행을 놓친 날 메우는 용도.

---

## 리포지토리 비대화 방지

하루 4번 커밋이 쌓인다.
- 스냅샷엔 **누적거래대금만** 백만원 정수로(파일당 약 30KB). 이름·가격을 넣지 말 것.
- 일자 파일은 30거래일, 스냅샷은 45거래일 지나면 지운다(`rebuild_index`, `prune_snapshots`).
- 일자 파일 크기의 대부분은 3개월 일봉이다(포착 100종목 ≈ 200KB). 늘릴 땐 이걸 먼저 의심.

---

## 화면 (`docs/`)

- 상태는 URL 해시 `#YYYY-MM-DD/slot` — 링크 공유·뒤로 가기 가능(`hashchange` 처리).
- `index.json`은 매번 `?t=now`로, 일자 파일은 `?v=updated`로 받는다(Pages 캐시 10분 회피).
- 다크 기본 + `prefers-color-scheme: light` 대응. 색은 `:root` 토큰으로만.
- 휴대폰(≤640px): `#` 열·종목코드 숨김, **종목명 열 sticky** — 표를 옆으로 밀어도 이름이 남는다.
- 정렬: 첫 클릭은 큰 값부터(이름만 가나다순), 다시 누르면 반대.

---

## 로컬 실행

```bash
pip install -r requirements.txt
FORCE_RUN=1 python run.py --slot close      # 실제 data/·docs/data를 바꾼다 — 테스트는 복사본에서
python -m http.server 8781 -d docs          # http://localhost:8781
```
테스트 실행 결과를 커밋하지 말 것. 실험은 리포를 임시 폴더로 복사해서 한다.

줄바꿈은 LF(`core.autocrlf false`). Windows에서 파일을 쓸 땐 `newline="\n"`.

---

## 확인할 곳

- 실행 기록: https://github.com/shinkiyeol9814-droid/kosdaq-surge/actions — 실행마다
  `::notice`로 "N종목 스냅샷 · 포착 M"이 남는다. 건너뛴 실행은 사유가 warning/notice로 남는다.
- Pages 설정: Settings → Pages (main `/docs`).
