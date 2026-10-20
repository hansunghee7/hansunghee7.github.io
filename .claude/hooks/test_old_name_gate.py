import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "old-name-gate.py")


def run(payload):
    env = dict(os.environ, OLD_NAME_GATE_LOG=os.path.join(tempfile.gettempdir(), "old_name_gate_test.log"))
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", env=env)
    return p.returncode, p.stderr


def edit(new, old="x"):
    return {"tool_name": "Edit", "tool_input": {"file_path": "a.md", "old_string": old, "new_string": new}}


class OldNameGate(unittest.TestCase):
    def test_blocks_new_coinage(self):
        rc, err = run(edit("saegim DM 보내기 saegim-dm"))
        self.assertEqual(rc, 2)
        self.assertIn("saegim-dm", err)

    def test_blocks_korean_old_name(self):
        rc, _ = run(edit("새김UX 가이드"))
        self.assertEqual(rc, 2)

    def test_allows_system_id(self):
        rc, _ = run(edit("저장소 simplifier-saegim 와 saegim-pass-dev 를 본다"))
        self.assertEqual(rc, 0)

    def test_allows_keeping_existing_word(self):
        rc, _ = run(edit("saegim_x 사용", old="saegim_x 사용 전"))
        self.assertEqual(rc, 0)

    def test_allows_removal(self):
        rc, _ = run(edit("carvit_x", old="saegim_x"))
        self.assertEqual(rc, 0)

    def test_escape_passes(self):
        rc, _ = run(edit("saegim_new [옛이름 허용: 호환 별칭]"))
        self.assertEqual(rc, 0)

    def test_ignores_other_tools(self):
        rc, _ = run({"tool_name": "Bash", "tool_input": {"command": "echo saegim_new"}})
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
