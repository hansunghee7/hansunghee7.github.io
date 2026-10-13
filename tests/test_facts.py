"""facts.py 순수 함수 시험(DB 없이): 번호 생성, 셀 정리, 번호·비밀값 거부, 기본 항목."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.modules.setdefault("opsdb", types.ModuleType("opsdb"))
spec = importlib.util.spec_from_file_location("facts", ROOT / "scripts" / "ops" / "facts.py")
facts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(facts)


class FactsTest(unittest.TestCase):
    def test_next_no(self):
        self.assertEqual(facts.next_no([]), "F01")
        self.assertEqual(facts.next_no([{"no": "F03"}]), "F04")

    def test_rejects_ids(self):
        for bad in ("법인 110111-1234567", "사업자 123-45-67890", "sk-" + "a" * 20):
            with self.assertRaises(SystemExit):
                facts.clean(bad)

    def test_seed_clean_and_valid_status(self):
        for title, gate, st, res, src, nxt in facts.SEED:
            facts.clean(res, src, nxt)
            self.assertIn(st, facts.STATUSES)

    def test_cell(self):
        self.assertEqual(facts.cell("a|b", 10), "a/b")


if __name__ == "__main__":
    unittest.main()
