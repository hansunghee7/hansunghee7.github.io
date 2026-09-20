"""skill-nudge.py 시험: 개시어만 잡고, 비슷하게 시작하는 일반 문장은 건드리지 않는지 확인한다."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("skill_nudge", Path(__file__).parent / "skill-nudge.py")
sn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sn)


class NudgeTest(unittest.TestCase):
    def test_morning_keyword(self):
        self.assertIn("session-start", sn.nudge("하이~"))
        self.assertIn("session-start", sn.nudge("  하이~ 뒤에 지시서를 읽고 Phase 1만 진행하라"))

    def test_short_greeting_with_name(self):
        self.assertIn("session-start", sn.nudge("하이 탐"))

    def test_evening_keyword(self):
        self.assertIn("session-end", sn.nudge("바이~"))
        self.assertIn("session-end", sn.nudge("바이"))

    def test_words_that_merely_start_with_hai_are_ignored(self):
        self.assertEqual(sn.nudge("하이브리드 방식으로 바꿔줘"), "")
        self.assertEqual(sn.nudge("바이올린 연습 영상 만들어줘"), "")

    def test_normal_request_is_ignored(self):
        self.assertEqual(sn.nudge("이번 주 블로그 글 하나 써줘"), "")
        self.assertEqual(sn.nudge(""), "")


if __name__ == "__main__":
    unittest.main()
