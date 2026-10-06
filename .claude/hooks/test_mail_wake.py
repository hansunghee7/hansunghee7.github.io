"""mail-wake.py 시험: mailbox.py send 뒤에만 세션 깨우기 안내를 내보낸다(전체·사장님 제외)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name("mail-wake.py")


def run(command=None, raw=None):
    if raw is None:
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}).encode("utf-8")
    p = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8")


class MailWakeTest(unittest.TestCase):
    def test_send_to_persona_emits_reminder(self):
        code, out = run('python mailbox.py send 노트 "제목" --body x')
        self.assertEqual(code, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("'노트'", ctx)
        self.assertIn("SendMessage", ctx)

    def test_quoted_recipient_is_unquoted(self):
        code, out = run("python solar-bible/mailbox/mailbox.py send '지투' t")
        self.assertIn("'지투'", json.loads(out)["hookSpecificOutput"]["additionalContext"])

    def test_broadcast_and_boss_are_silent(self):
        for to in ("전체", "사장님"):
            self.assertEqual(run(f"python mailbox.py send {to} t"), (0, ""))

    def test_non_send_commands_are_silent(self):
        self.assertEqual(run("python mailbox.py list"), (0, ""))
        self.assertEqual(run("ls"), (0, ""))

    def test_broken_input_passes(self):
        # 경계: JSON이 아닌 입력은 조용히 통과
        self.assertEqual(run(raw=b"not json"), (0, ""))


if __name__ == "__main__":
    unittest.main()
