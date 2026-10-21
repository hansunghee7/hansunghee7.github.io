"""cite-note-gate.py 시험: python .claude/hooks/test_cite_note_gate.py"""
import json, subprocess, sys
from pathlib import Path
H = Path(__file__).with_name("cite-note-gate.py")
def run(ti, tool="mcp__saegim__cite"):
    raw = json.dumps({"tool_name": tool, "tool_input": ti}).encode("utf-8") if ti is not None else b"not json"
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True).returncode
cases = [
    ("접두어 없는 note는 막음", {"note": "보고 문구 반영"}, 2),
    ("빈 note는 막음", {"note": ""}, 2),
    ("[탐] 접두어는 통과", {"note": "[탐] 보고 문구 반영"}, 0),
    ("note 입력이 없으면 통과", {"section": "x"}, 0),
    ("깨진 입력은 통과", None, 0),
]
bad = [n for n, ti, w in cases if run(ti) != w]
# 등록 이름 이중 허용: carvit 이름으로도 같은 결과
bad += ["carvit:" + n for n, ti, w in cases if run(ti, "mcp__carvit__cite") != w]
total = len(cases) * 2
print("통과" if not bad else "실패: " + ", ".join(bad), f"({total - len(bad)}/{total})")
sys.exit(1 if bad else 0)
