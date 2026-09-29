"""PreToolUse 훅(2026-09-29 탐, 사장님 승인): 서브에이전트가 브라우저·화면 제어 도구를 부르면 막는다.
이유: 9/29 하이쿠 스트레스 테스트에서 하이쿠가 preview_start·navigate를 잡고 놓지 못해 탐·노트·마야 세션이 함께 멈춤.
문서 규칙(CLAUDE.md 대기형 도구 금지)은 어기면 그만이라 도구 관문에 둔다(CLAUDE#4e7b).
판정: PreToolUse 입력에 agent_id가 있으면 서브에이전트 안에서 부른 것(본 세션은 없음). 본 세션의 브라우저 사용은 그대로 통과.
세션 모델이 하이쿠인 경우(2026-09-29 N80): 입력의 transcript_path 끝부분에서 최근 assistant 메시지의 model을 읽어 판정한다.
한계: 첫 도구 호출 전이라 assistant 기록이 없거나 기록 형식이 바뀌면 통과(fail-open).
파싱 실패는 통과(fail-open): 관문 오류가 모든 세션을 멈추면 안 된다.
"""
import json, sys
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
tool = str(data.get("tool_name") or "")
BLOCKING = ("mcp__Claude_Browser__", "mcp__claude-in-chrome__", "mcp__computer-use__")


def session_model(path):
    """대화 기록(transcript) 끝부분에서 가장 최근 assistant 메시지의 모델 이름을 읽는다. 못 읽으면 빈 문자열."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 262144))
            tail = f.read().decode("utf-8", "ignore").split("\n")
        for line in reversed(tail):
            if '"assistant"' not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue  # 잘린 첫 줄 등
            if obj.get("type") == "assistant":
                m = (obj.get("message") or {}).get("model")
                if m:
                    return str(m)
    except Exception:
        pass
    return ""


if tool.startswith(BLOCKING):
    who = ""
    if data.get("agent_id"):
        who = "서브에이전트"
    elif "haiku" in session_model(str(data.get("transcript_path") or "")).lower():
        who = "하이쿠 세션(경량 모델)"
    if who:
        sys.stderr.write(
            f"[대기형 도구 관문] {who}는 {tool}을(를) 쓸 수 없습니다(세션 제어권을 붙잡아 다른 세션까지 멈춘 사고, 2026-09-29). "
            "웹·API 검증은 `curl -m 30` 또는 헤드리스 스크립트(타임아웃 30초)로 하고, 화면 조작이 꼭 필요하면 "
            "하던 일을 멈추고 부모 세션(사장님)에 그 사실을 보고하세요.")
        sys.exit(2)
sys.exit(0)
