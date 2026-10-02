"""PreToolUse(mcp__saegim__cite) 훅(2026-10-02 탐, F1 판정 E3): cite의 note가 `[`로 시작하지 않으면 막는다.
이유: 페르소나별 새김 실사용 집계에 구분자가 필요하다(CLAUDE.md id:b6d2). 형식은 `[탐] 무엇을 반영했는지`.
파싱 실패, note 입력 자체가 없는 경우는 통과(fail-open)."""
import json, sys
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
ti = data.get("tool_input") or {}
if "note" in ti and not str(ti.get("note") or "").lstrip().startswith("["):
    sys.stderr.write(
        "[cite note 관문] cite의 note는 `[페르소나명] 내용`으로 시작해야 합니다(예: `[탐] 보고 첫 화면 문구에 반영`). "
        "페르소나별 새김 사용을 집계하는 구분자입니다. 고쳐서 다시 호출하세요.")
    sys.exit(2)
sys.exit(0)
