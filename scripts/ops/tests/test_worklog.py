"""worklog.py 단위 시험. 운영 DB(opsdb)의 insert·select는 mock으로 대체한다(DB·네트워크 접속 없음).
비밀값 모양 문자열은 소스에 그대로 적지 않고 실행 중에 조립한다(저장소 유출 검사 오탐 방지).

실행: python -m pytest scripts/ops/tests/test_worklog.py  (또는 python -m unittest)
"""
import contextlib
import importlib.util
import io
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("worklog_under_test", OPS / "worklog.py")
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

FAKE_SECRETS = {
    "sk": "sk-" + "a" * 12,
    "aiza": "AI" + "za" + "b" * 22,
    "sb": "sb_" + "secret_" + "x",
    "ghp": "gh" + "p_" + "c" * 10,
    "pem": "-----" + "BEGIN KEY",
}


def ns(**kw):
    base = dict(who="핏", text=["대본", "3편", "검증"], task=None, evidence=None)
    base.update(kw)
    return type("A", (), base)()


class Add(unittest.TestCase):
    def setUp(self):
        self.insert = mock.patch.object(wl.opsdb, "insert").start()
        self.addCleanup(mock.patch.stopall)

    def test_valid_row_shape(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            wl.add(ns(task="N66", evidence="로그/a.txt"))
        table, rows = self.insert.call_args.args
        self.assertEqual(table, "tasks")
        r = rows[0]
        self.assertEqual((r["owner"], r["section"], r["no"], r["title"], r["status"], r["evidence"], r["source"]),
                         ("핏", "worklog", "N66", "대본 3편 검증", "기록", "로그/a.txt", "agent-log"))
        self.assertEqual(r["raw"]["source"], "agent-log")
        self.assertEqual(r["source_date"], datetime.now().strftime("%Y-%m-%d"))
        self.assertIn("기록함: [핏] 대본 3편 검증", buf.getvalue())

    def test_task_defaults_to_empty_string(self):
        with contextlib.redirect_stdout(io.StringIO()):
            wl.add(ns())
        self.assertEqual(self.insert.call_args.args[1][0]["no"], "")

    def test_every_allowed_name_works_and_others_are_rejected(self):
        for who in sorted(wl.WHO):
            with self.subTest(who=who), contextlib.redirect_stdout(io.StringIO()):
                wl.add(ns(who=who))
        n = self.insert.call_count
        for bad in ("누구", "", "TAM"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                wl.add(ns(who=bad))
        self.assertEqual(self.insert.call_count, n)

    def test_length_limits(self):
        with contextlib.redirect_stdout(io.StringIO()):
            wl.add(ns(text=["가" * 300]))  # 300자는 통과
        self.assertEqual(self.insert.call_count, 1)
        for bad in (["가" * 301], [""], ["   "], []):
            with self.subTest(n=len(" ".join(bad))), self.assertRaises(SystemExit):
                wl.add(ns(text=bad))
        self.assertEqual(self.insert.call_count, 1)

    def test_secret_shapes_rejected_in_text_and_evidence(self):
        for name, s in FAKE_SECRETS.items():
            with self.subTest(where="text", name=name), self.assertRaises(SystemExit):
                wl.add(ns(text=["메모", s]))
            with self.subTest(where="evidence", name=name), self.assertRaises(SystemExit):
                wl.add(ns(evidence=s))
        self.insert.assert_not_called()

    def test_ordinary_words_are_not_mistaken_for_secrets(self):
        with contextlib.redirect_stdout(io.StringIO()):
            wl.add(ns(text=["sk-", "짧은", "토큰 설명은 그대로 통과"]))
        self.insert.assert_called_once()


class Rows(unittest.TestCase):
    def setUp(self):
        self.select = mock.patch.object(wl.opsdb, "select", return_value=[]).start()
        self.addCleanup(mock.patch.stopall)

    def test_query_shape_and_default_days(self):
        wl.rows()
        args, kw = self.select.call_args
        self.assertEqual(args[:2], ("tasks", "owner,no,title,evidence,source_date,raw"))
        where = kw["where"]
        self.assertEqual(where["section"], "eq.worklog")
        self.assertNotIn("owner", where)
        self.assertEqual(where["source_date"], "gte." + (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"))
        self.assertEqual((kw["order"], kw["limit"]), ("id.desc", 200))

    def test_who_and_days_filters(self):
        wl.rows("마야", 1)
        where = self.select.call_args.kwargs["where"]
        self.assertEqual(where["owner"], "eq.마야")
        self.assertEqual(where["source_date"], "gte." + (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))


class Out(io.StringIO):
    def reconfigure(self, **kw):  # worklog.main()이 표준출력 인코딩을 바꾸려고 부른다
        pass


class Cli(unittest.TestCase):
    def setUp(self):
        self.insert = mock.patch.object(wl.opsdb, "insert").start()
        self.select = mock.patch.object(wl.opsdb, "select").start()
        self.addCleanup(mock.patch.stopall)

    def run_cli(self, *argv):
        buf = Out()
        with mock.patch.object(sys, "argv", ["worklog.py", *argv]), contextlib.redirect_stdout(buf):
            wl.main()
        return buf.getvalue()

    def test_add_via_cli(self):
        out = self.run_cli("add", "--who", "지투", "--task", "N1", "로고", "수정")
        self.assertEqual(self.insert.call_args.args[1][0]["title"], "로고 수정")
        self.assertIn("기록함: [지투]", out)

    def test_add_requires_who(self):
        with mock.patch.object(sys, "argv", ["worklog.py", "add", "내용"]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                wl.main()

    def test_list_prints_lines_and_count(self):
        self.select.return_value = [
            {"owner": "핏", "no": "N66", "title": "검증", "evidence": "a.log", "source_date": "2026-10-05", "raw": {"at": "2026-10-05 09:00:00"}},
            {"owner": "탐", "no": "", "title": "정리", "evidence": None, "source_date": "2026-10-05", "raw": {}},
        ]
        out = self.run_cli("list", "--who", "핏", "--days", "5").splitlines()
        self.assertEqual(out[0], "2026-10-05 09:00:00  [핏] N66 검증  (증거 a.log)")
        self.assertEqual(out[1], "2026-10-05  [탐] 정리")  # 시각이 없으면 날짜, 번호·증거가 없으면 생략
        self.assertEqual(out[2], "-- 2건")
        where = self.select.call_args.kwargs["where"]
        self.assertEqual(where["owner"], "eq.핏")
        self.assertEqual(where["source_date"], "gte." + (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))

    def test_today_uses_one_day_window(self):
        self.select.return_value = []
        out = self.run_cli("today")
        self.assertEqual(out.strip(), "-- 0건")
        self.assertEqual(self.select.call_args.kwargs["where"]["source_date"], "gte." + (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))


if __name__ == "__main__":
    unittest.main()
