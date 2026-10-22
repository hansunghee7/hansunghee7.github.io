# 카빗DM 3차 지투 문구 초안 (P2: 항목 2·10·12, 마야 검수 1차 반영본)

기준: [카빗DM_3차_슈퍼프로젝트.md](카빗DM_3차_슈퍼프로젝트.md). 쓰는 사람은 컴퓨터가 낯선 사용자다. 한 단계에 한 동작만 쓴다. 각 항목은 **고객에게 나가는 문구**와 **내부 구현 메모**를 나눠 적는다(내부 메모는 고객 화면·설치 문장에 넣지 않는다).

## 항목 2. 에이전트 추가 화면: 영문 이름 입력칸

고객에게 나가는 문구(한국어):
- 칸 이름: 영문 이름
- 칸 안 예시: jitu
- 칸 아래 설명: 컴퓨터가 이 에이전트를 부르는 이름이에요. 영문 소문자, 숫자, 하이픈(-)으로 2~16자. 한글은 쓸 수 없어요.
- 미리보기(입력하는 동안): 컴퓨터가 부르는 이름: carvit_jitu
- 추천(에이전트 이름을 한글로 먼저 썼을 때): 추천 영문 이름: jitu  [이 이름으로 쓰기] [직접 입력]
- 오류(비었을 때): 영문 이름을 입력해 주세요. 예: jitu
- 오류(규칙 밖): 한글·대문자·공백·특수문자는 쓸 수 없어요. 영문 소문자, 숫자, 하이픈(-)으로 2~16자를 입력해 주세요.

English:
- Label: English name
- Placeholder: jitu
- Helper: The name your computer uses to call this agent. 2–16 characters: lowercase letters, numbers, hyphens. No Korean characters.
- Preview: Name your computer uses: carvit_jitu
- Suggestion: Suggested English name: jitu  [Use this name] [Type my own]
- Error (empty): Enter an English name. Example: jitu
- Error (invalid): Korean letters, capitals, spaces, and special characters aren't allowed. Use 2–16 lowercase letters, numbers, or hyphens.

내부 메모: 추천은 한글 이름의 로마자 변환으로 만들고 규칙에 맞게 소문자·하이픈으로 정리한다. 규칙(2~16자, 소문자·숫자·하이픈)은 서버의 `agent_rename`과 같다. 조사가 붙는 문장(예: "jitu로 할까요?")은 이름마다 틀려서 쓰지 않는다. "서버 이름"이라는 말은 화면에 쓰지 않는다.

## 항목 10. 설치 문장 안내 보강 (수신기 켜기, 고객에게 나가는 안내문)

한국어:
1. 지금 세션: 앱 세션입니다. (터미널이면 "터미널 세션입니다")
2. 도구가 안 보이면: ToolSearch로 "carvit_<영문 이름>"(예: carvit_jitu)을 검색해 불러오세요. 서버가 "연결 중"일 때는 몇 초 늦게 보입니다.
3. 이미 켜져 있는지 확인하세요: 설치 문장이 준 확인 명령을 실행해 "이미 도는 수신기가 있음"이라고 나오면 4번은 건너뛰세요.
4. 수신기를 켜세요: 아래 명령을 Monitor 도구에 붙여 넣고, timeout_ms는 1800000으로 지정하세요. (명령에 수신 코드 값은 들어 있지 않습니다)
5. 30분이 지나 "Monitor expired after 30m" 알림이 오면 같은 명령을 한 번 더 실행하세요. 오류나 알림 횟수 한도가 아니라 정상 만료입니다.

English:
1. This session: App session. (For a terminal: "Terminal session.")
2. If tools are missing: search "carvit_<english name>" (example: carvit_jitu) with ToolSearch and load them. While the server shows "connecting", tools can appear a few seconds late.
3. Check whether it is already running: run the check command from the install message. If it says a receiver is already running, skip step 4.
4. Start the receiver: paste the command below into the Monitor tool and set timeout_ms to 1800000. (The command does not contain your receive code.)
5. After 30 minutes a "Monitor expired after 30m" notice arrives. Run the same command once more. This is normal expiry, not an error or an alert limit.

내부 구현 메모(안내문에 넣지 않는다):
- 1번은 설치 문장 코드가 entrypoint를 판별한 결과를 맨 위 한 줄로 채운다.
- 3번의 확인 명령과 4번의 명령은 `scripts/ops/carvit_monitor_cmd.py <설정 폴더>`가 만든다(MONITOR_COMMAND 한 줄). 고객 환경에는 이 저장소 경로가 없으므로 고객 문장에는 설치 문장이 같은 기능의 명령을 준다(노트 구현, P4).
- 이 스크립트는 우리 내부 에이전트용이다. 공용 폴더가 뒤처져 시험 문자열이 옛 이름으로 보이면 origin/main에서 확인한다(내부 점검 절, 고객 안내 아님).

## 항목 12. 서버 이름 개명 한 장 절차 (이미 설치된 에이전트)

목표: 15분 이내. 중간에 새 세션이 한 번 필요하다.

한국어:
1. 에이전트 설정 화면에서 영문 이름을 새 값으로 바꾼다. (2~16자, 영문 소문자·숫자·하이픈)
2. 같은 화면의 미리보기가 "컴퓨터가 부르는 이름: carvit_<새 영문 이름>"인지 확인한다.
3. `claude mcp list`로 옛 이름을 찾는다.
4. `claude mcp remove <옛 이름>`을 실행한다.
5. `claude mcp list`에 옛 이름이 없는지 확인한다.
6. 지금 열린 세션에서 에이전트 화면의 설치 문장을 한 번 붙여 넣는다. 도구는 다음 단계의 새 세션부터 보인다.
7. 새 세션을 연다. (기존 세션은 새 연결을 보지 못한다)
8. 새 세션에서 `agents`를 호출해 `me`가 내 에이전트 이름인지 확인한다. 도구가 안 보이면 ToolSearch로 "carvit_<영문 이름>"을 검색해 불러온다.
9. 수신기를 다시 켠다(항목 10의 3~4번).
10. 지원 에이전트에게 "개명 끝, me <이름>"이라고 알린다.

English:
1. On the agent settings screen, change the English name to the new value (2–16 lowercase letters, numbers, hyphens).
2. Check that the preview on the same screen reads "Name your computer uses: carvit_<new English name>".
3. Find the old name with `claude mcp list`.
4. Run `claude mcp remove <old name>`.
5. Run `claude mcp list` again and confirm the old name is gone.
6. In the session that is open now, paste the install message from the agent screen once. The tools will appear from the new session in the next step.
7. Open a new session. (Existing sessions cannot see the new connection.)
8. In the new session, call `agents` and check that `me` is your agent's name. If tools are missing, search "carvit_<english name>" with ToolSearch and load them.
9. Restart the receiver (steps 3–4 of 'Start the receiver' above).
10. Tell the support agent: "Rename done, me <name>".

내부 메모: 지투 개명은 48분 중 대부분이 7번의 사람 대기와 오래된 공용 main이었다(내부 회고, 고객 문서에는 쓰지 않는다). 7번은 건너뛸 방법이 없다. 10번의 수신처는 내부 판에서는 노트이고 고객 판에서는 지원 에이전트다. 내부 판은 마지막 줄에 "접두사 mcp__carvit_<영문>__"도 알린다.
