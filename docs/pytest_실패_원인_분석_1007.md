# scripts pytest 기존 실패 원인 분석 (2026-10-07)

**결론: 이 클라우드(리눅스) 세션에서는 `python3 -m pytest scripts -q`를 최신 main(커밋 440af1079)에서 5회 돌렸지만 매번 0건 실패(345 passed, 1 xfailed)로, 보고된 "277 통과·31 실패(흔들려서 22건)"를 전혀 재현하지 못했다 — 코드 리뷰로 찾은 위험 패턴 중 실제로 재현·확인한 것은 `scripts/hermes_courier/test_courier.py` 하나(수집만 해도 실제 저장소 파일을 바꾸는 부작용)뿐이고, 나머지는 "미확인" 가설로만 남긴다.**

## 실행 방법과 회차별 결과

환경: 이 클라우드 세션(Linux, Python 3.13.16, pytest 9.1.1), 저장소 커밋 `440af1079`(2026-10-07, PR #2019 병합 직후). 매 회차 `timeout 300 python3 -m pytest scripts -q`로 실행했고, 어느 회차도 타임아웃에 걸리지 않았다(모두 10~12초 안에 끝남).

| 회차 | 결과 | 걸린 시간 |
|---|---|---|
| 1 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.71s |
| 2 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.29s |
| 3 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.37s |
| 4 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.45s |
| 5 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 11.00s |

`--collect-only`로는 346개 항목(345 + xfail 1건)이 잡힌다. 매번 실패 수가 토씨 하나 안 틀리고 0건 — "회차별로 실패 건수가 달라진다"는 보고된 증상이 이 환경에서는 아예 성립하지 않는다. xfail 1건(`test_ask_vertex_fallback.py::GeneralException::test_token_issuing_exception_falls_back_to_free`)은 의도된 표시라 이번 분석 대상이 아니다.

CI(`build-check.yml`)는 애초에 이 넓은 범위를 돌리지 않는다 — `python3 -m pytest scripts/ops/tests -q`만 자동 실행하고, `scripts` 전체를 겨냥한 실행은 어디에도 없다. 즉 "277/31"은 누군가(아마 운영 기기, 대장 메모의 "신PC")가 수동으로 넓게 돌린 결과로 보이며, 자동화된 재현 경로가 없다.

## 원인별 분류

**실패를 직접 분류할 수 없었다(위 결과대로 실패가 0건이었으므로).** 대신 "실패했다면 그 원인이 됐을 법한" 위험 패턴을 코드를 읽어 찾았다. 아래 분류 중 ①만 직접 재현·확인했고, 나머지는 코드 구조상 존재를 확인했을 뿐 실제 실패로 이어지는 것은 보지 못했다.

① **모듈 수집 중 최상위 코드 부작용 + 시험 간 상태 공유(실제 파일)** — 확인함, 1개 파일
- `scripts/hermes_courier/test_courier.py`: `def test_...` 함수가 하나도 없다. 파일 맨 위(모듈 최상위)에서 바로 `reset()` → `mail(...)` 여러 번 → `run()`(실제 `subprocess.run`으로 `mailbox_courier.py` 실행)을 호출하고 `check()`가 그 결과를 `print()`만 한다. pytest는 이 파일에서 "수집할 테스트가 0개"라고 보지만, **수집(import)하는 것만으로** 저장소의 실제 파일 `scripts/hermes_courier/tstate.json`을 덮어쓴다. `--collect-only`로도 재현됨(아래 "재현 여부" 참고).
- 같은 폴더의 `scripts/ops/*.py`(`test_denied_notify.py`, `test_inventory_trend.py`, `test_kick_publish.py`, `test_lints.py`, `test_local_llm.py`, `test_night_research.py`)도 구조가 같다(최상위에서 바로 실행하고 `sys.exit()`). 다만 이쪽은 PR #2018에서 추가된 `scripts/conftest.py`의 `collect_ignore_glob`이 `scripts/ops/` 바로 아래 `test_*.py`를 전부 가려서, 지금의 `pytest scripts`에서는 수집되지 않는다. `scripts/hermes_courier/`, `scripts/hermes_ops/`는 이 가림 목록에 없다 — `scripts/hermes_ops/test_pending_detector.py`는 `unittest.TestCase` 기반 정상 시험이라 문제 없지만, `test_courier.py`는 빠져나갔다.

② **시각·날짜 의존(이론상 레이스)** — 미확인, 코드만 확인
- `scripts/ops/tests/test_worklog.py`: `wl.add(...)`를 호출해 내부적으로 기록되는 `source_date`와, 테스트가 그 직후 독립적으로 다시 계산하는 `datetime.now().strftime("%Y-%m-%d")`를 비교하는 자리가 5곳(줄 51, 104, 111, 152, 158). 두 번의 `datetime.now()` 호출 사이에 자정을 넘으면 하루 차이로 실패할 수 있다. 실제로 그런 순간에 걸려 실패한 사례는 보지 못했다(극히 드묾, "흔들리는 이유"로 보기엔 빈도가 안 맞음).

③ **실제(운영) 설정 파일 의존** — 확인함(실패는 아님, 설계상 의도)
- `scripts/ops/tests/test_jobs_schema.py`는 고정된 픽스처가 아니라 저장소의 실제 운영 파일 `scripts/ops/jobs.toml`·`jobs_goosolar.toml`을 그대로 읽어 스키마를 검사한다(의도된 설계: 감시 대장이 깨지면 바로 알아채려는 린트). 두 파일이 지금은 유효해서 통과하지만, 둘 중 하나가 편집 도중(필수 칸 누락 등)인 상태에서 다른 세션이 동시에 테스트를 돌리면 "코드 버그"가 아니라 "설정 파일이 그 순간 불완전"해서 실패할 수 있다.

④ **외부 서비스·네트워크 호출** — 코드상 없음을 확인
- `opsdb`를 참조하는 시험 파일(`test_worklog.py`, `test_recall.py`)은 전부 `mock.patch`/`monkeypatch`로 막혀 있고 실제 네트워크 호출이 없다. `urllib`를 쓰는 `test_ask_vertex_fallback.py`도 `urlopen` 자체를 `mock.patch`로 교체해 실제 요청을 보내지 않는다. 이번 점검 범위에서 실제로 외부에 나가는 호출은 찾지 못했다.

⑤ **코드와 시험의 불일치** — 이번 범위에서 못 찾음
- 명시적으로 지목된 `test_card.py`, `test_scheduled_publish.py`를 포함해 전체 346개 항목이 이 환경에서 전부 통과했고, 코드를 읽어도 두 파일에서 구현과 시험이 어긋나는 지점을 찾지 못했다. "원래 있던 실패"라는 보고와 달리 이 환경에서는 근거를 못 찾았다 — 미확인으로 남긴다.

## 재현 여부

- **① 모듈 수집 부작용**: 단독 실행(`pytest scripts/hermes_courier/test_courier.py --collect-only -q`)에서도, 전체 실행(`pytest scripts -q`) 안에서도 둘 다 재현됨(`git diff`로 `tstate.json`의 날짜 키가 실행 때마다 오늘 날짜로 갱신되는 것을 직접 확인). 단, 이 부작용 자체는 pytest의 "failed" 카운트에는 안 잡힌다(테스트 함수가 없어 그냥 0개 수집으로 끝남) — 그래서 "31건 실패"의 직접 원인이라고 단정할 수는 없고, "원인불명 실패가 쌓일 수 있는 토양"이라는 정도로만 말할 수 있다.
- **②③④⑤**: 이 환경(전체 실행 5회, 개별 파일 실행 포함)에서 재현되는 실패가 없어 "단독/전체 실행 시 재현 여부" 자체를 확인할 실패 사례가 없었다. 코드 구조상 가능성만 적었다.

## 흔들리는 이유 가설 (31건 ↔ 22건)

- **가설 A: 실제 운영 경로·운영 중인 백그라운드 프로세스와의 경합.** `scripts/ops/`의 여러 모듈(`watch.py`, `recall.py`, `session_brief.py`, `review_queue.py`)은 테스트에서 격리되지 않는 한 기본값이 실제 운영 경로(`C:\work\_ops`, `C:\work\hansunghee7.github.io` 등)를 가리키도록 `os.environ.get("OPS_*", 실경로)`로 짜여 있다. 만약 "31건" 보고가 실제 운영 기기(신PC, 대장 문서가 "신PC"라고 부르는 기기)에서 나온 것이고 그 기기에서 헤르메스 크론이 동시에 돌고 있었다면, 같은 상태 파일(`state.json`, `ports_baseline.json`, 우편함 등)을 테스트와 실제 크론이 동시에 건드려 경합이 생길 수 있다 — **확인한 증거**: ①에서 테스트가 실제 공유 파일을 쓰는 것은 직접 봤다. **미확인**: 그 순간 실제로 헤르메스 크론이 같이 돌고 있었는지, 그래서 쓰기 경합이 일어났는지는 이 세션에서 알 수 없다.
- **가설 B: 환경(패키지·OS) 차이.** 이 클라우드 세션은 처음에 `pytest`가 설치돼 있지 않아 별도로 설치해야 했다(`/usr/bin/python3`엔 없었고 `/root/.local/bin/pytest`라는 별도 uv 툴만 있었음). "31건" 보고가 나온 기기의 파이썬 환경에 `pytest`/`PyYAML` 등의 버전이나 설치 여부가 다르면, import 단계에서부터 결과가 달라질 수 있다. **미확인**: 그 기기의 실제 패키지 목록을 받지 못해 비교 불가.
- **가설 C: 측정 시점의 커밋이 다름.** "31건" 수치가 나온 시점이 이번 세션이 보는 `440af1079`(PR #2019까지 반영) 이전이었다면, 그사이 머지된 `scripts/conftest.py` 수정(PR #2014, #2018)이나 이번에 추가된 시험들이 결과를 바꿨을 수 있다. 실제로 테스트 총 개수부터 다르다(보고 277+31=308건 vs 이 세션 345+1=346건, 38개 차이) — **확인한 사실**: 총 개수가 다르다는 것 자체. **미확인**: 어느 커밋에서 측정했는지, 그 차이가 전적으로 테스트 추가분 때문인지.
- 세 가설 모두 **이 클라우드 세션은 구조적으로 검증할 수 없다**: 네트워크가 격리돼 있고(`C:\work\_ops` 같은 실제 운영 경로가 존재하지 않음), 신PC에 떠 있는 진짜 헤르메스 크론에도 접근할 수 없다.

## 권장 수정 순서

1. **[소] `scripts/hermes_courier/test_courier.py`를 pytest 수집 대상에서 빼거나(파일명을 `test_`로 시작하지 않게 바꾸거나 `scripts/conftest.py`의 가림 목록에 추가) 진짜 `def test_...` 함수로 바꾼다.** 한 줄 이유: 지금 구조로는 돌릴 때마다 실제 저장소 파일이 바뀌는데 pytest 성적표에는 전혀 안 잡혀서, 원인 모를 변경이 계속 쌓인다 — 고치기도 쉽고 영향(매 실행마다 발생)도 가장 크다.
2. **[소] 신PC(운영 기기)에서 `python3 -m pytest scripts -q -rf > 실패로그.txt`를 2~3회 받아 실제 실패 테스트 이름 목록을 이 문서에 채운다.** 한 줄 이유: 이 보고서의 모든 가설은 "실제 실패 목록"이 없어 미확인으로 남아 있고, 그 목록 없이는 다음 단계(원인 분류 확정)로 못 넘어간다. 크기는 작지만(명령 하나) 사람이 그 기기에서 직접 돌려야 하므로 에이전트 단독으로는 못 끝낸다.
3. **[중] `scripts/ops/`의 운영 스크립트들이 테스트 중에도 실제 운영 경로(`C:\work\_ops` 등)를 기본값으로 쓰는 구조를, 테스트에서는 항상 명시적으로 격리된 경로를 쓰도록 점검표로 만든다**(이번에 추가한 `test_watch.py`·`test_recall.py`처럼 `monkeypatch`로 격리하는 방식을 다른 ops 시험에도 점검). 한 줄 이유: 가설 A가 맞다면 운영 기기에서 테스트와 실제 크론이 같은 파일을 두고 경합할 수 있는 구조 자체를 줄인다.
4. **[대] 2번에서 받은 실제 실패 목록으로 이 보고서의 "원인별 분류"·"흔들리는 이유"를 다시 쓴다.** 한 줄 이유: 지금은 코드 리뷰 기반 가설뿐이라, 실측 없이 더 고치는 건 추측에 추측을 쌓는 것이다 — 우선순위는 높지만 실제 작업량(재분석 전체)이 가장 크다.

## 근거의 한계

- 이 세션에서 0건 실패가 나온 것은 "버그가 없다"는 뜻이 아니라 "이 환경에서는 그 버그가 드러나지 않는다"는 뜻일 수 있다 — 특히 가설 A·B처럼 운영 기기 고유의 상태에 의존하는 문제라면 클라우드 세션은 원천적으로 못 본다.
- CI는 `scripts/ops/tests`만 돌리고 `scripts` 전체를 자동으로 돌리지 않으므로, 이번 분석은 "어쩌다 한 번 수동으로 넓게 돌린 결과"를 사후에 설명하려는 시도다. 재발 방지를 확인할 자동화된 기준선이 없다.
- 비밀값이 의심되는 로그 출력은 없었다(이번 5회 실행 모두 표준 pytest 요약뿐이었고, 민감해 보이는 값은 보지 못했다).
- 원본 코드·시험·설정은 이 분석 과정에서 전혀 고치지 않았다(`scripts/hermes_courier/tstate.json`이 실행마다 바뀐 것은 `git checkout`으로 매번 되돌려 커밋에 포함하지 않았다).
