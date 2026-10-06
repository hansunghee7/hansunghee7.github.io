# scripts pytest 기존 실패 원인 분석 (2026-10-07)

**결론: 환경에 따라 결과가 다르다 — CI(GitHub Actions, 리눅스)와 이 클라우드 세션(리눅스)에서는 `python3 -m pytest scripts -q`가 5회 모두 0건 실패(345 passed, 1 xfailed)로 통과하지만, 로컬 Windows 환경에서 실측하면(사장님 제공, 2회 동일) 31 failed / 314 passed로 반복 실패한다. 내역은 `test_scheduled_publish` 15건·`pending_detector` 9건·`test_card` 7건이고 샘플 원인은 cp949 `UnicodeDecodeError`다 — 즉 "재현 불가"가 아니라 "리눅스에서는 통과, 윈도우에서는 인코딩 관련으로 재현되는 실패"로 정정한다. 이 세션은 Windows 환경 자체에 접근할 수 없어 사장님이 전달한 수치를 그대로 인용했고, 직접 재실행해 검증하지는 못했다.**

## 실행 방법과 회차별 결과

### 이 세션이 직접 실행한 것: 클라우드(리눅스) 환경

환경: 이 클라우드 세션(Linux, Python 3.13.16, pytest 9.1.1), 저장소 커밋 `440af1079`(2026-10-07, PR #2019 병합 직후). 매 회차 `timeout 300 python3 -m pytest scripts -q`로 실행했고, 어느 회차도 타임아웃에 걸리지 않았다(모두 10~12초 안에 끝남).

| 회차 | 결과 | 걸린 시간 |
|---|---|---|
| 1 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.71s |
| 2 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.29s |
| 3 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.37s |
| 4 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 10.45s |
| 5 | 345 passed, 1 xfailed, 52 subtests passed, 0 failed | 11.00s |

`--collect-only`로는 346개 항목(345 + xfail 1건)이 잡힌다. 5회 모두 토씨 하나 안 틀리고 0건 실패였다. xfail 1건(`test_ask_vertex_fallback.py::GeneralException::test_token_issuing_exception_falls_back_to_free`)은 의도된 표시라 이번 분석 대상이 아니다.

CI(`build-check.yml`)도 같은 리눅스 계열이고, 실제로 `python3 -m pytest scripts/ops/tests -q`만 자동 실행한다(`scripts` 전체를 겨냥한 자동 실행은 없음). PR #2020에서 이 보고서를 올렸을 때 CI의 `build` 체크는 통과(success)했다 — CI 쪽도 리눅스에서는 실패가 없다는 것과 일치한다.

### 사장님이 제공한 실측: 로컬 Windows 환경 (이 세션이 직접 돌리지 않음)

| 회차 | 결과 |
|---|---|
| 1 | 31 failed / 314 passed |
| 2 | 31 failed / 314 passed (1회차와 동일) |

내역(사장님 제공): `test_scheduled_publish` 15건, `pending_detector` 9건, `test_card` 7건 = 31건. 샘플 원인: cp949 `UnicodeDecodeError`. 이 수치는 이 세션이 직접 실행해 확인한 것이 아니라 지시문으로 전달받은 결과를 그대로 인용한 것이다 — 어떤 python 버전·로캘·실행 명령으로 쟀는지, 어느 커밋에서 쟀는지는 **미확인**이다.

314 + 31 = 345로, 이 세션의 리눅스 결과(345 passed, 그 외 1 xfailed = 346)와 전체 개수가 사실상 같다(xfail 1건 정도 차이). 애초 배경 설명에 있던 "277 통과·31 실패(308건)"와는 전체 개수부터 다르다 — "277"쪽은 더 이전 커밋에서 잰 것으로 보이고, 이번에 받은 "314+31=345"는 지금 커밋(또는 그와 테스트 개수가 같은 시점)과 맞아떨어진다. 정확히 어느 커밋인지는 **미확인**.

## 원인별 분류

리눅스(CI·클라우드 세션)에서는 실패가 0건이라 이 세션이 직접 실패를 분류할 수는 없었다. 대신 ⓐ 사장님이 제공한 Windows 실측(실제 실패 목록 일부 포함)과 ⓑ 코드를 읽어 찾은 위험 패턴을 구분해 적는다.

**ⓐ 환경 의존 경로·인코딩 — Windows에서 확인됨(사장님 제공), 3개 파일·31건**
- `test_scheduled_publish`(15건), `pending_detector`(9건), `test_card`(7건)에서 cp949 `UnicodeDecodeError`가 샘플 원인으로 보고됐다. cp949는 한국어 Windows의 기본 콘솔/파일 인코딩이고, 리눅스는 기본이 UTF-8이다 — 이 세 파일이 공통으로 `subprocess.run(...)`으로 자식 프로세스를 띄우거나 파일을 읽는 지점에서, 인코딩을 명시하지 않은 경로가 있으면 Windows에서만 cp949로 디코드를 시도하다 깨질 수 있다. **확인한 것**: 세 파일명·건수·에러 종류(사장님 제공). **미확인**: 31건 각각의 정확한 줄 번호·어느 subprocess 호출인지·세 파일 모두가 전부 같은 cp949 원인인지(사장님은 "샘플 원인"이라고만 했음, 전수는 아님).

**ⓑ 모듈 수집 중 최상위 코드 부작용 + 시험 간 상태 공유(실제 파일) — 리눅스에서 직접 재현·확인, 1개 파일**
- `scripts/hermes_courier/test_courier.py`: `def test_...` 함수가 하나도 없다. 파일 맨 위(모듈 최상위)에서 바로 `reset()` → `mail(...)` 여러 번 → `run()`(실제 `subprocess.run`으로 `mailbox_courier.py` 실행)을 호출하고 `check()`가 그 결과를 `print()`만 한다. pytest는 이 파일에서 "수집할 테스트가 0개"라고 보지만, **수집(import)하는 것만으로** 저장소의 실제 파일 `scripts/hermes_courier/tstate.json`을 덮어쓴다. `--collect-only`로도 재현됨(아래 "재현 여부" 참고). 이건 31건의 Windows 실패 목록(test_scheduled_publish·pending_detector·test_card)에는 없으므로, Windows 실패의 직접 원인은 아니고 별개의 문제다.
- 같은 폴더의 `scripts/ops/*.py`(`test_denied_notify.py`, `test_inventory_trend.py`, `test_kick_publish.py`, `test_lints.py`, `test_local_llm.py`, `test_night_research.py`)도 구조가 같다. 다만 이쪽은 PR #2018에서 추가된 `scripts/conftest.py`의 `collect_ignore_glob`이 `scripts/ops/` 바로 아래 `test_*.py`를 전부 가려서, 지금의 `pytest scripts`에서는 수집되지 않는다. `scripts/hermes_courier/`, `scripts/hermes_ops/`는 이 가림 목록에 없다.

**ⓒ 시각·날짜 의존(이론상 레이스) — 미확인, 코드만 확인**
- `scripts/ops/tests/test_worklog.py`: `wl.add(...)`를 호출해 내부적으로 기록되는 `source_date`와, 테스트가 그 직후 독립적으로 다시 계산하는 `datetime.now().strftime("%Y-%m-%d")`를 비교하는 자리가 5곳(줄 51, 104, 111, 152, 158). 두 번의 `datetime.now()` 호출 사이에 자정을 넘으면 하루 차이로 실패할 수 있다. Windows 31건 목록에는 `test_worklog`가 없으므로 이번 실패의 원인은 아니다 — 별개의 잠재 위험으로만 남긴다.

**ⓓ 실제(운영) 설정 파일 의존 — 확인함(실패는 아님, 설계상 의도)**
- `scripts/ops/tests/test_jobs_schema.py`는 고정된 픽스처가 아니라 저장소의 실제 운영 파일 `scripts/ops/jobs.toml`·`jobs_goosolar.toml`을 그대로 읽어 스키마를 검사한다(의도된 설계). Windows 31건 목록에는 없다.

**ⓔ 외부 서비스·네트워크 호출 — 코드상 없음을 확인**
- `opsdb`를 참조하는 시험 파일(`test_worklog.py`, `test_recall.py`)은 전부 `mock.patch`/`monkeypatch`로 막혀 있고 실제 네트워크 호출이 없다. `urllib`를 쓰는 `test_ask_vertex_fallback.py`도 `urlopen` 자체를 `mock.patch`로 교체해 실제 요청을 보내지 않는다.

## 재현 여부

- **ⓐ 환경 의존 경로·인코딩(cp949)**: Windows에서는 2회 모두 재현(전체 실행, 사장님 제공). 리눅스에서는 전체 실행 5회·CI 모두 재현 안 됨(통과) — **확인**: 두 OS에서 결과가 정반대로 갈린다는 사실. **미확인**: 단독 실행(파일 하나만 지정)해도 Windows에서 같은 31건이 재현되는지, 이 세션이 Windows에서 직접 단독/전체 실행을 둘 다 돌려본 적은 없다.
- **ⓑ 모듈 수집 부작용**: 리눅스 단독 실행(`pytest scripts/hermes_courier/test_courier.py --collect-only -q`)에서도, 전체 실행(`pytest scripts -q`) 안에서도 둘 다 재현됨(`git diff`로 `tstate.json`의 날짜 키가 실행 때마다 오늘 날짜로 갱신되는 것을 직접 확인). 이 부작용 자체는 pytest의 "failed" 카운트에는 안 잡힌다(테스트 함수가 없어 그냥 0개 수집으로 끝남). Windows에서도 재현되는지는 **미확인**(사장님이 제공한 31건 목록에는 없지만, 수집 시 파일이 바뀌는 부작용 자체는 OS와 무관하게 일어날 것으로 보인다 — 다만 직접 확인은 못 했다).
- **ⓒ·ⓓ·ⓔ**: 리눅스에서 재현되는 실패가 없어 "단독/전체 실행 시 재현 여부" 자체를 확인할 실패 사례가 없었다. 코드 구조상 가능성만 적었다.

## 흔들리는 이유 가설

- 원래 배경 설명은 "31건이 22건으로 흔들린다"였지만, 이번에 사장님이 전달한 Windows 2회 실측은 **둘 다 31건으로 동일**했다 — 적어도 이 두 번 사이에서는 흔들림이 재현되지 않았다. 원래 "22건" 보고가 언제·몇 회 측정한 것인지는 **미확인**이라 이번 결과와 직접 비교할 수 없다.
- **가설 A: 실제 운영 경로·운영 중인 백그라운드 프로세스와의 경합.** `scripts/ops/`의 여러 모듈(`watch.py`, `recall.py`, `session_brief.py`, `review_queue.py`)은 테스트에서 격리되지 않는 한 기본값이 실제 운영 경로(`C:\work\_ops`, `C:\work\hansunghee7.github.io` 등)를 가리키도록 `os.environ.get("OPS_*", 실경로)`로 짜여 있다. 운영 기기(신PC)에서 헤르메스 크론이 동시에 돌고 있었다면 같은 상태 파일을 테스트와 실제 크론이 동시에 건드려 경합이 생길 수 있다 — **확인한 증거**: ⓑ에서 테스트가 실제 공유 파일을 쓰는 것은 직접 봤다. **미확인**: 그 순간 실제로 헤르메스 크론이 같이 돌고 있었는지, Windows 31건(cp949 계열)과 이 경합 가설이 같은 현상인지 다른 현상인지.
- **가설 B(이번 실측으로 사실관계 일부 확인됨): OS 인코딩 차이.** 애초 "환경 패키지·OS 차이"로만 추측했던 것이, 이번 실측으로 "cp949(Windows 기본 인코딩) 관련 `UnicodeDecodeError`"라는 구체적 원인으로 좁혀졌다. **확인**: 세 파일·31건·에러 종류(사장님 제공), 리눅스(CI·클라우드)에서는 재현 안 됨. **미확인**: 31건 전부가 cp949 때문인지(샘플만 그렇다고 들었음), 정확히 어느 줄의 어떤 `subprocess`/`open()` 호출이 인코딩을 안 정했는지.
- **가설 C: 측정 시점의 커밋이 다름.** 애초 배경 설명의 "277+31=308"과 이번 "314+31=345"는 전체 개수부터 다르다 — "277" 쪽이 더 이전 커밋에서 잰 것으로 보인다(이번 "314+31=345"는 이 세션의 리눅스 전체 개수 345~346과 거의 일치). **확인**: 두 번의 배경 설명 간 총 개수가 다르다는 사실 자체. **미확인**: "277" 보고가 정확히 어느 커밋에서 나온 것인지.
- 가설 A·C는 **이 클라우드 세션이 구조적으로 검증할 수 없다**(운영 경로·헤르메스 크론에 접근 불가, 과거 측정 시점의 커밋 기록 없음). 가설 B는 이번 실측으로 "그런 차이가 실재한다"는 것까지는 확인됐지만, cp949가 코드의 어느 지점에서 어떻게 나는지는 이 세션에서 추가로 들여다보지 않았다(보고서 파일 외 다른 파일을 고치지 말라는 이번 지시 범위 밖).

## 권장 수정 순서

1. **[소] `scripts/hermes_courier/test_courier.py`를 pytest 수집 대상에서 뺀다**(파일명을 `test_`로 시작하지 않게 바꾸거나 `scripts/conftest.py`의 가림 목록에 추가하거나, 진짜 `def test_...` 함수로 바꾼다). 한 줄 이유: 지금 구조로는 돌릴 때마다 실제 저장소 파일이 바뀌는데 pytest 성적표에는 전혀 안 잡혀서, 원인 모를 변경이 계속 쌓인다 — 고치기도 쉽고 영향(매 실행마다 발생)도 가장 크다. 단, Windows 31건(cp949)과는 별개 문제이므로 이걸 고쳐도 31건은 그대로 남는다.
2. **[중] 실패 목록을 반영한다.** 이번에 받은 파일 단위 목록(`test_scheduled_publish` 15건, `pending_detector` 9건, `test_card` 7건)은 "어느 파일이 실패하는가"까지는 알려주지만 "그 파일 안의 어느 테스트가, 어느 줄에서, 왜(cp949가 정확히 어디서 터지는지)"는 아직 모른다. Windows 기기에서 `python -m pytest scripts/test_scheduled_publish.py scripts/hermes_ops/test_pending_detector.py scripts/test_card.py -v -rf > 실패로그.txt`처럼 **파일명·줄 단위까지 나오는 로그**를 받아 이 보고서를 갱신한다. 한 줄 이유: 지금은 "cp949로 깨진다"는 범주까지만 알고 정확한 호출부를 모르면 고칠 데를 특정할 수 없다 — 사람이 Windows 기기에서 직접 돌려야 해서 에이전트 단독으로는 못 끝낸다.
3. **[대] 운영 경로를 격리한 뒤 원인을 재분류한다.** 2번의 상세 로그를 받으면, ⓐ(cp949) 각 실패가 정말 인코딩 문제인지 아니면 ⓐ 말고 가설 A(운영 경로·크론 경합)까지 겹친 것인지 다시 나눠야 한다 — 이번 보고서의 ⓐ~ⓔ 분류와 "흔들리는 이유" 가설 A·B·C를 실제 로그 기준으로 다시 쓴다. `scripts/ops/`가 테스트 중에도 실제 운영 경로(`C:\work\_ops` 등)를 기본값으로 쓰는 구조를, 테스트에서는 항상 명시적으로 격리된 경로를 쓰도록(이번에 추가한 `test_watch.py`·`test_recall.py`의 `monkeypatch` 방식처럼) 점검표로 만드는 작업도 포함한다. 한 줄 이유: 지금은 파일명 3개·샘플 원인 1개뿐이라, 상세 로그와 경로 격리 없이 더 깊이 고치는 건 추측에 추측을 쌓는 것이다 — 우선순위는 높지만 실제 작업량(상세 로그 확보 + 재분석 + 격리 점검)이 가장 크다.

## 근거의 한계

- 이 세션은 Windows 환경 자체를 실행할 수 없다. "31 failed / 314 passed", 파일별 건수(15/9/7), "cp949 UnicodeDecodeError"는 전부 사장님이 전달한 내용을 그대로 옮긴 것이고, 이 세션이 독립적으로 재현·검증하지 못했다.
- Windows 쪽의 정확한 Python 버전, 로캘(지역) 설정, 실행에 쓴 정확한 명령, 측정한 커밋 해시는 **미확인**이다.
- 31건 각각의 정확한 테스트 이름·줄 번호·트레이스백은 받지 못했다 — 파일 단위 건수와 "샘플 원인" 한 가지만 안다.
- CI는 `scripts/ops/tests`만 돌리고 `scripts` 전체를 자동으로 돌리지 않으므로, 이번 분석의 리눅스 쪽 "0건 실패"는 이 세션이 수동으로 넓게 돌린 결과이지 CI가 매번 보장하는 범위가 아니다.
- 비밀값이 의심되는 로그 출력은 이 세션이 직접 실행한 리눅스 결과에서는 없었다(표준 pytest 요약뿐). Windows 쪽 로그는 이 세션이 보지 못했으므로 비밀값 포함 여부도 **미확인**이다.
- 원본 코드·시험·설정은 이 보고서 수정 과정에서 전혀 고치지 않았다(`scripts/hermes_courier/tstate.json`이 실행마다 바뀐 것은 `git checkout`으로 매번 되돌려 커밋에 포함하지 않았다).
