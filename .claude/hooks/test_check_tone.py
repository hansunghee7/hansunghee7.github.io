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

    def test_asking_boss_to_act_is_caught_without_reason(self):
        k = "사장님께 행동 요청(사유 표시 없음)"
        self.assertIn(k, self.kinds("사장님이 확장 새로고침을 눌러 주세요."))
        self.assertIn(k, self.kinds("사장님이 PowerShell에서 명령을 실행해 주시면 됩니다."))

    def test_reason_tag_allows_asking(self):
        self.assertEqual(self.kinds("사장님이 외부 서비스 로그인을 해 주세요. [사람 개입 필요: 자격증명]"), [])

    def test_pin_request_is_blocked_even_with_human_tag(self):
        # 사장님 지시 2026-10-03: PIN 입력은 없앨 개입이라 사유 표시로도 통과시키지 않는다
        self.assertIn("사장님께 PIN 입력 요청", self.kinds("사장님이 PIN을 입력해 주세요. [사람 개입 필요: 자격증명]"))
        self.assertIn("사장님께 PIN 입력 요청", self.kinds("서랍을 열려면 사장님이 PIN을 한 번 입력해 주시면 됩니다."))

    def test_pin_request_allowed_only_with_improvement_task_tag(self):
        self.assertEqual(self.kinds("사장님이 PIN을 입력해 주세요. [PIN 개선 과제: N116]"), [])

    def test_decisions_and_reports_are_not_action_requests(self):
        self.assertEqual(self.kinds("사장님이 정하실 것: 2단계 시작 시점입니다."), [])
        self.assertEqual(self.kinds("사장님이 어제 PIN을 입력하셨고 지투가 이어서 처리했습니다."), [])


if __name__ == "__main__":
    unittest.main()
