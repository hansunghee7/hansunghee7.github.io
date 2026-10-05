"""db-gate.py 시험: python .claude/hooks/test_db_gate.py"""
import json
import subprocess
import sys
from pathlib import Path

H = Path(__file__).with_name("db-gate.py")


def run(tool, **inp):
    raw = json.dumps({"tool_name": tool, "tool_input": inp}).encode("utf-8")
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True).returncode


block = [
    ("Read", {"file_path": "C:/work/hansunghee7.github.io/docs/탐_업무대장.md"}),
    ("Read", {"file_path": "docs/진행상황.md", "limit": 2000}),
    ("Grep", {"pattern": "N151", "path": "docs/탐_업무대장.md"}),
    ("Grep", {"pattern": "N151", "glob": "docs/*업무대장.md"}),
    ("Bash", {"command": "grep -n N151 docs/탐_업무대장.md"}),
    ("Bash", {"command": "cat docs/진행상황.md | head -400"}),
    ("PowerShell", {"command": "Get-Content docs/마야_업무대장.md"}),
    ("PowerShell", {"command": "Select-String -Path docs/핏_업무대장.md -Pattern N66"}),
]
ok = [
    ("Read", {"file_path": "docs/탐_업무대장.md", "limit": 80, "offset": 100}),
    ("Read", {"file_path": "docs/CLAUDE_md_근거_이력.md"}),
    ("Grep", {"pattern": "x", "path": "docs/WRITING_GUIDE.md"}),
    ("Bash", {"command": "sed -n '100,140p' docs/탐_업무대장.md"}),
    ("Bash", {"command": "git log --oneline -- docs/진행상황.md"}),
    ("Bash", {"command": "wc -c docs/탐_업무대장.md"}),
    ("Bash", {"command": "grep -n N151 docs/탐_업무대장.md  # [DB 불가: 방금 바뀐 건 확인]"}),
    ("Bash", {"command": "python scripts/ops/opsdb.py select tasks --where no=eq.N151"}),
    ("Bash", {"command": "python - <<'EOF'\nopen('docs/탐_업무대장.md','w')\nEOF"}),
    ("Edit", {"file_path": "docs/탐_업무대장.md"}),
    ("Bash", {"command": "python - <<'EOF'\nprint(type(e), 'grep')\nopen('docs/탐_업무대장.md')\nEOF"}),
]
bad = []
for t, i in block:
    if run(t, **i) != 2:
        bad.append(f"막아야함:{t} {i}")
for t, i in ok:
    if run(t, **i) != 0:
        bad.append(f"통과해야함:{t} {i}")
n = len(block) + len(ok)
print("통과" if not bad else "실패: " + "; ".join(bad), f"({n - len(bad)}/{n})")
sys.exit(1 if bad else 0)
