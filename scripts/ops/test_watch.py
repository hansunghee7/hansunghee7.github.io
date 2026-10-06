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

    def test_file_age_checks_heartbeat_file(self):
        import os
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False)
        f.close()
        at = datetime.fromtimestamp(os.path.getmtime(f.name) + 60 * 10, tz=KST)
        self.assertEqual(w.check_file_age({"path": f.name, "max_age_min": 45}, at)[0], "ok")
        at = datetime.fromtimestamp(os.path.getmtime(f.name) + 60 * 90, tz=KST)
        self.assertEqual(w.check_file_age({"path": f.name, "max_age_min": 45}, at)[0], "fail")
        self.assertEqual(w.check_file_age({"path": f.name + ".none", "max_age_min": 45}, at)[0], "fail")

    def test_git_checks_grade_lines_and_age(self):
        import subprocess
        import tempfile
        d = tempfile.mkdtemp()
        run = lambda *c: subprocess.run(["git", "-C", d, *c], capture_output=True, check=True, stdin=subprocess.DEVNULL)
        run("init", "-q", "-b", "main")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        open(d + "/F.md", "w").write("\n".join(["x"] * 210))
        run("add", "F.md")
        run("commit", "-q", "-m", "m")
        run("update-ref", "refs/remotes/origin/main", "HEAD")
        w.git_fetch = lambda repo, branch: None  # 원격 없이 시험
        job = {"repo": d, "path": "F.md", "warn_over": 200, "fail_over": 250, "max_age_days": 14}
        self.assertEqual(w.check_git_file_lines(job, T0)[0], "warn")
        self.assertEqual(w.check_git_file_lines(dict(job, warn_over=300, fail_over=400), T0)[0], "ok")
        self.assertEqual(w.check_git_file_lines(dict(job, warn_over=100, fail_over=200), T0)[0], "fail")
        now = datetime.now(KST)
        self.assertEqual(w.check_git_file_age(job, now)[0], "ok")
        self.assertEqual(w.check_git_file_age(job, now + timedelta(days=20))[0], "fail")

    def test_first_run_sends_no_per_item_alerts(self):
        _, a = w.merge_state({}, [{"id": "a", "name": "A", "status": "fail", "detail": "x"}], T0)
        self.assertEqual(a, [])


class BoundaryTest(unittest.TestCase):
    """is_due·merge_state·보조 함수의 경계·실패 입력 시험."""

    def test_parse_iso_returns_none_on_bad_input(self):
        self.assertIsNone(w.parse_iso("not-a-date"))
        self.assertIsNone(w.parse_iso(None))
        self.assertEqual(w.parse_iso(T0.isoformat()), T0)

    def test_is_due_true_for_missing_empty_or_garbage_checked(self):
        self.assertTrue(w.is_due({}, 60, T0))
        self.assertTrue(w.is_due({"checked": ""}, 60, T0))
        self.assertTrue(w.is_due({"checked": "garbage"}, 60, T0))

    def test_is_due_two_minute_tolerance_edges(self):
        prev = {"checked": T0.isoformat()}
        self.assertFalse(w.is_due(prev, 60, T0 + timedelta(minutes=57, seconds=59)))
        self.assertTrue(w.is_due(prev, 60, T0 + timedelta(minutes=58)))
        self.assertTrue(w.is_due(prev, 60, T0 + timedelta(minutes=60)))

    def test_is_due_false_when_clock_goes_backwards(self):
        prev = {"checked": T0.isoformat()}
        self.assertFalse(w.is_due(prev, 60, T0 - timedelta(minutes=10)))

    def test_is_stale_boundary(self):
        edge = 1.5 * 100 + 60  # 210분
        self.assertFalse(w.is_stale(T0, 100, T0 + timedelta(minutes=edge)))
        self.assertTrue(w.is_stale(T0, 100, T0 + timedelta(minutes=edge, seconds=1)))

    def test_infer_period_defaults_and_floor(self):
        self.assertEqual(w.infer_period_min([]), 1440)
        self.assertEqual(w.infer_period_min([T0, T0 + timedelta(hours=1)]), 1440)
        self.assertEqual(w.infer_period_min([T0] * 3), 1440)  # 간격이 전부 0이면 기본값
        self.assertEqual(w.infer_period_min([T0 + timedelta(seconds=10 * i) for i in range(4)]), 1)  # 최소 1분

    def test_merge_state_since_kept_while_status_unchanged_and_reset_on_change(self):
        r = {"id": "a", "name": "A", "status": "fail", "detail": "x"}
        s1, _ = w.merge_state({"a": {"status": "ok", "fails": 0, "since": "old"}}, [r], T0)
        self.assertEqual(s1["a"]["since"], T0.isoformat())
        later = T0 + timedelta(minutes=5)
        s2, _ = w.merge_state(s1, [r], later)
        self.assertEqual(s2["a"]["since"], T0.isoformat())
        self.assertEqual(s2["a"]["fails"], 2)
        self.assertEqual(s2["a"]["checked"], later.isoformat())

    def test_merge_state_warn_is_not_a_failure(self):
        r = {"id": "a", "name": "A", "status": "warn", "detail": "x"}
        prev = {"a": {"status": "fail", "fails": 1, "fail_after": 2}}
        new, alerts = w.merge_state(prev, [r], T0)
        self.assertEqual(new["a"]["fails"], 0)
        self.assertEqual(alerts, [])  # 알림 임계 전 실패였으므로 복구 알림도 없음

    def test_merge_state_down_alert_fires_only_once(self):
        r = {"id": "a", "name": "A", "status": "fail", "detail": "x"}
        state = {"a": {"status": "ok", "fails": 0}}
        kinds = []
        for _ in range(4):
            state, alerts = w.merge_state(state, [r], T0)
            kinds.append([k for k, _ in alerts])
        self.assertEqual(kinds, [[], ["down"], [], []])

    def test_merge_state_recovery_after_alerted_failure_alerts_up(self):
        r = {"id": "a", "name": "A", "status": "ok", "detail": "x"}
        prev = {"a": {"status": "fail", "fails": 3, "fail_after": 2}}
        _, alerts = w.merge_state(prev, [r], T0)
        self.assertEqual([k for k, _ in alerts], ["up"])

    def test_merge_state_empty_prev_never_alerts_even_if_failing(self):
        r = {"id": "a", "name": "A", "status": "fail", "detail": "x", "fail_after": 1}
        new, alerts = w.merge_state({}, [r], T0)
        self.assertEqual(alerts, [])
        self.assertEqual(new["a"]["fails"], 1)

    def test_merge_state_empty_results_gives_empty_state(self):
        self.assertEqual(w.merge_state({"a": {"status": "ok"}}, [], T0), ({}, []))


class DirectAlertTest(unittest.TestCase):
    def test_check_tcp_any_port(self):
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        up = srv.getsockname()[1]
        self.assertEqual(w.check_tcp({"host": "127.0.0.1", "ports": [1, up]}, T0)[0], "ok")
        srv.close()
        self.assertEqual(w.check_tcp({"host": "127.0.0.1", "ports": [1]}, T0)[0], "fail")

    def test_direct_notify_off_by_default(self):
        w.DIRECT_NOTIFY = ""
        self.assertIsNone(w.direct_notify("t", "b"))


if __name__ == "__main__":
    unittest.main()
