"""요구사항 취합 후 전달(req)과 노트 요청 관문(jitu-loop.py pre-send) 시험(사장님 지시 2026-10-06).
실행: cd .claude/hooks && python -m unittest test_jitu_loop_req"""
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


class ReqToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06"}

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, *args, today=None, ok=True):
        env = dict(self.env)
        if today:
            env["JITU_PO_TODAY"] = today
        r = run([TOOL] + list(args), env=env)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8"))
        return r

    def test_collecting_area_not_sendable(self):
        self.tool("req", "add", "--area", "온보딩", "--text", "연결 확인 표시")
        r = self.tool("req", "check-send", "온보딩", ok=False)
        self.assertNotEqual(r.returncode, 0)

    def test_ready_makes_area_sendable(self):
        self.tool("req", "add", "--area", "온보딩", "--text", "연결 확인 표시")
        self.tool("req", "ready", "온보딩", "--note", "선행 없음, 충돌 없음, 고객 DB 영향 칸 하나, 시험 실행기로 확인")
        self.assertEqual(self.tool("req", "check-send", "온보딩", ok=False).returncode, 0)

    def test_short_note_rejected(self):
        self.tool("req", "add", "--area", "온보딩", "--text", "x")
        self.assertNotEqual(self.tool("req", "ready", "온보딩", "--note", "다 모음", ok=False).returncode, 0)

    def test_ready_without_items_rejected(self):
        self.assertNotEqual(self.tool("req", "ready", "없는영역", "--note", "빠진 것 점검을 마쳤습니다 확인", ok=False).returncode, 0)

    def test_new_item_cancels_ready(self):
        self.tool("req", "add", "--area", "온보딩", "--text", "a")
        self.tool("req", "ready", "온보딩", "--note", "선행 없음, 충돌 없음, 영향 없음, 확인 방법 있음")
        self.tool("req", "add", "--area", "온보딩", "--text", "새 요구")
        self.assertNotEqual(self.tool("req", "check-send", "온보딩", ok=False).returncode, 0)

    def test_due_shows_collecting_after_a_day_only(self):
        self.tool("req", "add", "--area", "온보딩", "--text", "a")
        self.assertNotIn("요구사항 취합 중", self.tool("due").stdout.decode("utf-8"))
        self.assertIn("요구사항 취합 중", self.tool("due", today="2026-10-07").stdout.decode("utf-8"))

    def test_ready_area_not_in_due(self):
        self.tool("req", "add", "--area", "온보딩", "--text", "a")
        self.tool("req", "ready", "온보딩", "--note", "선행 없음, 충돌 없음, 영향 없음, 확인 방법 있음")
        self.assertNotIn("요구사항 취합 중", self.tool("due", today="2026-10-09").stdout.decode("utf-8"))


class PreSendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06", "JITU_LOOP_FORCE_JITU": "1"}

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, msg, to=NOTE, env=None):
        e = dict(self.env)
        e.update(env or {})
        return run([HOOK, "pre-send"], json.dumps({"tool_input": {"to": to, "message": msg}}), e)

    def ready_area(self, area="온보딩"):
        run([TOOL, "req", "add", "--area", area, "--text", "a"], env=self.env)
        run([TOOL, "req", "ready", area, "--note", "선행 없음, 충돌 없음, 영향 없음, 확인 방법 있음"], env=self.env)

    def test_info_message_passes(self):
        self.assertEqual(self.send("#567 병합했고 실측 결과를 알립니다. 검토 문제 없음.").returncode, 0)

    def test_new_request_without_area_tag_blocked(self):
        r = self.send("연결 확인 표시를 추가해 주세요.")
        self.assertEqual(r.returncode, 2)
        self.assertIn("영역", r.stderr.decode("utf-8"))

    def test_new_request_with_unready_area_blocked(self):
        run([TOOL, "req", "add", "--area", "온보딩", "--text", "a"], env=self.env)
        r = self.send("[영역: 온보딩] 연결 확인 표시를 추가해 주세요.")
        self.assertEqual(r.returncode, 2)
        self.assertIn("전달할 수 없습니다", r.stderr.decode("utf-8"))

    def test_new_request_with_ready_area_passes(self):
        self.ready_area()
        self.assertEqual(self.send("[영역: 온보딩] 연결 확인 표시를 추가해 주세요.").returncode, 0)

    def test_stop_request_without_gain_blocked(self):
        r = self.send("지금 개발을 멈춰 주세요.")
        self.assertEqual(r.returncode, 2)
        self.assertIn("이득", r.stderr.decode("utf-8"))

    def test_stop_request_with_gain_passes(self):
        msg = "[멈춤·변경 이득: 이 방식으로 계속하면 고객 DB 칸을 두 번 바꿔야 해서 1일 낭비] 029 실행을 보류해 주세요."
        self.assertEqual(self.send(msg).returncode, 0)

    def test_stop_request_with_short_gain_blocked(self):
        self.assertEqual(self.send("[멈춤·변경 이득: 이득] 개발을 중단해 주세요.").returncode, 2)

    def test_to_other_persona_passes(self):
        self.assertEqual(self.send("연결 확인 표시를 추가해 주세요.", to="탐 1006 화 1728").returncode, 0)

    def test_non_jitu_session_passes(self):
        self.assertEqual(self.send("연결 확인 표시를 추가해 주세요.", env={"JITU_LOOP_FORCE_JITU": "0"}).returncode, 0)

    def test_bad_json_passes(self):
        self.assertEqual(run([HOOK, "pre-send"], "not json", self.env).returncode, 0)


if __name__ == "__main__":
    unittest.main()
