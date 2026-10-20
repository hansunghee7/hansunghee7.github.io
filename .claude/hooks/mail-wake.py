"""PostToolUse 훅(2026-09-25 탐, 사장님 승인 "세가지 적용"): mailbox.py send를 실행하면 보낸 쪽에게
"받는 세션이 떠 있으면 세션 메시지로도 깨우라"를 띄운다.
이유: 우편은 받는 쪽이 새 세션을 열 때만 읽혀서, 떠 있는 세션은 우편만으로 다음 행동을 못 한다
(9/25 지투 → 노트 v2 전환 알림이 5시간 떠 있던 노트 세션에 닿지 않은 사고). 근거 CLAUDE.md id:98ae.
"""
import json, re, sys

try:  # 윈도우 기본 인코딩(cp949)으로 읽으면 한글 이름이 깨진다(9/25 실측) -> 바이트를 UTF-8로 직접 푼다
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
cmd = str((data.get("tool_input") or {}).get("command", ""))
m = re.search(r"mailbox\.py\"?'?\s+send\s+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
if not m:
    sys.exit(0)
to = m.group(1).strip("\"'")
if to in ("전체", "사장님"):
    sys.exit(0)
msg = (f"[우편 알림 규칙] '{to}'에게 우편을 보냈습니다. 에이전트 간 연락은 카빗DM(dm_send)이 기본이고 우편은 카빗DM에 등록되지 않은 에이전트에게만 씁니다. "
       "세션 메시지(SendMessage·send_message)는 사장님 승인을 받은 뒤에만 보낼 수 있습니다. 회신이 필요하면 내 업무대장에 '확인필요'로 올려 두세요.")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
