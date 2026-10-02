"""popup-gate.py 시험: python .claude/hooks/test_popup_gate.py"""
import json, subprocess, sys
from pathlib import Path
H = Path(__file__).with_name("popup-gate.py")
def run(tool, cmd):
    raw = json.dumps({"tool_name": tool, "tool_input": {"command": cmd}}).encode("utf-8") if cmd is not None else b"not json"
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True).returncode
block = ["notepad foo.txt", "notepad.exe a.md", "cd x && notepad a.txt", "echo hi; start a.html", "start a.html",
         "cmd /c start x.html", "Start-Process notepad a.txt", "Start-Process -FilePath notepad.exe", "python -c \"import os; os.startfile('a')\"",
         "explorer.exe C:/work/a.txt", "Invoke-Item a.txt", "ii a.txt", "ls | notepad"]
ok = ["bash start_chromes.sh", "git log --start", "git log --since=x --start", "bash .claude/hooks/session-start.sh", "restart-service x",
      "Start-Sleep 3", "python scripts/start_server.py", "npm start", "echo notepad", "git commit -m 'notepad 금지 추가'", "ls docs", "ssh pc start-job"]
bad = []
for c in block:
    for t in ("Bash", "PowerShell"):
        if run(t, c) != 2: bad.append(f"막아야함:{c}")
for c in ok:
    if run("Bash", c) != 0: bad.append(f"통과해야함:{c}")
if run("Bash", None) != 0: bad.append("깨진 입력")
n = len(block) * 2 + len(ok) + 1
print("통과" if not bad else "실패: " + ", ".join(bad), f"({n - len(bad)}/{n})")
sys.exit(1 if bad else 0)
