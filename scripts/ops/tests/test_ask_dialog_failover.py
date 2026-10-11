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
        self.assertEqual(c({"error": '{"message": "요청이 몰려 20분 뒤 다시"}', "text": ""}), ad.EXIT_LIMIT)
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


    def test_limit_then_no_worker_call_for_20min(self):
        with tempfile.TemporaryDirectory() as d:
            fb = {"text": "폴백답", "error": None, "sources": [], "route": "fallback"}
            with mock.patch.object(ad, "STATE_FILE", Path(d) / "s.json"), \
                 mock.patch.object(ad, "fallback", return_value=fb), \
                 mock.patch.object(ad, "ask", return_value={"text": "", "error": "HTTP 429 x"}) as a:
                ad.ask_with_failover("q")          # 한도 -> 상태 파일 기록
                self.assertEqual(a.call_count, 1)
                ad.ask_with_failover("q")          # 휴식 중 -> Worker 미호출
                self.assertEqual(a.call_count, 1)
                self.assertFalse(list(Path(d).glob("*.tmp")))
                self.assertTrue(ad.worker_resting(now=__import__("time").time() + 1100))
                self.assertFalse(ad.worker_resting(now=__import__("time").time() + 1300))

    def test_corrupt_state_means_no_rest(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text("{깨짐", encoding="utf-8")
            with mock.patch.object(ad, "STATE_FILE", p):
                self.assertFalse(ad.worker_resting())

    def test_render_fallback_without_log_id(self):
        out = {"time": "t", "question": "q", "text": "a", "sources": [{"title": "x.md", "similarity": None, "source_url": "u"}],
               "error": None, "route": "fallback"}
        s = ad.render(out)
        self.assertTrue(s.rstrip().splitlines()[-1].startswith("### 경로: fallback"))  # 경로 줄은 맨 끝 한 줄
        ad.render({"question": "q", "text": "", "sources": []})  # 필드 누락도 통과

    def test_classify_no_misfire(self):
        c = ad.classify
        self.assertEqual(c({"error": "HTTP 500 서버 오류, 20분 전 배포", "text": ""}), ad.EXIT_OTHER)
        self.assertEqual(c({"error": "연결 실패 (20분 전 점검)", "text": ""}), ad.EXIT_OTHER)
        self.assertEqual(c({"error": "HTTP 429 x", "text": ""}), ad.EXIT_LIMIT)

    def test_title_weight_and_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "001_기획자의 질문.md").write_text(
                "---\ntitle: 기획자의 질문\n---\n\n좋은 질문 하나가 회의의 방향을 바꾸는 순간을 오래 지켜보았습니다 정말로요.\n", encoding="utf-8")
            (Path(d) / "002_다른글.md").write_text(
                "---\ntitle: 다른글\n---\n\n기획자 회의에서 질문 질문 질문이 반복되며 길게 이어지는 아무 말 문단입니다 아무 말 아무 말.\n", encoding="utf-8")
            r = ad.search_local("기획자 질문", dirs=[Path(d)])
            self.assertEqual(r[0][0], "001_기획자의 질문.md")
        self.assertIn("1인칭", ad.build_prompt("q", []))


if __name__ == "__main__":
    unittest.main()
