"""pace_log.py 단위 시험. 기록 폴더(STATE)는 임시 폴더로 바꾸고 시각은 실제 현재 시각 기준 상대값을 쓴다. 네트워크 없음.

실행: python -m pytest scripts/ops/tests/test_pace_log.py  (또는 python -m unittest)
"""
import contextlib
import csv
import datetime as dt
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pace_log_under_test", OPS / "pace_log.py")
pl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pl)

UTC = dt.timezone.utc
RESET = dt.datetime(2026, 10, 10, 0, 0, tzinfo=UTC)


class Pure(unittest.TestCase):
    def test_parse_utc_accepts_z_suffix(self):
        self.assertEqual(pl.parse_utc("2026-10-10T00:00:00Z"), RESET)
        self.assertEqual(pl.parse_utc("2026-10-10T09:00:00+09:00"), RESET)

    def test_evaluate_on_pace_halfway(self):
        now = RESET - dt.timedelta(days=3.5)
        elapsed, pace, days_left, per_day = pl.evaluate(50, RESET, now)
        self.assertAlmostEqual(elapsed, 0.5)
        self.assertAlmostEqual(pace, 1.0)
        self.assertAlmostEqual(days_left, 3.5)
        self.assertAlmostEqual(per_day, 50 / 3.5)

    def test_evaluate_fast_and_slow(self):
        _, fast, _, _ = pl.evaluate(60, RESET, RESET - dt.timedelta(days=5))  # 경과 2/7에 60% 사용
        _, slow, _, _ = pl.evaluate(10, RESET, RESET - dt.timedelta(days=3.5))
        self.assertGreater(fast, 2.0)
        self.assertLess(slow, 0.5)

    def test_evaluate_clamps_edges(self):
        before_start = RESET - dt.timedelta(days=8)  # 창 시작 전: 경과율 하한 0.0001
        elapsed, pace, _, _ = pl.evaluate(1, RESET, before_start)
        self.assertEqual(elapsed, 0.0001)
        self.assertAlmostEqual(pace, 100.0)
        after_reset = RESET + dt.timedelta(days=1)  # 초기화 뒤: 경과율 상한 1.0, 남은 일수 하한 0.01
        elapsed, _, days_left, per_day = pl.evaluate(40, RESET, after_reset)
        self.assertEqual((elapsed, days_left), (1.0, 0.01))
        self.assertAlmostEqual(per_day, 60 / 0.01)

    def test_label_boundaries(self):
        self.assertEqual(pl.label(0.0), "정상")
        self.assertEqual(pl.label(1.0), "정상")  # 기준값은 '초과'부터
        self.assertEqual(pl.label(1.01), "주의")
        self.assertEqual(pl.label(1.3), "주의")
        self.assertEqual(pl.label(1.31), "경고")


class MainRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(pl, "STATE", str(Path(self.tmp.name) / "pace"))  # 폴더가 아직 없어도 만들어야 한다
        p.start()
        self.addCleanup(p.stop)
        self.reset = (dt.datetime.now(UTC) + dt.timedelta(days=3.5)).isoformat()  # 지금이 창의 정확히 중간

    def run_main(self, *args):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["pace_log.py", "--reset", self.reset, *args]), contextlib.redirect_stdout(buf):
            rc = pl.main()
        return rc, buf.getvalue()

    def rows(self):
        with open(Path(pl.STATE) / "usage.csv", encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    def test_on_pace_writes_header_row_and_last_run(self):
        rc, out = self.run_main("--week", "20", "--five", "30", "--ctx", "64", "--note", "세션 시작")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("정상:"))
        rows = self.rows()
        self.assertEqual(rows[0][0], "기록시각_UTC")
        self.assertEqual(len(rows), 2)
        r = rows[1]
        self.assertEqual((r[1], r[2], r[3], r[6], r[9]), ("20.0", "30.0", "64.0", "정상", "세션 시작"))
        last = (Path(pl.STATE) / "last-run.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(last[1].split()[0], "정상")

    def test_labels_by_usage(self):
        for week, lab in ((20, "정상"), (60, "주의"), (80, "경고")):
            with self.subTest(week=week):
                _, out = self.run_main("--week", str(week))
                self.assertTrue(out.startswith(lab + ":"), out)

    def test_optional_columns_blank_when_omitted(self):
        self.run_main("--week", "10")
        r = self.rows()[1]
        self.assertEqual((r[2], r[3], r[9]), ("", "", ""))

    def test_second_run_appends_without_second_header(self):
        self.run_main("--week", "10")
        self.run_main("--week", "20")
        rows = self.rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual([r[0] for r in rows].count("기록시각_UTC"), 1)

    def test_last_run_reflects_latest_label(self):
        self.run_main("--week", "20")
        self.run_main("--week", "80")
        last = (Path(pl.STATE) / "last-run.txt").read_text(encoding="utf-8")
        self.assertIn("경고", last)

    def test_week_is_required(self):
        with mock.patch.object(sys, "argv", ["pace_log.py", "--reset", self.reset]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                pl.main()


if __name__ == "__main__":
    unittest.main()
