"""queue-gate.py 시험: 지투가 '정하실 것 없음'으로 끝내려는데 대장에 대기·지투 행이 있으면 잡고, 그 밖엔 통과한다."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("queue_gate", Path(__file__).parent / "queue-gate.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

LEDGER = """## 열린 항목
| # | 안건 | 출처 | 상태 | 다음 행동 | 증거 | 비용 | 결정자 |
|---|---|---|---|---|---|---|---|
| N60 | 라운드 C 시트 생성 | 사장님 10/5 | 대기 | 시작 | 증거 | 무료 | 지투 |
| N61 | 노트 회신 | 사장님 | 확인필요 | 대기 중 | - | 저 | 노트 |
| N62 | 템플릿 결정 | 사장님 | 대기 | - | - | 저 | 사장님 |
## 닫힌 항목
| N1 | 옛것 | x | 대기 | - | - | - | 지투 |
"""


class QueueGateTest(unittest.TestCase):
    def test_idle_with_open_row_is_blocked(self):
        rows = g.check("지투", "끝. 정하실 것: 없음", LEDGER)
        self.assertEqual([r[0] for r in rows], ["N60"])  # 닫힌 항목·타인 결정자는 안 센다

    def test_wait_marker_counts_as_idle(self):
        self.assertTrue(g.check("지투", "[실행 대기: 노트 회신]", LEDGER))

    def test_not_idle_passes(self):
        self.assertEqual(g.check("지투", "라운드 B 번호표를 보냈습니다.", LEDGER), [])

    def test_other_persona_passes(self):
        self.assertEqual(g.check("탐", "정하실 것: 없음", LEDGER), [])

    def test_no_open_rows_passes(self):
        self.assertEqual(g.check("지투", "정하실 것: 없음", LEDGER.replace("| 대기 | 시작 |", "| 진행 | 시작 |")), [])

    def test_persona_from_first_message(self):
        self.assertEqual(g.persona_of("하이 지투"), "지투")
        self.assertEqual(g.persona_of("지투 예약 세션입니다"), "지투")
        self.assertIsNone(g.persona_of("하이 탐"))

    def test_hourly_cap(self):
        with tempfile.TemporaryDirectory() as d:
            g.COUNT_FILE = os.path.join(d, "c.json")
            self.assertTrue(all(g.allowed_now(1000.0 + i) for i in range(3)))
            self.assertFalse(g.allowed_now(1010.0))  # 4번째는 통과시킨다(막지 않음)
            self.assertTrue(g.allowed_now(1000.0 + 3700))  # 한 시간 뒤 다시 센다


if __name__ == "__main__":
    unittest.main()
