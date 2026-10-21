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

    def test_corrupt_state_recovery_cap_10(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "state.json").write_text("{깨진", encoding="utf-8")
            fb, fd = Fake(), Fake()
            r = self.go(d, rows(30), fb, fd)
            self.assertEqual(sum(1 for ln in fb.calls[0].splitlines() if ln.startswith("- N")), 10)
            self.assertTrue((Path(d) / "state.json.bak").exists())
            self.assertIn("복구", Path(r["path"]).read_text(encoding="utf-8"))
            # 다음 실행은 정상 상한 20, 이미 처리한 10행은 제외되고 나머지 20행이 후보
            fb2, fd2 = Fake(), Fake()
            r2 = self.go(d, rows(30), fb2, fd2, "2026-10-23")
            self.assertEqual(r2["changed"], 20)

    def test_failed_call_keeps_state(self):
        with tempfile.TemporaryDirectory() as d:
            bad = lambda c, o: (1, "")
            r = self.go(d, rows(3), Fake(), bad)
            self.assertEqual(r["rc"], 1)
            self.assertEqual(mf.load_state(Path(d) / "state.json")[0], {})
            r2 = self.go(d, rows(3), bad, bad, "2026-10-23")  # 둘 다 실패
            self.assertEqual(r2["rc"], 1)
            r3 = self.go(d, rows(3), Fake(), Fake(), "2026-10-24")  # 다음 날 다시 처리
            self.assertEqual((r3["rc"], r3["changed"]), (0, 3))
            self.assertEqual(len(mf.load_state(Path(d) / "state.json")[0]), 3)

    def test_atomic_replace(self):
        with tempfile.TemporaryDirectory() as d:
            used = []
            real = mf.os.replace
            mf.os.replace = lambda a, b: (used.append((Path(a).name, Path(b).name)), real(a, b))[1]
            try:
                self.go(d, rows(2), Fake(), Fake())
            finally:
                mf.os.replace = real
            self.assertIn(("state.json.tmp", "state.json"), used)
            self.assertFalse((Path(d) / "state.json.tmp").exists())

    def test_kst_date(self):
        import datetime
        utc = datetime.timezone.utc
        self.assertEqual(mf.kst_today(datetime.datetime(2026, 10, 21, 16, 0, tzinfo=utc)), "2026-10-22")
        self.assertEqual(mf.kst_today(datetime.datetime(2026, 10, 21, 14, 59, tzinfo=utc)), "2026-10-21")

    def test_rerun_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = self.go(d, rows(1), Fake(), Fake())["path"]
            p2 = self.go(d, rows(1, nxt="바뀜"), Fake(), Fake())["path"]
            p3 = self.go(d, rows(1, nxt="또 바뀜"), Fake(), Fake())["path"]
            self.assertEqual([Path(p).name for p in (p1, p2, p3)], ["2026-10-22.md", "2026-10-22-2.md", "2026-10-22-3.md"])
            self.assertTrue(all(Path(p).exists() for p in (p1, p2, p3)))


if __name__ == "__main__":
    unittest.main()
