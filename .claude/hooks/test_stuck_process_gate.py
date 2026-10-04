"""stuck-process-gate.py 시험: 막혔다는 답변은 절차 기록을 열어 봤을 때만 통과한다."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("sg", Path(__file__).parent / "stuck-process-gate.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

READ = [("Read", {"file_path": "C:/work/hansunghee7.github.io/docs/핏_프로세스표.md"})]
OTHER = [("Bash", {"command": "ls /tmp"})]


class StuckGateTest(unittest.TestCase):
    def test_stuck_without_lookup_is_blocked(self):
        self.assertEqual(sg.check("Vids 내려받기가 안 됩니다.", OTHER), "no-process-lookup")
        self.assertEqual(sg.check("다운로드에서 막혔습니다.", []), "no-process-lookup")

    def test_stuck_with_process_lookup_passes(self):
        self.assertIsNone(sg.check("Vids 내려받기가 안 됩니다.", READ))
        self.assertIsNone(sg.check("막혔습니다.", [("Grep", {"pattern": "삽입", "path": "GENERATION_PIPELINES.md"})]))

    def test_negated_or_clean_text_passes(self):
        self.assertIsNone(sg.check("막힘 없이 통과했습니다.", []))
        self.assertIsNone(sg.check("결과를 기록했습니다.", []))


if __name__ == "__main__":
    unittest.main()
