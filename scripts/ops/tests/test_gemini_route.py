"""gemini_route.py 시험. 네트워크·gcloud·키 대장·실제 장부 접근 없음(전부 가짜 함수, 임시 폴더).

실행: python -m pytest scripts/ops/tests/test_gemini_route.py
"""
import datetime
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("gemini_route_under_test", OPS / "gemini_route.py")
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)
import ask_vertex as av  # noqa: E402
import quota  # noqa: E402

FAKE_KEY = "AI" + "za" + "Sy" + "X" * 33  # 키 모양 가짜 값(소스에 통째로 두지 않는다)
FAKE_TOK = "ya" + "29." + "T" * 30
OKJSON = {"candidates": [{"content": {"parts": [{"text": "답입니다"}]},
                          "groundingMetadata": {"groundingChunks": [{"web": {"title": "t", "uri": "https://e.x/a"}}], "webSearchQueries": ["q"]}}],
          "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patches = [mock.patch.object(gr, "ROUTE_LOG", self.tmp / "route.jsonl"),
                   mock.patch.object(av, "LOG", self.tmp / "usage.csv"),
                   mock.patch.object(quota, "STATE", self.tmp / "quota_state.json"),
                   mock.patch.object(gr, "_free_keys", return_value=[("K", FAKE_KEY)]),
                   mock.patch.object(gr, "_token", return_value=FAKE_TOK),
                   mock.patch.object(gr, "_day_krw", return_value=0.0),
                   mock.patch.object(av, "total_since", return_value=0.0),
                   mock.patch.dict("os.environ", {}, clear=False)]
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)
        self.urls = []

    def server(self, plan):
        """plan: URL 일부 -> 상태코드. 200이면 정상 응답."""
        def post(url, headers, body, timeout):
            self.urls.append(url)
            for k, code in plan.items():
                if k in url:
                    return code, (OKJSON if code == 200 else None)
            return 0, None
        return mock.patch.object(gr, "_http_post", side_effect=post)


class Route(Base):
    def test_free_429_then_company_ok(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=True, who="핏")
        self.assertEqual((r["route"], r["status"], r["exit_code"]), ("vertex-company", "ok", 0))
        self.assertEqual(r["sources"][0]["uri"], "https://e.x/a")
        self.assertIn("핏", (self.tmp / "usage.csv").read_text(encoding="utf-8"))
        self.assertTrue(quota.blocked_until(quota.load_state(), "제미나이-무료-검색", datetime.datetime.now()))

    def test_free_company_fail_personal_ok(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 403, "project-e59": 200}):
            r = gr.call("질문", who="탐")
        self.assertEqual((r["route"], r["exit_code"]), ("vertex-personal", 0))
        self.assertEqual([t[0] for t in r["tried"]], ["free", "vertex-company"])

    def test_free_first_success_skips_vertex(self):
        with self.server({"generativelanguage": 200}):
            r = gr.call("질문")
        self.assertEqual(r["route"], "free")
        self.assertFalse(any("aiplatform" in u for u in self.urls))

    def test_day_cap_refuses_vertex(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 200}), \
                mock.patch.object(gr, "_day_krw", return_value=av.DAY_KRW + 1):
            r = gr.call("질문")
        self.assertEqual((r["route"], r["status"], r["exit_code"]), ("none", "capped", 3))
        self.assertFalse(any("aiplatform" in u for u in self.urls))
        self.assertIn("상한", r["text"])

    def test_all_fail_exit_2(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 503, "project-e59": 500}):
            r = gr.call("질문")
        self.assertEqual((r["status"], r["exit_code"]), ("failed", 2))
        self.assertIn("모든 단계 실패", r["text"])

    def test_no_auth_exit_4(self):
        with mock.patch.object(gr, "_free_keys", return_value=[]), mock.patch.object(gr, "_token", return_value=""), self.server({}):
            r = gr.call("질문")
        self.assertEqual(r["exit_code"], 4)

    def test_cli_exit_code(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 503, "project-e59": 500}):
            self.assertEqual(gr.main(["--who", "핏", "--search", "질문"]), 2)

    def test_timeout_env(self):
        seen = []

        def post(url, headers, body, timeout):
            seen.append(timeout)
            return 200, OKJSON
        with mock.patch.object(gr, "_http_post", side_effect=post), mock.patch.dict("os.environ", {"VERTEX_TIMEOUT": "42"}):
            gr.call("질문")
        self.assertEqual(seen, [42])


class NoSecrets(Base):
    def test_no_key_shaped_values_in_return_or_log(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", who="핏")
        blob = json.dumps(r, ensure_ascii=False) + (self.tmp / "route.jsonl").read_text(encoding="utf-8")
        blob += (self.tmp / "usage.csv").read_text(encoding="utf-8") + (self.tmp / "quota_state.json").read_text(encoding="utf-8")
        self.assertNotIn(FAKE_KEY, blob)
        self.assertNotIn(FAKE_TOK, blob)
        self.assertIsNone(gr.KEY_LIKE.search(blob))
        rec = json.loads((self.tmp / "route.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(set(rec), {"time", "who", "route", "status", "ms", "bytes"})

    def test_mask(self):
        self.assertNotIn(FAKE_KEY, gr.mask(f"오류 {FAKE_KEY}"))
        self.assertIsNone(re.search(gr.KEY_LIKE, gr.mask(f"x {FAKE_TOK}")))


if __name__ == "__main__":
    unittest.main()
