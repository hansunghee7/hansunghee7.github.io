"""grants.py 순수 함수 시험(DB 없이): 구분 판정, 번호 생성, 표 셀 정리, 비밀값 거부, 거울 보호 목록."""
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.modules.setdefault("opsdb", types.ModuleType("opsdb"))
spec = importlib.util.spec_from_file_location("grants", ROOT / "scripts" / "ops" / "grants.py")
grants = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grants)


class GrantsTest(unittest.TestCase):
    def test_kind_of(self):
        self.assertEqual(grants.kind_of("서울특별시(서울R&D지원센터)"), "지자체")
        self.assertEqual(grants.kind_of("Google Cloud (민간)"), "기업")
        self.assertEqual(grants.kind_of("중소벤처기업부"), "국가")

    def test_next_no(self):
        self.assertEqual(grants.next_no([]), "G01")
        self.assertEqual(grants.next_no([{"no": "G01"}, {"no": "G09"}]), "G10")

    def test_cell(self):
        self.assertEqual(grants.cell("a|b\nc", 10), "a/b c")
        self.assertTrue(grants.cell("x" * 100, 20).endswith("…"))

    def test_secret_rejected(self):
        with self.assertRaises(SystemExit):
            grants.clean("메모 sk-" + "a" * 20)

    def test_mirror_protects_grant_rows(self):
        src = (ROOT / "scripts" / "ops" / "import_ops_tables.py").read_text(encoding="utf-8")
        found = re.findall(r"not\.in\.\(([^)]*)\)", src)
        self.assertTrue(found)
        for f in found:
            self.assertIn("grant", f.split(","), "시간당 거울이 지원현황(section=grant) 행을 지우면 안 된다")


if __name__ == "__main__":
    unittest.main()
