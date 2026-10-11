"""vertex_research.py 폴백 순서 시험(회사 -> 개인 -> 검색 없는 무료). 네트워크·gcloud 호출 없음(전부 mock).

실행: python -m pytest scripts/ops/tests/test_vertex_research_fallback.py  (또는 python -m unittest)
ask_vertex·gemini_fast는 가짜 모듈로 바꿔 끼우고, HTTP 호출(post)과 gcloud 토큰(token)은 mock으로 대체한다.
"""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]


def load_module():
    sys.path.insert(0, str(OPS))
    spec = importlib.util.spec_from_file_location("vertex_research_under_test", OPS / "vertex_research.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vr = load_module()
OK = {"text": "답", "sources": [], "usage": {}}


def err(code, msg=None):
    return {"error": msg or f"HTTP {code}", "code": code, "detail": ""}


class Base(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("VERTEX_NO_FAILOVER", None)
        self.av = types.SimpleNamespace(COMPANY_ACCOUNT="company-acct", COMPANY_PROJECT="company-proj", token=mock.Mock(return_value="TOK-company"))
        self.gf = types.SimpleNamespace(ask=mock.Mock(return_value={"ok": True, "text": "무료 답"}))
        p = mock.patch.dict(sys.modules, {"ask_vertex": self.av, "gemini_fast": self.gf})
        p.start()
        self.addCleanup(p.stop)
        self.token = mock.patch.object(vr, "token", return_value="TOK-personal")
        self.token.start()
        self.addCleanup(self.token.stop)
        self.posts = []
        # 기본: 검색 전용 키 없음(실제 키·장부·네트워크 금지). 개별 시험에서 바꾼다.
        self.sk = mock.patch.object(vr, "ask_search_key", return_value=err(0, "검색 키 없음"))
        self.sk_mock = self.sk.start()
        self.addCleanup(self.sk.stop)

    def script_posts(self, *results):
        """post 호출을 순서대로 results로 답하고, 호출된 URL을 self.posts에 쌓는다."""
        it = iter(results)

        def fake(url, headers, body):
            self.posts.append(("company" if "company-proj" in url else "personal" if vr.PROJECT in url else "other", headers.get("Authorization")))
            return next(it)

        p = mock.patch.object(vr, "post", side_effect=fake)
        p.start()
        self.addCleanup(p.stop)

    def batch(self, route="vertex"):
        return vr.ask_batch(["Q1", "Q2"], "공통", "m", route)


class VertexOrder(Base):
    def test_company_success_stops_there(self):
        self.script_posts(dict(OK))
        res = self.batch()
        self.assertEqual(self.posts, [("company", "Bearer TOK-company")])
        self.assertEqual((res["route"], res["project"]), ("vertex", "company"))
        self.gf.ask.assert_not_called()

    def test_company_fail_then_personal(self):
        for code in (401, 402, 403, 429):
            with self.subTest(code=code):
                self.posts.clear()
                self.script_posts(err(code), dict(OK))
                res = self.batch()
                self.assertEqual(self.posts, [("company", "Bearer TOK-company"), ("personal", "Bearer TOK-personal")])
                self.assertEqual(res["project"], "personal")
                self.gf.ask.assert_not_called()

    def test_full_order_company_personal_nosearch(self):
        self.script_posts(err(402), err(403))
        res = self.batch()
        self.assertEqual([p[0] for p in self.posts], ["company", "personal"])
        self.gf.ask.assert_called_once()
        self.assertEqual(res["route"], "free-nosearch")
        self.assertTrue(res["text"].startswith("[검색 없음"))
        self.assertEqual(res["sources"], [])
        self.assertIn("Q1. Q1", self.gf.ask.call_args.args[0])  # 질문 묶음 그대로 전달

    def test_empty_company_token_skips_company(self):
        self.av.token.return_value = ""
        self.script_posts(dict(OK))
        res = self.batch()
        self.assertEqual([p[0] for p in self.posts], ["personal"])
        self.assertEqual(res["project"], "personal")

    def test_company_exception_skips_to_personal(self):
        self.av.token.side_effect = RuntimeError("로그인 만료")
        self.script_posts(dict(OK))
        res = self.batch()
        self.assertEqual([p[0] for p in self.posts], ["personal"])
        self.assertEqual(res["project"], "personal")

    def test_personal_token_exception_goes_to_nosearch(self):
        # 일반 예외(gcloud 토큰 실패)도 code 0 오류로 바뀌어 검색 없는 무료 호출로 넘어간다
        self.av.token.return_value = ""
        vr.token.side_effect = RuntimeError("gcloud 없음")
        self.script_posts()
        res = self.batch()
        self.assertEqual(res["route"], "free-nosearch")

    def test_codes_that_reach_nosearch(self):
        for code in (0, 401, 402, 403, 429, 500, 503):
            with self.subTest(code=code):
                self.gf.ask.reset_mock()
                self.posts.clear()
                self.script_posts(err(code), err(code))
                self.assertEqual(self.batch()["route"], "free-nosearch")

    def test_other_error_code_does_not_fall_to_nosearch(self):
        self.script_posts(err(404), err(404))
        res = self.batch()
        self.gf.ask.assert_not_called()
        self.assertEqual((res["route"], res["error"]), ("vertex", "HTTP 404"))

    def test_nosearch_failure_returns_vertex_error(self):
        self.gf.ask.return_value = {"ok": False, "status": 429}
        self.script_posts(err(403), err(403))
        res = self.batch()
        self.assertEqual((res["route"], res["error"]), ("vertex", "HTTP 403"))

    def test_no_failover_env_blocks_nosearch(self):
        os.environ["VERTEX_NO_FAILOVER"] = "1"
        self.script_posts(err(403), err(403))
        res = self.batch()
        self.gf.ask.assert_not_called()
        self.assertEqual(res["route"], "vertex")
        self.assertIn("error", res)


class RouteSwitch(Base):
    def test_auto_tries_search_key_first(self):
        self.sk_mock.return_value = dict(OK)
        with mock.patch.object(vr, "ask_free") as f, mock.patch.object(vr, "ask_vertex") as v:
            res = self.batch("auto")
        self.sk_mock.assert_called_once()
        f.assert_not_called()
        v.assert_not_called()
        self.assertEqual(res["route"], "search-key")

    def test_auto_search_key_failure_falls_to_vertex(self):
        for e in (err(0, "검색 키 없음"), err(0, "검색 키 cap"), err(429), err(503)):
            with self.subTest(e=e["error"]):
                self.sk_mock.return_value = e
                self.script_posts(dict(OK))
                with mock.patch.object(vr, "ask_free") as f:
                    res = self.batch("auto")
                f.assert_not_called()
                self.assertEqual((res["route"], res["project"]), ("vertex", "company"))

    def test_route_search_key_does_not_continue(self):
        self.sk_mock.return_value = err(429)
        with mock.patch.object(vr, "ask_vertex") as v:
            res = self.batch("search-key")
        v.assert_not_called()
        self.assertEqual((res["route"], res["error"]), ("search-key", "HTTP 429"))

    def test_route_free_does_not_use_search_key(self):
        with mock.patch.object(vr, "ask_free", return_value=dict(OK)):
            res = self.batch("free")
        self.sk_mock.assert_not_called()
        self.assertEqual(res["route"], "free")

    def test_ask_search_key_wraps_gemini_route_stage(self):
        self.sk.stop()
        gr = types.SimpleNamespace(search_key_stage=mock.Mock(return_value=(True, None, (200, {"candidates": [{"content": {"parts": [{"text": "답"}]}}]}, "m", 0))))
        with mock.patch.dict(sys.modules, {"gemini_route": gr}):
            res = vr.ask_search_key(["Q1"], "공통", "m")
            self.assertEqual(res["text"], "답")
            gr.search_key_stage.return_value = (True, ("search-key", "HTTP429"), None)
            self.assertEqual(vr.ask_search_key(["Q1"], "공통", "m")["error"], "검색 키 HTTP429")
            gr.search_key_stage.return_value = (False, None, None)
            self.assertIn("error", vr.ask_search_key(["Q1"], "공통", "m"))
        self.sk.start()

    def test_route_free_does_not_continue_to_vertex(self):
        with mock.patch.object(vr, "ask_free", return_value=err(429)), mock.patch.object(vr, "ask_vertex") as v:
            res = self.batch("free")
        v.assert_not_called()
        self.assertEqual(res["route"], "free")
        self.assertIn("error", res)

    def test_route_vertex_skips_free(self):
        self.script_posts(dict(OK))
        with mock.patch.object(vr, "ask_free") as f:
            self.batch("vertex")
        f.assert_not_called()


if __name__ == "__main__":
    unittest.main()
