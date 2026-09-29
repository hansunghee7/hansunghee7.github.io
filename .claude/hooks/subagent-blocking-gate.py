"""PreToolUse 훅(2026-09-29 탐, 사장님 승인): 서브에이전트가 브라우저·화면 제어 도구를 부르면 막는다.
이유: 9/29 하이쿠 스트레스 테스트에서 하이쿠가 preview_start·navigate를 잡고 놓지 못해 탐·노트·마야 세션이 함께 멈춤.
문서 규칙(CLAUDE.md 대기형 도구 금지)은 어기면 그만이라 도구 관문에 둔다(CLAUDE#4e7b).
판정: PreToolUse 입력에 agent_id가 있으면 서브에이전트 안에서 부른 것(본 세션은 없음). 본 세션의 브라우저 사용은 그대로 통과.
못 막는 것: 하이쿠를 본 세션 모델로 직접 띄운 경우(입력에 모델 정보가 없어 판별 불가).
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
if data.get("agent_id") and tool.startswith(BLOCKING):
    sys.stderr.write(
        f"[대기형 도구 관문] 서브에이전트는 {tool}을(를) 쓸 수 없습니다(세션 제어권을 붙잡아 다른 세션까지 멈춘 사고, 2026-09-29). "
        "웹·API 검증은 `curl -m 30` 또는 헤드리스 스크립트(타임아웃 30초)로 하고, 화면 조작이 꼭 필요하면 "
        "하던 일을 멈추고 부모 세션에 그 사실을 보고하세요.")
    sys.exit(2)
sys.exit(0)
