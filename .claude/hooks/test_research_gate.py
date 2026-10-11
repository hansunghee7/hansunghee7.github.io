"""research-gate.py 시험: python .claude/hooks/test_research_gate.py"""
import json, subprocess, sys
from pathlib import Path
H = Path(__file__).with_name("research-gate.py")
def run(tool, sub, prompt, want_text=None):
    p = subprocess.run([sys.executable, str(H)], input=json.dumps({"tool_name": tool, "tool_input": {"subagent_type": sub, "prompt": prompt, "command": prompt}}).encode("utf-8"), capture_output=True)
    if want_text is not None and want_text not in p.stderr.decode('utf-8', 'ignore'):
        return -1
    return p.returncode
cases = [
    ("collector는 막음", ("Agent", "collector", "PIN 정책 자료 수집"), 2),
    ("일반 에이전트의 리서치는 막음", ("Agent", "general-purpose", "구글 PIN 벤치마킹 해 줘"), 2),
    ("예외 표시가 있으면 통과", ("Agent", "collector", "[제미나이 불가: 로그인 페이지] 수집"), 0),
    ("코드 탐색은 통과", ("Agent", "explorer", "background.js에서 store 찾기"), 0),
    ("다른 도구는 통과", ("Bash", "", "리서치"), 0),
    ("도구 밖 검색 연동 호출은 막음", ("Bash", "", "python -c \"body={'tools':[{'google_search':{}}]}\""), 2),
    ("vertex_research.py는 통과", ("Bash", "", "python C:/work/_ops/tools/vertex_research.py --topic x a b"), 0),
    ("저장소판 vertex_research.py도 통과", ("Bash", "", "python scripts/ops/vertex_research.py --topic x a b"), 0),
    ("Agent 안내에 정본 순서(검색 전용 키)", ("Agent", "collector", "자료 수집", "검색 전용 키"), 2),
    ("Bash 안내에 정본 순서(검색 전용 키)", ("Bash", "", "python -c \"g='googleSearch'\"", "검색 전용 키"), 2),
    ("안내에 옛 문구(무료 체험 크레딧) 없음", ("Agent", "collector", "자료 수집", "무료 체험 크레딧"), -1),
]
bad = [n for n, a, want in cases if run(*a) != want]
print("통과" if not bad else "실패: " + ", ".join(bad), f"({len(cases) - len(bad)}/{len(cases)})")
sys.exit(1 if bad else 0)
