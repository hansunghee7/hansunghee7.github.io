"""비티 막힘 문구가 안티그래비티 풀만 뜻하고 Vertex(GCP 풀) 경로를 함께 알리는지 고정한다(10/19 사고 재발방지)."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota  # noqa: E402


class BtBlockedWordingTest(unittest.TestCase):
    def test_gcp_hint_present_and_no_sonnet_advice(self):
        self.assertIn("BT_MODEL=vertex", quota.BT_GCP_HINT)
        self.assertIn("비티(GCP 풀", quota.BT_GCP_HINT)
        self.assertEqual(quota.pool_label("비티"), "비티(안티그래비티 풀)")
        self.assertEqual(quota.pool_label("덱스"), "덱스")

    def test_vertex_pool_is_counted_not_blocked(self):
        self.assertIn("비티-vertex", quota.BUDGET)
        self.assertEqual(quota.WHO_MAP["비티-vertex"][0], "비티-vertex")

    def test_blocked_summary_mentions_gcp_pool(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        orig_state, orig_calls = quota.load_state, quota.load_calls
        quota.load_state = lambda: {"비티": {"blocked_until": (now + timedelta(hours=5)).isoformat()}}
        quota.load_calls = lambda n: []
        try:
            worst, lines = quota.summary(now)
        finally:
            quota.load_state, quota.load_calls = orig_state, orig_calls
        self.assertEqual(worst, 1)
        self.assertIn("비티(안티그래비티 풀) 막힘", lines[0])
        self.assertIn("BT_MODEL=vertex", lines[0])


if __name__ == "__main__":
    unittest.main()
