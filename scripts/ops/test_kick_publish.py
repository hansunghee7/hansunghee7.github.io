"""kick_publish.py의 결정 로직 시험(외부 호출 없음)."""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("kick_publish", Path(__file__).parent / "kick_publish.py")
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def run_at(minutes_ago, status="completed"):
    t = (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"status": status, "createdAt": t}


class KickTest(unittest.TestCase):
    def test_recent_run_means_github_is_fine_so_skip(self):
        self.assertEqual(k.decide([run_at(7)], NOW)[0], "skip")

    def test_stale_last_run_means_github_missed_so_kick(self):
        action, why = k.decide([run_at(60)], NOW)
        self.assertEqual(action, "kick")
        self.assertIn("누락", why)

    def test_running_or_queued_is_never_kicked(self):
        self.assertEqual(k.decide([run_at(90), run_at(1, "in_progress")], NOW)[0], "skip")
        self.assertEqual(k.decide([run_at(90, "queued")], NOW)[0], "skip")

    def test_no_history_kicks(self):
        self.assertEqual(k.decide([], NOW)[0], "kick")

    def test_uses_most_recent_run_not_first_in_list(self):
        self.assertEqual(k.decide([run_at(200), run_at(5)], NOW)[0], "skip")


if __name__ == "__main__":
    unittest.main()
