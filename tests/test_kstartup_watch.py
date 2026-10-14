"""kstartup_watch.py 순수 함수 시험(네트워크 없이): 목록 파싱, 키워드 판정."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ksw", ROOT / "scripts" / "ops" / "kstartup_watch.py")
ksw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ksw)

SAMPLE = '<a href="#" onclick="go_view(179428)"><p class="tit">2027년 창업도약패키지 모집공고</p></a><a onclick="go_view(179408)"><p class="tit">일반 공고</p></a><a onclick="go_view(179428)"><p class="tit">중복</p></a>'


class KsTest(unittest.TestCase):
    def test_parse(self):
        r = ksw.parse(SAMPLE)
        self.assertEqual(r[0], ("179428", "2027년 창업도약패키지 모집공고"))
        self.assertEqual(len(r), 2)

    def test_hit(self):
        self.assertIn("창업도약", ksw.hit("2027년 창업도약패키지"))
        self.assertEqual(ksw.hit("농식품 공고"), [])


if __name__ == "__main__":
    unittest.main()
