"""grant_reqs.py 순수 함수 시험(DB 없이): 번호 생성, 사업별 집계, 정렬, 번호·비밀값 거부, 거울 보호 목록."""
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.modules.setdefault("opsdb", types.ModuleType("opsdb"))
spec = importlib.util.spec_from_file_location("grant_reqs", ROOT / "scripts" / "ops" / "grant_reqs.py")
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)


class GrantReqsTest(unittest.TestCase):
    def test_next_no(self):
        self.assertEqual(gr.next_no([], "Q"), "Q01")
        self.assertEqual(gr.next_no([{"no": "Q09"}, {"no": "Q10"}], "Q"), "Q11")
        self.assertEqual(gr.next_no([{"no": "A02"}], "A"), "A03")

    def test_matrix_counts(self):
        rows = [{"owner": "G14", "status": "충족"}, {"owner": "G14", "status": "확인필요"}, {"owner": "G20", "status": "확인필요"}]
        mc = gr.matrix_counts(rows)
        self.assertEqual(mc["G14"]["충족"], 1)
        self.assertEqual(mc["G14"]["확인필요"], 1)
        self.assertEqual(mc["G20"]["미충족"], 0)

    def test_act_sort(self):
        rows = [
            {"no": "A1", "status": "대기", "source_date": "2026-11-01", "raw": '{"priority": 2}'},
            {"no": "A2", "status": "완료", "source_date": "2026-10-01", "raw": '{"priority": 1}'},
            {"no": "A3", "status": "대기", "source_date": "2026-10-20", "raw": '{"priority": 1}'},
        ]
        self.assertEqual([r["no"] for r in sorted(rows, key=gr.act_sort_key)], ["A3", "A1", "A2"])

    def test_common_usage(self):
        rows = [{"raw": '{"common": "C01"}'}, {"raw": {"common": "C01"}}, {"raw": '{"common": "C02"}'}, {"raw": "{}"}]
        self.assertEqual(gr.common_usage(rows), {"C01": 2, "C02": 1})

    def test_boss_tier(self):
        import datetime
        t = datetime.date(2026, 10, 14)
        hi = {"source_date": "2026-10-20", "raw": '{"impact": "상"}'}
        mid = {"source_date": "2026-10-20", "raw": '{"impact": "중"}'}
        late = {"source_date": "2026-12-01", "raw": '{"impact": "상"}'}
        self.assertEqual(gr.boss_tier(hi, 14, t), 1)
        self.assertEqual(gr.boss_tier(mid, 14, t), 2)
        soon = {"source_date": "2026-11-15", "raw": '{"impact": "상"}'}
        self.assertEqual(gr.boss_tier(soon, 14, t), 3)
        self.assertEqual(gr.boss_tier(late, 14, t), 4)

    def test_rejects_ids(self):
        for bad in ("123-45-67890", "110111-1234567", "sk-" + "a" * 20):
            with self.assertRaises(SystemExit):
                gr.clean(bad)

    def test_mirror_protects_req_and_act(self):
        src = (ROOT / "scripts" / "ops" / "import_ops_tables.py").read_text(encoding="utf-8")
        found = re.findall(r"not\.in\.\(([^)]*)\)", src)
        self.assertTrue(found)
        for f in found:
            for sec in ("req", "act", "creq"):
                self.assertIn(sec, f.split(","), f"시간당 거울이 section={sec} 행을 지우면 안 된다")


if __name__ == "__main__":
    unittest.main()
