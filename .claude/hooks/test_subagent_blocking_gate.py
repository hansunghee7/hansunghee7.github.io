"""subagent-blocking-gate.py 시험: python .claude/hooks/test_subagent_blocking_gate.py"""
import json, subprocess, sys
from pathlib import Path
H = Path(__file__).with_name("subagent-blocking-gate.py")
def run(payload):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True).returncode
cases = [
    ("서브에이전트의 preview_start는 막음", {"tool_name": "mcp__Claude_Browser__preview_start", "agent_id": "a1"}, 2),
    ("서브에이전트의 navigate는 막음", {"tool_name": "mcp__Claude_Browser__navigate", "agent_id": "a1"}, 2),
    ("서브에이전트의 Chrome 도구는 막음", {"tool_name": "mcp__claude-in-chrome__navigate", "agent_id": "a1"}, 2),
    ("서브에이전트의 화면 제어는 막음", {"tool_name": "mcp__computer-use__left_click", "agent_id": "a1"}, 2),
    ("본 세션의 브라우저는 통과", {"tool_name": "mcp__Claude_Browser__navigate"}, 0),
    ("서브에이전트의 Bash는 통과", {"tool_name": "Bash", "agent_id": "a1"}, 0),
    ("깨진 입력은 통과", b"not json", 0),
]
bad = [n for n, p, want in cases if run(p) != want]
print("통과" if not bad else "실패: " + ", ".join(bad), f"({len(cases) - len(bad)}/{len(cases)})")
sys.exit(1 if bad else 0)
