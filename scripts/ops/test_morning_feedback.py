"""morning_feedback.py 시험: 호출 함수를 가짜로 바꿔 실제 비티·덱스·DB를 부르지 않는다. 실행: python scripts/ops/test_morning_feedback.py"""
import tempfile
import unittest
from pathlib import Path

import morning_feedback as mf


def rows(n, start=1, nxt="다음 행동 본문"):
    return [{"no": f"N{i}", "title": f"행 {i}", "status": "진행", "next_action": nxt} for i in range(start, start + n)]


class Fake:
    def __init__(self):
        self.calls = []

    def __call__(self, card, out):
        self.calls.append(Path(card).read_text(encoding="utf-8"))
        Path(out).write_text("1줄\n2줄\n3줄", encoding="utf-8")
        return 0, "1줄\n2줄\n3줄"


class T(unittest.TestCase):
    def go(self, d, data, fb, fd, date="2026-10-22"):
        return mf.run(date, fetch=lambda: data, bt=fb, dex=fd, ensure=lambda a: "BT9" if a == "bt" else "DX9", out_dir=d)

    def test_no_change_no_call(self):
        with tempfile.TemporaryDirectory() as d:
            fb, fd = Fake(), Fake()
            data = rows(3)
            self.go(d, data, fb, fd, "2026-10-21")  # 첫 실행: 전부 바뀐 행
            fb2, fd2 = Fake(), Fake()
            r = self.go(d, data, fb2, fd2)
            self.assertEqual((r["calls"], len(fb2.calls), len(fd2.calls)), (0, 0, 0))
            self.assertIn("없음", Path(r["path"]).read_text(encoding="utf-8"))

    def test_cap_20_and_ledger_line(self):
        with tempfile.TemporaryDirectory() as d:
            fb, fd = Fake(), Fake()
            r = self.go(d, rows(30), fb, fd)
            self.assertEqual(r["calls"], 2)
            card = fb.calls[0]
            self.assertEqual(card.splitlines()[0], "업무대장: BT9")
            self.assertEqual(fd.calls[0].splitlines()[0], "업무대장: DX9")
            self.assertEqual(sum(1 for ln in card.splitlines() if ln.startswith("- N")), 20)
            self.assertIn("- N30 ", card)
            self.assertNotIn("- N1 ", card)

    def test_masks_secret_words(self):
        with tempfile.TemporaryDirectory() as d:
            fb, fd = Fake(), Fake()
            self.go(d, rows(1, nxt="api_key 교체, 토큰 발급, password 확인, sk-abc123"), fb, fd)
            card = fb.calls[0].split("바뀐 행", 1)[1]
            for w in ("api_key", "토큰", "password", "sk-abc"):
                self.assertNotIn(w, card)
            self.assertIn("[가림]", card)

    def test_changed_row_only_and_result_path(self):
        with tempfile.TemporaryDirectory() as d:
            self.go(d, rows(3), Fake(), Fake(), "2026-10-21")
            data = rows(3)
            data[1]["next_action"] = "바뀐 다음 행동"
            fb, fd = Fake(), Fake()
            r = self.go(d, data, fb, fd)
            self.assertEqual(r["changed"], 1)
            self.assertEqual(r["path"], str(Path(d) / "2026-10-22.md"))
            self.assertTrue(Path(r["path"]).exists())
            self.assertIn("- N2 ", fb.calls[0])
            self.assertNotIn("- N1 ", fb.calls[0])


if __name__ == "__main__":
    unittest.main()
