"""PreToolUse 훅(2026-10-20 노트, 사장님 지시): 에이전트끼리의 세션 메시지(SendMessage, 앱 도구 mcp__ccd_session_mgmt__send_message)는 보낼 때마다 사장님 승인이 있을 때만 쓴다(장애 예외 없음, 2026-10-20 개정).
규칙: 받는 쪽이 다른 로컬 세션(local_...) 또는 페르소나 이름이면, 이 대화의 최근 120분 안에 사장님이 직접 쓴 글 중
'세션메시지/세션 메시지'를 말하며 승인하는 문구가 있어야 통과한다. 서브에이전트에게 보내는 SendMessage는 대상이 아니다.
시스템 알림·도구 결과·다른 세션의 전달은 사람 입력이 아니다(승인으로 안 친다). 입력 파싱 실패는 통과(fail-open).
대상인데 대화 기록을 못 읽으면 막는다(안전 우선). 정본 규칙: 공정 카드 노트 #121(카빗DM 우선 도그푸딩)."""
import datetime
import json
import re
import sys

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PERSONAS = {"지투", "탐", "노트", "마야", "핏", "북", "폴", "덱스", "비티", "페이브", "타미"}
APPROVE = re.compile(r"승인|써도|써라|보내|허용|오케이|ㅇㅋ|\bok\b|진행")
TOPIC = re.compile(r"세션\s*메시지")
NOT_HUMAN = ("SYSTEM NOTIFICATION", "<system-reminder>", "<task-notification>", "<wake reason",
             "Stop hook feedback", "<cross-session-message", "<side-sessions-event>")
WINDOW_MIN = 120


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def is_tool_result(content):
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def targeted(to):
    to = (to or "").strip()
    return to.startswith("local_") or to in PERSONAS or to.startswith("uds:")


def block(msg):
    sys.stderr.write("[세션메시지 관문] " + msg + "\n")
    sys.exit(2)


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        sys.exit(0)
    ti = data.get("tool_input") or {}
    tool = data.get("tool_name")
    to = str(ti.get("to") or ti.get("session_id") or "")
    if tool not in ("SendMessage", "mcp__ccd_session_mgmt__send_message") or not targeted(to):
        sys.exit(0)
    try:
        rows = [json.loads(l) for l in open(data["transcript_path"], encoding="utf-8") if l.strip()]
    except Exception:
        block("대화 기록을 읽지 못해 승인 여부를 확인할 수 없습니다. 카빗DM(dm_send)을 쓰거나, 사장님께 알리고 승인을 받으세요.")
    now = datetime.datetime.now(datetime.timezone.utc)
    for r in reversed(rows):
        m = r.get("message") or {}
        if not ((r.get("type") == "user" or m.get("role") == "user") and not is_tool_result(m.get("content"))):
            continue
        t = text_of(m.get("content"))
        if not t.strip() or any(k in t for k in NOT_HUMAN):
            continue
        if not (TOPIC.search(t) and APPROVE.search(t)):
            continue
        ts = r.get("timestamp")
        try:
            when = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if (now - when).total_seconds() > WINDOW_MIN * 60:
                continue
        except Exception:
            pass  # 시각을 못 읽으면 문구만 본다
        sys.exit(0)
    block("에이전트끼리 세션 메시지는 사장님 승인이 있어야 쓸 수 있습니다(사장님 2026-10-20, 장애 예외 없음). "
          "먼저 카빗DM(dm_send)으로 보내세요. 꼭 세션 메시지가 필요하면 사장님께 알리고 '세션메시지 사용 승인'을 받은 뒤 다시 시도하세요(승인은 120분간 유효).")


main()
