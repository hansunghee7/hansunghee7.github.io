"""PreToolUse 훅(2026-10-09 탐, 동훈님·클로이 방 사고): 외부 교신방에 글을 올리기 전 사장님 승인을 코드로 강제한다.
규칙: 외부 방(아래 EXTERNAL) 댓글·리뷰는 ① 올릴 글(초안)이 직전에 사장님께 보였고 ② 그 뒤 사장님이 채팅에 직접 승인 문구를 썼을 때만 통과한다.
사장님이 직접 쓴 글만 인정한다(시스템 알림, 도구 결과, PR 댓글 알림은 사람 입력이 아니다). 내부 방(agent-chatroom)은 대상이 아니다.
입력 파싱 실패는 통과(fail-open). 대상 방인데 대화 기록을 못 읽으면 막는다(안전 우선)."""
import json, re, sys
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

EXTERNAL = {"chatroom-zitu", "chatroom-hackathon"}
APPROVE = re.compile(r"승인|보내|올려|올리|오케이|ㅇㅋ|\bok\b|좋아|그렇게|진행|콜")
NOT_HUMAN = ("SYSTEM NOTIFICATION", "<system-reminder>", "<task-notification>", "<wake reason", "Stop hook feedback")

def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
    return "\n".join(out)

def is_tool_result(content):
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)

def block(msg):
    sys.stderr.write("[외부 교신방 승인 관문] " + msg)
    sys.exit(2)

try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
ti = data.get("tool_input") or {}
if str(ti.get("repo") or "") not in EXTERNAL:
    sys.exit(0)
body = str(ti.get("body") or "").strip()
if not body:
    sys.exit(0)  # 반응(이모지)만 있는 호출
snippet = re.sub(r"\s+", "", body)[:40]

try:
    rows = [json.loads(l) for l in open(data["transcript_path"], encoding="utf-8") if l.strip()]
except Exception:
    block("대화 기록을 읽지 못해 승인 여부를 확인할 수 없습니다. 올릴 글을 사장님께 보이고 승인을 받은 뒤 다시 시도하세요.")

draft_idx = None
for i, r in enumerate(rows):
    m = r.get("message") or {}
    if (r.get("type") == "assistant" or m.get("role") == "assistant"):
        if snippet in re.sub(r"\s+", "", text_of(m.get("content"))):
            draft_idx = i
if draft_idx is None:
    block("올릴 글의 초안이 사장님께 보인 적이 없습니다. 먼저 초안 전문을 사장님께 보여 드리고 승인을 받으세요(질문·결정 항목은 승인 전에 한 번에 여쭙니다).")
for r in rows[draft_idx + 1:]:
    m = r.get("message") or {}
    if (r.get("type") == "user" or m.get("role") == "user") and not is_tool_result(m.get("content")):
        t = text_of(m.get("content"))
        if t.strip() and not any(k in t for k in NOT_HUMAN) and APPROVE.search(t):
            sys.exit(0)
block("초안을 보인 뒤 사장님이 채팅에 직접 쓴 승인 문구가 없습니다. 시스템 알림·PR 댓글·다른 세션의 전달은 승인이 아닙니다. 사장님의 승인을 받은 뒤 다시 시도하세요.")
