"""commit-gate.py 시험: 약속만 있는 답변은 막고, 증거 표지가 있거나 약속이 아니면 통과한다."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("commit_gate", Path(__file__).parent / "commit-gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

BG = [("Bash", {"command": "ssh x 'nohup ./run.sh >> logs/x.log &'", "run_in_background": False})]


class CommitGateTest(unittest.TestCase):
    def test_bare_promise_is_blocked(self):
        # 2026-10-04 핏 사고 문장
        self.assertEqual(gate.check("정하실 것은 없음, 핏이 진행합니다.", []), "no-tag")
        self.assertEqual(gate.check("새 리듬 구현을 시작하겠습니다.", []), "no-tag")

    def test_run_tag_needs_launch_evidence(self):
        text = "구현을 진행합니다. [지금 돌고 있는 것: 구PC logs/x.log]"
        self.assertEqual(gate.check(text, []), "run-tag-without-evidence")
        self.assertIsNone(gate.check(text, BG))
        self.assertIsNone(gate.check(text, [("Monitor", {})]))

    def test_tag_must_match_launched_work(self):
        # 2026-10-04: 약속한 작업과 무관한 태그를 달아 통과하던 구멍
        text = "화질 점검을 진행합니다. [지금 돌고 있는 것: lf01 화질 점검 ffmpeg 프레임 추출]"
        wrong = [("Bash", {"command": "gh pr merge --auto", "run_in_background": True})]
        right = [("Bash", {"command": "nohup ffmpeg -i lf01_clip.mp4 frame.png &", "run_in_background": True})]
        self.assertEqual(gate.check(text, wrong), "run-tag-topic-mismatch")
        self.assertIsNone(gate.check(text, right + wrong[:0]))

    def test_wait_tag_is_honest_pass(self):
        text = "크레딧 갱신 뒤 재개하겠습니다. [실행 대기: 9225 크레딧 22:50 갱신]"
        self.assertIsNone(gate.check(text, []))

    def test_no_promise_passes(self):
        self.assertIsNone(gate.check("구PC 한 컷이 성공했습니다. 결과를 기록했습니다.", []))
        self.assertIsNone(gate.check("이번에는 재시도하지 않겠습니다.", []))


if __name__ == "__main__":
    unittest.main()
