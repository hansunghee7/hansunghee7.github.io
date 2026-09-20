import unittest
import urllib.error
from datetime import date
from unittest import mock

import fetch_youtube_analytics as fya

RESP = {
    "columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "averageViewPercentage"}],
    "rows": [["abc", 120, 61.5], ["def", 30, 40.0]],
}


class T(unittest.TestCase):
    def test_rows_to_dicts(self):
        self.assertEqual(fya.rows_to_dicts(RESP)[0], {"video": "abc", "views": 120, "averageViewPercentage": 61.5})
        self.assertEqual(fya.rows_to_dicts({"columnHeaders": [{"name": "views"}]}), [])

    def test_fallback_on_400(self):
        calls = []

        def fake(token, params):
            calls.append(params["metrics"])
            if len(calls) == 1:
                raise urllib.error.HTTPError("u", 400, "bad", {}, __import__("io").BytesIO(b"unsupported combination"))
            return RESP

        with mock.patch.object(fya, "query", fake):
            rows, used = fya.run_report("t", {}, [["a", "b", "c"], ["a"]], "시험")
        self.assertEqual(len(rows), 2)
        self.assertEqual(used, ["a"])
        self.assertEqual(calls, ["a,b,c", "a"])

    def test_no_fallback_on_403(self):
        def fake(token, params):
            raise urllib.error.HTTPError("u", 403, "no", {}, __import__("io").BytesIO(b"forbidden"))

        with mock.patch.object(fya, "query", fake):
            rows, used = fya.run_report("t", {}, [["a"], ["b"]], "시험")
        self.assertIsNone(rows)

    def test_window_ends_yesterday(self):
        seen = []

        def fake(token, params):
            seen.append((params["startDate"], params["endDate"]))
            return RESP

        with mock.patch.object(fya, "query", fake):
            snap = fya.collect("t", date(2026, 9, 21))
        self.assertEqual(seen[0], ("2026-08-24", "2026-09-20"))
        self.assertEqual(set(snap["reports"]), {"videos", "traffic", "daily"})

    def test_merge_keeps_previous_report_when_missing(self):
        old = {"snapshots": {"2026-09-21": {"reports": {"traffic": [{"x": 1}]}}}}
        out = fya.merge_snapshot(old, "2026-09-21", {"window": {}, "reports": {"videos": [{"v": 1}]}}, "now")
        self.assertEqual(out["snapshots"]["2026-09-21"]["reports"]["traffic"], [{"x": 1}])
        self.assertEqual(out["snapshots"]["2026-09-21"]["reports"]["videos"], [{"v": 1}])

    def test_merge_trims_old_snapshots(self):
        old = {"snapshots": {f"2026-01-{d:02d}": {"reports": {}} for d in range(1, 31)}}
        old["snapshots"].update({f"2026-02-{d:02d}": {"reports": {}} for d in range(1, 29)})
        old["snapshots"].update({f"2026-03-{d:02d}": {"reports": {}} for d in range(1, 32)})
        out = fya.merge_snapshot(old, "2026-04-01", {"window": {}, "reports": {}}, "now")
        self.assertEqual(len(out["snapshots"]), fya.KEEP_SNAPSHOTS)
        self.assertIn("2026-04-01", out["snapshots"])


if __name__ == "__main__":
    unittest.main()
