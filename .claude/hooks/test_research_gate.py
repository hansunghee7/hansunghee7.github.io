"""research-gate.py 시험: python .claude/hooks/test_research_gate.py"""
import json, subprocess, sys
from pathlib import Path
H = Path(__file__).with_name("research-gate.py")
def run(tool, sub, prompt):
    p = subprocess.run([sys.executable, str(H)], input=json.dumps({"tool_name": tool, "tool_input": {"subagent_type": sub, "prompt": prompt}}).encode("utf-8"), capture_output=True)
    return p.returncode
cases = [
    ("collector는 막음", ("Agent", "collector", "PIN 정책 자료 수집"), 2),
    ("일반 에이전트의 리서치는 막음", ("Agent", "general-purpose", "구글 PIN 벤치마킹 해 줘"), 2),
    ("예외 표시가 있으면 통과", ("Agent", "collector", "[제미나이 불가: 로그인 페이지] 수집"), 0),
    ("코드 탐색은 통과", ("Agent", "explorer", "background.js에서 store 찾기"), 0),
    ("다른 도구는 통과", ("Bash", "", "리서치"), 0),
]
bad = [n for n, a, want in cases if run(*a) != want]
print("통과" if not bad else "실패: " + ", ".join(bad), f"({len(cases) - len(bad)}/{len(cases)})")
sys.exit(1 if bad else 0)
