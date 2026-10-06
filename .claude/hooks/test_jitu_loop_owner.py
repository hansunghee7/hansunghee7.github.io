"""문구 수정 요청의 담당 판정 관문(jitu-loop.py pre-send) 시험(사장님 지시 2026-10-06). 실행: cd .claude/hooks && python -m unittest test_jitu_loop_owner"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "jitu-loop.py")
TOOL = os.path.join(HERE, "..", "..", "scripts", "ops", "jitu_po.py")
NOTE = "노트 1006 화 1811"


def run(args, stdin=None, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable] + args, input=(stdin or "").encode("utf-8"), capture_output=True, env=e)


class OwnerGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06", "JITU_LOOP_FORCE_JITU": "1"}
        run([TOOL, "req", "add", "--area", "온보딩", "--text", "a"], env=self.env)
        run([TOOL, "req", "ready", "온보딩", "--note", "선행 없음, 충돌 없음, 영향 없음, 확인 방법 있음"], env=self.env)

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, msg, to=NOTE, env=None):
        e = dict(self.env)
        e.update(env or {})
        return run([HOOK, "pre-send"], json.dumps({"tool_input": {"to": to, "message": msg}}), e)

    def test_copy_fix_request_to_note_blocked(self):
        r = self.send("[영역: 온보딩] 가입 화면의 설치 코드 안내 문구를 고쳐 주세요.")
        self.assertEqual(r.returncode, 2)
        self.assertIn("지투가 직접", r.stderr.decode("utf-8"))

    def test_mail_body_request_blocked(self):
        self.assertEqual(self.send("[영역: 온보딩] 가입 안내 메일 본문을 수정해 주세요.").returncode, 2)

    def test_copy_request_with_owner_tag_passes(self):
        msg = "[영역: 온보딩] [지투 직접 불가: 번역 사전 키와 시험이 서버 코드와 한 묶음이라 노트의 시험 환경이 필요] 안내 문구를 고쳐 주세요."
        self.assertEqual(self.send(msg).returncode, 0)

    def test_short_owner_tag_blocked(self):
        self.assertEqual(self.send("[영역: 온보딩] [지투 직접 불가: 시간] 안내 문구를 고쳐 주세요.").returncode, 2)

    def test_code_request_unaffected(self):
        self.assertEqual(self.send("[영역: 온보딩] 연결 확인 요청이 실패하면 재시도하도록 만들어 주세요.").returncode, 0)

    def test_info_message_mentioning_copy_passes(self):
        self.assertEqual(self.send("문구 줄은 지투가 직접 고칩니다. 겹치는 작업이 있는지 알려 주세요.").returncode, 0)

    def test_negative_instruction_passes(self):
        self.assertEqual(self.send("문구 줄은 수정하지 말아 달라고 알립니다.").returncode, 0)

    def test_other_persona_passes(self):
        self.assertEqual(self.send("안내 문구를 고쳐 주세요.", to="마야 1006 화 1816").returncode, 0)

    def test_non_jitu_session_passes(self):
        self.assertEqual(self.send("안내 문구를 고쳐 주세요.", env={"JITU_LOOP_FORCE_JITU": "0"}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
