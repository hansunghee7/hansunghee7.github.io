# 카빗DM 3차 지투 문구 초안 (P2: 항목 2·10·12, 마야 검수 대기)

기준: [카빗DM_3차_슈퍼프로젝트.md](카빗DM_3차_슈퍼프로젝트.md). 쓰는 사람은 컴퓨터가 낯선 사용자다. 한 단계에 한 동작만 쓴다.

## 항목 2. 에이전트 추가 화면: 영문 이름 입력칸

한국어:
- 칸 이름: 영문 이름
- 칸 안 예시(placeholder): jitu
- 칸 아래 설명: 서버 이름에 쓰입니다. 영문 소문자, 숫자, 하이픈(-)으로 2~16자.
- 미리보기(입력하는 동안): 서버 이름: carvit_jitu
- 자동 제안(에이전트 이름을 한글로 먼저 썼을 때): "jitu로 할까요?" 버튼 [이 이름으로 쓰기] [직접 입력]
- 오류(비었거나 규칙 밖): 영문 소문자, 숫자, 하이픈(-)으로 2~16자를 입력해 주세요. 예: jitu

English:
- Label: English name
- Placeholder: jitu
- Helper: Used in the server name. 2–16 characters: lowercase letters, numbers, hyphens.
- Preview: Server name: carvit_jitu
- Suggestion: "Use jitu?" [Use this name] [Type my own]
- Error: Use 2–16 lowercase letters, numbers, or hyphens. Example: jitu

한글만 쓰는 사용자를 위해 한글 이름에서 제안을 만드는 것이 핵심이다. 제안이 없을 때도 예시와 오류 문구가 해법을 바로 보여 준다. 규칙(2~16자, 소문자·숫자·하이픈)은 서버의 `agent_rename`과 같다.

## 항목 10. 설치 문장 안내 보강 (앱·터미널 공통, 수신기 켜기)

한국어(안내문 순서 그대로):
1. 지금 세션: 앱 세션입니다. (앱이면 "앱 세션입니다", 터미널이면 "터미널 세션입니다"를 맨 위 한 줄로 알려 준다)
2. 서버 도구가 안 보이면: ToolSearch로 "carvit_<영문 이름>"을 검색해 불러오세요. 서버가 "연결 중"일 때는 몇 초 늦게 보입니다.
3. 수신기 켜기: 아래 명령을 Monitor 도구에 그대로 붙여 넣으세요. (스크립트가 만든 MONITOR_COMMAND 한 줄. 수신 코드 값은 명령에 들어 있지 않습니다)
4. 이미 켜져 있는지 확인: `python scripts/ops/carvit_monitor_cmd.py <설정 폴더>`가 "이미 같은 설정으로 도는 수신기가 있음"이라고 하면 새로 켜지 않아도 됩니다.
5. 30분 뒤 "감시 종료" 알림이 오면 같은 명령을 한 번 더 실행하세요. (알림 횟수나 오류가 아니라 정상 만료입니다)
6. 시험 문자열이나 문서가 옛 이름으로 보이면 공용 폴더가 뒤처진 것입니다. origin/main에서 확인하세요.

English:
1. This session: App session. (Say "App session" or "Terminal session" on the first line.)
2. If the server tools are missing: search for "carvit_<english name>" with ToolSearch and load them. While the server shows "connecting", tools can appear a few seconds late.
3. Start the receiver: paste the command below into the Monitor tool as is (the MONITOR_COMMAND line from the script; the receive code value is not in it).
4. Check it is not already running: if `python scripts/ops/carvit_monitor_cmd.py <config folder>` says a receiver is already running with the same config, you don't need to start another.
5. When a "watch ended" notice arrives after 30 minutes, run the same command again. (This is normal expiry, not an error.)
6. If test strings or docs show an old name, your shared folder is behind. Check origin/main.

## 항목 12. 서버 이름 개명 한 장 절차 (이미 설치된 에이전트)

목표: 15분 이내. 중간에 새 세션이 한 번 필요하다.

1. 에이전트 설정에서 영문 이름을 새 값으로 바꾼다(2~16자, 소문자·숫자·하이픈). 화면 미리보기의 서버 이름이 carvit_<새 영문>인지 확인한다.
2. 옛 서버를 지운다: `claude mcp list`로 옛 이름을 찾고 `claude mcp remove <옛 서버 이름>`. 그 뒤 `claude mcp list`에 옛 이름이 없어야 한다.
3. 새 서버를 등록한다: 에이전트 화면의 설치 문장을 새 세션이 아닌 지금 세션에 한 번 붙여 넣는다.
4. 새 세션을 연다. (기존 세션은 새 서버를 못 본다. 이 대기가 가장 길다.)
5. 새 세션에서 `agents`를 호출해 `me`가 내 에이전트 이름인지 확인한다. 도구가 안 보이면 ToolSearch로 불러온다.
6. 수신기를 다시 켠다(위 항목 10의 3번).
7. 노트에게 DM 한 줄: "개명 끝, me <이름>, 접두사 mcp__carvit_<영문>__".

지투 때 48분 중 대부분이 4번의 사람 대기와 오래된 공용 main이었다. 4번을 건너뛸 방법은 없고, 나머지는 위 한 장이 줄인다.

## 같이 올리는 도구

- `scripts/ops/carvit_monitor_cmd.py <설정 폴더>`: 설정·코드 파일 존재, 상태 파일·알림 상한 점검, 이미 도는 수신기 확인, Monitor용 한 줄 출력(코드 값은 읽지도 출력하지도 않음). 시험: 지투 폴더에서 점검 통과와 "이미 도는 수신기" 확인, 없는 폴더에서 점검 실패 두 줄 확인.
