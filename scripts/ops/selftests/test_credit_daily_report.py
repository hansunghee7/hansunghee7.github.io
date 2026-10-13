"""credit_daily_report.py 시험: 가짜 장부로 앞섬·정상·지연·위험·완료와 실패 행 무시, 콘솔 기록 구조를 확인한다(외부 호출 없음)."""
import csv, importlib.util, json, os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cdr", HERE / "credit_daily_report.py")
cdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cdr)


def make_ledger(tmp, rows):
    p = Path(tmp) / "ledger.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "who", "model", "cost_usd", "in_tok", "out_tok", "status"])
        for r in rows:
            w.writerow(r)
    return p


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["CREDIT_DAILY_DIR"] = str(Path(self.tmp) / "d")
        os.environ["CREDIT_NO_TELEGRAM"] = "1"

    def status(self, usd, now):
        # 시험 시각은 한국시간. 장부 시각(UTC)은 10/13 01:00Z로 고정
        os.environ["CREDIT_LEDGER"] = str(make_ledger(self.tmp, [["2026-10-13T01:00:00Z", "t", "m", usd, 1, 1, "ok"]]))
        c, _ = cdr.run("status", datetime.fromisoformat(now).replace(tzinfo=cdr.KST))
        return c

    def test_four_states(self):
        # 10/16 24시(=10/17 00:00) 최소 25
        self.assertEqual(self.status(40, "2026-10-16T23:59")["status"], "앞섬")
        self.assertEqual(self.status(24, "2026-10-16T23:59")["status"], "정상")
        self.assertEqual(self.status(20, "2026-10-16T23:59")["status"], "지연")
        self.assertEqual(self.status(10, "2026-10-16T23:59")["status"], "위험")
        self.assertEqual(self.status(99, "2026-10-20T10:00")["status"], "완료")

    def test_fail_rows_ignored_and_unpriced_counted(self):
        os.environ["CREDIT_LEDGER"] = str(make_ledger(self.tmp, [
            ["2026-10-13T01:00:00Z", "t", "m", 5, 1, 1, "fail:X"],
            ["2026-10-13T01:00:00Z", "t", "m", 2, 1, 1, "ok:가격미확인"],
            ["2026-10-12T01:00:00Z", "t", "m", 9, 1, 1, "ok"]]))
        c = cdr.compute(datetime(2026, 10, 13, 12, tzinfo=cdr.KST))
        self.assertAlmostEqual(c["spent"], 2.0)
        self.assertEqual(c["unpriced"], 1)

    def test_files_and_exit_code(self):
        os.environ["CREDIT_LEDGER"] = str(make_ledger(self.tmp, []))
        rc = cdr.main(["status", "--now", "2026-10-20T10:00"])
        self.assertEqual(rc, 1)
        d = Path(os.environ["CREDIT_DAILY_DIR"])
        self.assertTrue((d / "credit_actions.md").read_text(encoding="utf-8").count("python") >= 1)
        st = json.loads((d / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(st["status"], "위험")

    def test_console_record(self):
        os.environ["CREDIT_LEDGER"] = str(make_ledger(self.tmp, []))
        cdr.main(["record-console", "--remaining", "90.1", "--source", "시험", "--now", "2026-10-14T10:00"])
        con = json.loads((Path(os.environ["CREDIT_DAILY_DIR"]) / "console_check.json").read_text(encoding="utf-8"))
        self.assertEqual(con["checks"][-1]["remaining_usd"], 90.1)


if __name__ == "__main__":
    unittest.main()
