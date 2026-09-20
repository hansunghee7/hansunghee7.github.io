"""check-tone.py 시험: 오탐(시각 표현 "오늘")과 진짜 일반화가 구분되는지 확인한다."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("check_tone", Path(__file__).parent / "check-tone.py")
tone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tone)


class ToneTest(unittest.TestCase):
    def kinds(self, text):
        return [k for k, _ in tone.check(text)]

    def test_today_is_not_an_absolute_claim(self):
        # 2026-09-20 오탐: "오늘 낮입니다"의 "늘"이 "항상"으로 읽혔다
        self.assertEqual(self.kinds("진행상황 블록의 시각은 오늘 낮입니다."), [])

    def test_word_that_starts_with_neul_is_not_an_absolute_claim(self):
        # 2026-09-20 두 번째 오탐: "늘어나는지"(증가)의 "늘"이 "항상"으로 읽혔다
        self.assertEqual(self.kinds("여유가 늘어나는지는 확인이 필요합니다."), [])
        self.assertEqual(self.kinds("디스크가 늘어난 뒤에는 다시 확인합니다."), [])

    def test_real_generalization_is_still_caught(self):
        self.assertIn("근거 없는 일반화", self.kinds("에이전트들은 늘 그렇게 합니다."))
        self.assertIn("근거 없는 일반화", self.kinds("항상 이런 식입니다."))
        self.assertIn("근거 없는 일반화", self.kinds("매번 같은 실수를 합니다."))

    def test_evidence_marker_allows_generalization(self):
        self.assertEqual(self.kinds("항상 이런 식입니다. [추정]"), [])

    def test_hostile_framing_still_caught(self):
        self.assertIn("적대 프레이밍", self.kinds("사장님이 원칙을 번복하셨습니다."))


if __name__ == "__main__":
    unittest.main()
