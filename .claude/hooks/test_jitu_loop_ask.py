"""결정 요청 관문(jitu-loop.py stop)과 ask 기록장 시험(사장님 지시 2026-10-06 ①②). 실행: cd .claude/hooks && python -m unittest test_jitu_loop_ask"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "jitu-loop.py")
TOOL = os.path.join(HERE, "..", "..", "scripts", "ops", "jitu_po.py")
Q = "세인님께 사실 그대로의 다국어 확인 메일을 보낼지"
REPEAT = "정하실 것: " + Q + "\n추천: 1번, 사실 그대로의 확인 메일\n답이 없으면 보류합니다."


def run(args, stdin=None, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable] + args, input=(stdin or "").encode("utf-8"), capture_output=True, env=e)


class StopGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_LOOP_FORCE_JITU": "1"}

    def tearDown(self):
        self.tmp.cleanup()

    def stop(self, text, active=False, env=None):
        path = os.path.join(self.tmp.name, "t.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}, ensure_ascii=False) + "\n")
        e = dict(self.env)
        e.update(env or {})
        return run([HOOK, "stop"], json.dumps({"transcript_path": path, "stop_hook_active": active}), e)

    def add_ask(self, created=""):
        args = [TOOL, "ask", "add", "--text", Q, "--rec", "1번 사실 그대로 확인 메일", "--default", "보류"]
        if created:
            args += ["--created", created]
        run(args, env={"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06"})

    def test_none_passes(self):
        self.assertEqual(self.stop("보고입니다.\n\n정하실 것: 없음").returncode, 0)

    def test_decision_with_recommendation_and_default_passes(self):
        t = "정하실 것: 메일을 보낼지\n추천: 1번, 사실 그대로라서\n답이 없으면 보류하고 10/8에 다시 알립니다."
        self.assertEqual(self.stop(t).returncode, 0)

    def test_decision_without_recommendation_blocked(self):
        r = self.stop("정하실 것: 메일을 보낼지\n답이 없으면 보류합니다.")
        self.assertEqual(r.returncode, 2)
        self.assertIn("추천이 없습니다", r.stderr.decode("utf-8"))

    def test_decision_without_default_blocked(self):
        r = self.stop("정하실 것: 메일을 보낼지\n추천: 1번")
        self.assertEqual(r.returncode, 2)
        self.assertIn("기본값 또는 마감", r.stderr.decode("utf-8"))

    def test_marker_lines_after_decision_are_not_part_of_it(self):
        t = "정하실 것: 메일을 보낼지, 추천 1번, 답이 없으면 보류\n\n[사람 개입 필요: 외부 발신]"
        self.assertEqual(self.stop(t).returncode, 0)

    def test_stop_hook_active_passes(self):
        self.assertEqual(self.stop("정하실 것: 무엇을 할지", active=True).returncode, 0)

    def test_other_persona_passes(self):
        self.assertEqual(self.stop("정하실 것: 무엇을 할지", env={"JITU_LOOP_FORCE_JITU": "0"}).returncode, 0)

    def test_repeat_of_old_open_ask_blocked(self):
        self.add_ask("2026-10-06T09:00")
        r = self.stop(REPEAT)
        self.assertEqual(r.returncode, 2)
        self.assertIn("A-1", r.stderr.decode("utf-8"))

    def test_fresh_ask_is_not_blocked(self):
        self.add_ask()  # 방금 기록한 질문은 자기 자신이라 막지 않는다
        self.assertEqual(self.stop(REPEAT).returncode, 0)

    def test_answered_ask_is_not_blocked(self):
        self.add_ask("2026-10-06T09:00")
        run([TOOL, "ask", "answer", "A-1", "--answer", "보내지 않음"], env={"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06"})
        self.assertEqual(self.stop(REPEAT).returncode, 0)

    def test_different_decision_is_not_blocked(self):
        self.add_ask("2026-10-06T09:00")
        t = "정하실 것: 시연용 화면 값을 어느 길로 얻을지\n추천: B 길, 열람 규칙과 충돌이 없어서\n답이 없으면 B 길로 둡니다."
        self.assertEqual(self.stop(t).returncode, 0)


class AskToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06"}

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, *args, today=None):
        env = dict(self.env)
        if today:
            env["JITU_PO_TODAY"] = today
        r = run([TOOL] + list(args), env=env)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8"))
        return r.stdout.decode("utf-8")

    def test_open_ask_due_next_day_with_status_hint(self):
        self.tool("ask", "add", "--text", "메일을 보낼지", "--rec", "1번", "--default", "보류")
        self.assertNotIn("결정 요청", self.tool("due", today="2026-10-06"))
        out = self.tool("due", today="2026-10-07")
        self.assertIn("결정 요청", out)
        self.assertIn("다시 묻지 말고", out)

    def test_answer_closes_due(self):
        self.tool("ask", "add", "--text", "메일을 보낼지", "--rec", "1번", "--default", "보류")
        self.tool("ask", "answer", "A-1", "--answer", "보류")
        self.assertNotIn("결정 요청", self.tool("due", today="2026-10-09"))

    def test_find_reports_existing_ask(self):
        self.tool("ask", "add", "--text", "세인님께 다국어 확인 메일을 보낼지", "--rec", "1번", "--default", "보류")
        self.assertIn("A-1", self.tool("ask", "find", "다국어", "메일"))
        self.assertIn("없음", self.tool("ask", "find", "전혀다른주제"))

    def test_deadline_passed_is_due_same_day(self):
        self.tool("ask", "add", "--text", "메일을 보낼지", "--rec", "1번", "--default", "보류", "--due", "2026-10-05")
        self.assertIn("마감 지남", self.tool("due"))


if __name__ == "__main__":
    unittest.main()
