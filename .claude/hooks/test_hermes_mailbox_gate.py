"""hermes-mailbox-gate.py 시험: python .claude/hooks/test_hermes_mailbox_gate.py"""
import json, subprocess, sys
from pathlib import Path
H = Path(__file__).with_name("hermes-mailbox-gate.py")
def run(cmd):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}).encode("utf-8") if cmd is not None else b"not json"
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True).returncode
cases = [
    ("헤르메스 수신은 막음", 'python C:/work/solar-bible/mailbox/mailbox.py send 헤르메스 "작업" --from 탐', 2),
    ("따옴표 수신도 막음", "python mailbox.py send '헤르메스' 제목 --body x", 2),
    ("탐 수신은 통과", 'python mailbox.py send 탐 "제목" --from 헤르메스', 0),
    ("사장님 수신은 통과", 'python mailbox.py send 사장님 "결정" --ask "x"', 0),
    ("발신자가 헤르메스인 경우 통과", 'python mailbox.py send 핏 "제목" --from 헤르메스', 0),
    ("관련 없는 명령은 통과", "ls docs", 0),
    ("깨진 입력은 통과", None, 0),
]
bad = [n for n, c, w in cases if run(c) != w]
print("통과" if not bad else "실패: " + ", ".join(bad), f"({len(cases) - len(bad)}/{len(cases)})")
sys.exit(1 if bad else 0)
