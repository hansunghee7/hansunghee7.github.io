"""ask_dialog 폴백 단위 시험(네트워크·라우터 호출 없음)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ask_dialog as ad


class T(unittest.TestCase):
    def test_classify(self):
        c = ad.classify
        self.assertEqual(c({"error": "HTTP 429 x", "text": ""}), ad.EXIT_LIMIT)
        self.assertEqual(c({"error": '{"message": "20분 뒤 다시"}', "text": ""}), ad.EXIT_LIMIT)
        self.assertEqual(c({"error": "HTTP 403 error code: 1010", "text": ""}), ad.EXIT_BLOCKED)
        self.assertEqual(c({"error": "The read operation timed out", "text": ""}), ad.EXIT_TIMEOUT)
        self.assertEqual(c({"error": None, "text": " "}), ad.EXIT_EMPTY)
        self.assertEqual(c({"error": None, "text": "답"}), ad.EXIT_OK)

    def test_state_file(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ad, "STATE_FILE", Path(d) / "s.json"):
                self.assertFalse(ad.worker_resting())
                ad.set_rest(now=1000)
                self.assertTrue(ad.worker_resting(now=1000 + 60))
                self.assertFalse(ad.worker_resting(now=1000 + 1300))

    def test_failover_selection(self):
        fb = {"text": "폴백답", "error": None, "sources": [], "route": "fallback"}
        with mock.patch.object(ad, "worker_resting", return_value=True), \
             mock.patch.object(ad, "ask") as a, mock.patch.object(ad, "fallback", return_value=fb):
            out, code = ad.ask_with_failover("q")
            a.assert_not_called()  # 휴식 중엔 Worker를 부르지 않는다
            self.assertEqual((out["route"], code), ("fallback", 0))
        with mock.patch.object(ad, "worker_resting", return_value=False), \
             mock.patch.object(ad, "ask", return_value={"text": "ok", "error": None}), \
             mock.patch.object(ad, "fallback") as f:
            out, code = ad.ask_with_failover("q")
            f.assert_not_called()
            self.assertEqual((out["route"], code), ("worker", 0))
        with mock.patch.object(ad, "worker_resting", return_value=False), mock.patch.object(ad, "set_rest") as sr, \
             mock.patch.object(ad, "ask", return_value={"text": "", "error": "HTTP 429"}), \
             mock.patch.object(ad, "fallback", return_value={"text": "", "error": "x", "sources": []}):
            out, code = ad.ask_with_failover("q")
            sr.assert_called_once()
            self.assertEqual(code, ad.EXIT_LIMIT)

    def test_search_and_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.md").write_text(
                "---\ntitle: x\n---\n\n기획자는 질문을 먼저 던져야 합니다. 질문이 좋으면 기획의 방향이 달라집니다.\n\n"
                "무관한 문단입니다 점심 메뉴와 날씨 이야기만 길게 적습니다 하하하 하하하.\n", encoding="utf-8")
            r = ad.search_local("기획자의 질문", dirs=[Path(d)])
            self.assertEqual(r[0][0], "a.md")
            self.assertIn("[발췌 1]", ad.build_prompt("q", r))


if __name__ == "__main__":
    unittest.main()
