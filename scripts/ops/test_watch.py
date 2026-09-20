"""watch.py의 순수 계산 시험(외부 호출 없음)."""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("watch", Path(__file__).parent / "watch.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
KST = timezone(timedelta(hours=9))
T0 = datetime(2026, 9, 20, 12, 0, tzinfo=KST)

CRON = """\x1b[1m  Name:      health-check\x1b[0m
    Schedule:  every 30m
    Next run:  2026-09-20T20:22:24+09:00
    Last run:  2026-09-20T19:52:24+09:00  ok
  Name:      model-roster-review
    Schedule:  0 19 * * 6
    Next run:  2026-09-26T19:00:00+09:00
  Name:      prompt: Stagnation detector - check for stalled wo
    Last run:  2026-09-20T08:07:12+09:00  ok
"""


class WatchTest(unittest.TestCase):
    def test_parse_hermes_cron(self):
        j = w.parse_hermes_cron(CRON)
        self.assertEqual(j["health-check"]["last_status"], "ok")
        self.assertNotIn("last", j["model-roster-review"])
        self.assertEqual(w.find_by_name(j, "prompt: Stagnation detector")["last_status"], "ok")

    def test_never_ran_with_future_next_is_pending_not_fail(self):
        j = w.parse_hermes_cron(CRON)
        st, _ = w.check_hermes({"name": "model-roster-review", "period_min": 10080}, j, T0)
        self.assertEqual(st, "pending")

    def test_stale_hermes_job_fails(self):
        j = w.parse_hermes_cron(CRON)
        at = datetime(2026, 9, 20, 22, 0, tzinfo=KST)  # 마지막 실행 19:52, 주기 30분
        self.assertEqual(w.check_hermes({"name": "health-check", "period_min": 30}, j, at)[0], "fail")

    def test_missing_cron_fails(self):
        self.assertEqual(w.check_hermes({"name": "nope"}, {}, T0)[0], "fail")

    def test_infer_period_uses_median_gap(self):
        ts = [T0 + timedelta(days=i) for i in range(5)]
        self.assertEqual(w.infer_period_min(ts), 1440)
        self.assertEqual(w.infer_period_min(ts[:2]), 1440)  # 표본 부족은 기본값

    def test_is_stale_uses_one_and_half_periods_plus_grace(self):
        self.assertFalse(w.is_stale(T0, 1440, T0 + timedelta(hours=30)))
        self.assertTrue(w.is_stale(T0, 1440, T0 + timedelta(hours=40)))

    def test_alert_fires_on_second_consecutive_failure_and_on_recovery(self):
        r = {"id": "a", "name": "A", "status": "fail", "detail": "x"}
        s1, a1 = w.merge_state({"a": {"status": "ok", "fails": 0}}, [r], T0)
        self.assertEqual(a1, [])  # 첫 실패는 알리지 않음(깜빡임 방지)
        s2, a2 = w.merge_state(s1, [r], T0)
        self.assertEqual([k for k, _ in a2], ["down"])
        s3, a3 = w.merge_state(s2, [dict(r, status="ok")], T0)
        self.assertEqual([k for k, _ in a3], ["up"])

    def test_is_due_respects_each_jobs_own_interval(self):
        prev = {"checked": T0.isoformat()}
        self.assertFalse(w.is_due(prev, 60, T0 + timedelta(minutes=15)))
        self.assertTrue(w.is_due(prev, 60, T0 + timedelta(minutes=58)))
        self.assertTrue(w.is_due(None, 60, T0))

    def test_reused_result_keeps_state_and_never_alerts(self):
        prev = {"a": {"id": "a", "name": "A", "status": "fail", "detail": "x", "fails": 1, "since": "s", "checked": "c"}}
        new, alerts = w.merge_state(prev, [{**prev["a"], "reused": True}], T0)
        self.assertEqual(new["a"]["fails"], 1)
        self.assertEqual(alerts, [])

    def test_fail_after_one_alerts_on_first_failure(self):
        r = {"id": "d", "name": "D", "status": "fail", "detail": "x", "fail_after": 1}
        _, alerts = w.merge_state({"d": {"status": "ok", "fails": 0}}, [r], T0)
        self.assertEqual([k for k, _ in alerts], ["down"])

    def test_first_run_sends_no_per_item_alerts(self):
        _, a = w.merge_state({}, [{"id": "a", "name": "A", "status": "fail", "detail": "x"}], T0)
        self.assertEqual(a, [])


if __name__ == "__main__":
    unittest.main()
