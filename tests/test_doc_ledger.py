"""doc_ledger.py 순수 함수 시험(DB 없이): 번호 생성, 만료 계산, 번호·비밀값 거부, 거울 보호 목록."""
import datetime
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.modules.setdefault("opsdb", types.ModuleType("opsdb"))
spec = importlib.util.spec_from_file_location("doc_ledger", ROOT / "scripts" / "ops" / "doc_ledger.py")
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)


class DocLedgerTest(unittest.TestCase):
    def test_next_no(self):
        self.assertEqual(dl.next_no([]), "D01")
        self.assertEqual(dl.next_no([{"no": "D09"}]), "D10")

    def test_days_left(self):
        t = datetime.date(2026, 10, 14)
        self.assertEqual(dl.days_left("2026-10-24", t), 10)
        self.assertEqual(dl.days_left("2026-10-10", t), -4)
        self.assertIsNone(dl.days_left("", t))

    def test_rejects_ids(self):
        for bad in ("123-45-67890", "110111-1234567", "sk-" + "a" * 20):
            with self.assertRaises(SystemExit):
                dl.clean(bad)

    def test_mirror_protects_doc(self):
        src = (ROOT / "scripts" / "ops" / "import_ops_tables.py").read_text(encoding="utf-8")
        found = re.findall(r"not\.in\.\(([^)]*)\)", src)
        self.assertTrue(found)
        for f in found:
            self.assertIn("doc", f.split(","), "시간당 거울이 서류 대장(section=doc) 행을 지우면 안 된다")


if __name__ == "__main__":
    unittest.main()
