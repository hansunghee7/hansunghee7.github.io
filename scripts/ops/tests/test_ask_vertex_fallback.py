"""ask_vertex.py 크레딧 소진 대비 폴백 시험. 네트워크·gcloud 호출 없음(전부 mock).

실행: python -m pytest scripts/ops/tests/test_ask_vertex_fallback.py  (또는 python -m unittest)
시험하는 것
  - 회사 프로젝트가 401·402·403·429면 개인 프로젝트로 한 번 더, 개인도 막히면 무료 폴백(free_failover)
  - 일반 예외(네트워크 등)도 무료 폴백
  - 환경변수 VERTEX_NO_COMPANY, VERTEX_NO_FAILOVER
  - free_failover 자체: 라우터 먼저, 다음 무료 키(호출 적은 순), 모델 대체, 전부 막히면 종료 코드 2
계정·키 값은 쓰지 않는다(모듈 상수와 가짜 이름만).
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

OPS = Path(__file__).resolve().parents[1]


def load_module():
    sys.path.insert(0, str(OPS))
    spec = importlib.util.spec_from_file_location("ask_vertex_under_test", OPS / "ask_vertex.py")
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, {"VERTEX_DAY_KRW": "4100"}):  # 한도 계산이 다른 모듈을 읽지 않게
        spec.loader.exec_module(mod)
    return mod


av = load_module()
OK_BODY = json.dumps({"candidates": [{"content": {"parts": [{"text": "답"}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}).encode()


class FakeResp:
    def read(self):
        return OK_BODY


def http_error(code):
    return urllib.error.HTTPError("https://example.invalid", code, "x", {}, io.BytesIO(b"{}"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        (tmp / "q.md").write_text("질문", encoding="utf-8")
        self.q, self.out = tmp / "q.md", tmp / "out" / "a.md"
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for k in ("VERTEX_NO_COMPANY", "VERTEX_NO_FAILOVER", "VERTEX_NO_ROUTER"):
            os.environ.pop(k, None)
        # 사용량 기록·상한 계산은 임시 폴더와 고정값으로
        self.patches = {
            "LOG": mock.patch.object(av, "LOG", tmp / "vertex_usage.csv"),
            "today": mock.patch.object(av, "today_use", return_value=(0, 0.0, 0.0, 0.0)),
            "total": mock.patch.object(av, "total_since", return_value=0.0),
            "gcp": mock.patch.dict(sys.modules, {"gcp_usage": types.SimpleNamespace(today_krw=lambda: 0.0)}),
            "failover": mock.patch.object(av, "free_failover", return_value=0),
        }
        self.m = {k: p.start() for k, p in self.patches.items()}
        for p in self.patches.values():
            self.addCleanup(p.stop)
        self.token = mock.patch.object(av, "token", side_effect=lambda account=None: "TOK-company" if account == av.COMPANY_ACCOUNT else "TOK-personal")
        self.tok = self.token.start()
        self.addCleanup(self.token.stop)

    def run_main(self, urlopen_effects):
        argv = ["ask_vertex.py", str(self.q), str(self.out), "--who", "시험"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(av.urllib.request, "urlopen", side_effect=urlopen_effects) as uo:
            rc = av.main()
        self.urls = [c.args[0].full_url for c in uo.call_args_list]
        return rc

    def projects_called(self):
        return ["company" if av.COMPANY_PROJECT in u else "personal" if av.PROJECT in u else "?" for u in self.urls]


class CompanyToPersonal(Base):
    def test_company_error_codes_retry_on_personal(self):
        for code in (401, 402, 403, 429):
            with self.subTest(code=code):
                os.environ.pop("VERTEX_NO_COMPANY", None)  # 재시도가 켜 둔 값을 다음 반복에서 지운다
                self.m["failover"].reset_mock()
                rc = self.run_main([http_error(code), FakeResp()])
                self.assertEqual(rc, 0)
                self.assertEqual(self.projects_called(), ["company", "personal"])
                self.m["failover"].assert_not_called()
                self.assertEqual(self.out.read_text(encoding="utf-8"), "답")

    def test_company_other_codes_do_not_retry_personal(self):
        # 404는 재시도도 폴백도 없음(rc 2), 500·503은 개인 재시도 없이 바로 무료 폴백
        os.environ.pop("VERTEX_NO_COMPANY", None)
        self.assertEqual(self.run_main([http_error(404)]), 2)
        self.assertEqual(self.projects_called(), ["company"])
        self.m["failover"].assert_not_called()
        for code in (500, 503):
            with self.subTest(code=code):
                os.environ.pop("VERTEX_NO_COMPANY", None)
                self.m["failover"].reset_mock()
                self.run_main([http_error(code)])
                self.assertEqual(self.projects_called(), ["company"])
                self.assertEqual(self.m["failover"].call_args.args[3], f"HTTP{code}")

    def test_empty_company_token_goes_straight_to_personal(self):
        self.tok.side_effect = lambda account=None: "" if account == av.COMPANY_ACCOUNT else "TOK-personal"
        self.assertEqual(self.run_main([FakeResp()]), 0)
        self.assertEqual(self.projects_called(), ["personal"])


class PersonalToFree(Base):
    def test_personal_403_after_company_403_triggers_free_failover(self):
        self.m["failover"].return_value = 0
        self.run_main([http_error(403), http_error(403)])
        self.assertEqual(self.projects_called(), ["company", "personal"])
        self.m["failover"].assert_called_once()
        a, out, prompt, reason = self.m["failover"].call_args.args
        self.assertEqual((reason, prompt), ("HTTP403", "질문"))
        self.assertEqual(out, self.out)

    def test_failover_return_code_is_passed_through(self):
        os.environ["VERTEX_NO_COMPANY"] = "1"
        self.m["failover"].return_value = 2
        self.assertEqual(self.run_main([http_error(402)]), 2)

    def test_personal_codes_that_trigger_failover(self):
        os.environ["VERTEX_NO_COMPANY"] = "1"
        for code in (401, 402, 403, 429, 500, 503):
            with self.subTest(code=code):
                self.m["failover"].reset_mock()
                self.run_main([http_error(code)])
                self.assertEqual(self.m["failover"].call_args.args[3], f"HTTP{code}")

    def test_unlisted_code_is_plain_failure(self):
        os.environ["VERTEX_NO_COMPANY"] = "1"
        self.assertEqual(self.run_main([http_error(400)]), 2)
        self.m["failover"].assert_not_called()


class GeneralException(Base):
    def test_network_error_falls_back_to_free(self):
        os.environ["VERTEX_NO_COMPANY"] = "1"
        self.run_main([urllib.error.URLError("연결 실패")])
        self.assertEqual(self.m["failover"].call_args.args[3], "URLError")

    def test_empty_personal_token_ends_in_401_then_free(self):
        # 토큰 발급이 빈 문자열을 돌려주면 Bearer 헤더만 비어 401 -> 무료 폴백
        self.tok.side_effect = lambda account=None: ""
        self.run_main([http_error(401)])
        self.assertEqual(self.m["failover"].call_args.args[3], "HTTP401")

    @unittest.expectedFailure
    def test_token_issuing_exception_falls_back_to_free(self):
        # 현재 코드의 빈틈: token() 호출이 try 밖(main의 토큰 줄)이라, gcloud가 없어서 token()이 예외를 내면
        # 무료 폴백 없이 main이 그대로 죽는다. 고치면 이 시험이 통과로 바뀌고 expectedFailure 표시를 지우면 된다.
        self.tok.side_effect = TypeError("gcloud 없음")
        self.run_main([FakeResp()])
        self.m["failover"].assert_called_once()


class EnvSwitches(Base):
    def test_no_company_skips_company_token_and_project(self):
        os.environ["VERTEX_NO_COMPANY"] = "1"
        self.assertEqual(self.run_main([FakeResp()]), 0)
        self.assertEqual(self.projects_called(), ["personal"])
        self.assertNotIn(mock.call(av.COMPANY_ACCOUNT), self.tok.call_args_list)

    def test_no_failover_returns_error_instead_of_free_path(self):
        os.environ["VERTEX_NO_COMPANY"] = "1"
        os.environ["VERTEX_NO_FAILOVER"] = "1"
        self.assertEqual(self.run_main([http_error(403)]), 2)
        self.m["failover"].assert_not_called()
        self.assertEqual(self.run_main([urllib.error.URLError("x")]), 2)
        self.m["failover"].assert_not_called()

    def test_no_failover_does_not_block_company_to_personal_retry(self):
        os.environ["VERTEX_NO_FAILOVER"] = "1"
        self.assertEqual(self.run_main([http_error(402), FakeResp()]), 0)
        self.assertEqual(self.projects_called(), ["company", "personal"])

    def test_caps_use_free_failover_unless_disabled(self):
        self.m["total"].return_value = av.TOTAL_KRW + 1
        self.m["failover"].return_value = 0
        self.assertEqual(self.run_main([]), 0)
        self.assertEqual(self.m["failover"].call_args.args[3], "누적상한")
        self.m["total"].return_value = 0.0
        self.m["today"].return_value = (0, av.DAY_KRW + 1, 0.0, 0.0)
        self.assertEqual(self.run_main([]), 0)
        self.assertEqual(self.m["failover"].call_args.args[3], "일상한")
        self.m["failover"].reset_mock()
        os.environ["VERTEX_NO_FAILOVER"] = "1"
        self.assertEqual(self.run_main([]), 3)
        self.m["failover"].assert_not_called()


class FreeFailoverBody(unittest.TestCase):
    """free_failover 자체(가짜 gemini_fast·omni_gateway 주입)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cwd = os.getcwd()
        os.chdir(self.tmp.name)  # vertex_failover.csv(고정 경로)가 임시 폴더 아래로 가게
        os.makedirs("C:/work/_ops")  # 코드는 이 폴더를 만들지 않는다(운영 PC에는 이미 있음)
        self.addCleanup(os.chdir, cwd)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("VERTEX_NO_ROUTER", None)
        self.out = Path(self.tmp.name) / "out" / "a.md"
        self.calls = []
        counts = {"k_busy": 5, "k_idle": 0}
        keys = [{"fp": "k_busy", "value": "x"}, {"fp": "k_idle", "value": "x"}]
        self.results = {}  # (모델, fp) -> 결과
        g = types.SimpleNamespace(
            DEFAULT_MODEL="default-free",
            load_keys=lambda: keys,
            read_counter=lambda: {"day": {k: {"calls": n} for k, n in counts.items()}},
            today_pt=lambda: "day",
            call=self._call,
        )
        self.og = types.SimpleNamespace(chat=mock.Mock(return_value={"ok": False}))
        p = mock.patch.dict(sys.modules, {"gemini_fast": g, "omni_gateway": self.og})
        p.start()
        self.addCleanup(p.stop)

    def _call(self, key, prompt, model, search=False):
        self.calls.append((key["fp"], model, search))
        return self.results.get((model, key["fp"]), {"ok": False, "status": 429})

    def ns(self, **kw):
        return SimpleNamespace(search=False, model="req-model", who="시험", **kw)

    def test_router_first_and_no_key_calls(self):
        self.og.chat.return_value = {"ok": True, "text": "라우터 답", "model": "m1"}
        self.assertEqual(av.free_failover(self.ns(), self.out, "질문", "HTTP403"), 0)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "라우터 답")
        self.assertEqual(self.calls, [])
        self.assertIn("HTTP403,router:m1", "".join(Path("C:/work/_ops/vertex_failover.csv").read_text(encoding="utf-8").splitlines()[1:]).replace(" ", ""))

    def test_router_failure_then_least_used_key_first(self):
        self.results[("req-model", "k_idle")] = {"ok": True, "text": "키 답"}
        self.assertEqual(av.free_failover(self.ns(), self.out, "질문", "일상한"), 0)
        self.assertEqual(self.calls, [("k_idle", "req-model", False)])  # 호출 적은 키부터, 성공하면 멈춤
        self.assertEqual(self.out.read_text(encoding="utf-8"), "키 답")

    def test_falls_back_to_default_model_after_requested_model_fails(self):
        self.results[("default-free", "k_busy")] = {"ok": True, "text": "기본 모델 답"}
        self.assertEqual(av.free_failover(self.ns(), self.out, "질문", "HTTP429"), 0)
        self.assertEqual([c[:2] for c in self.calls], [("k_idle", "req-model"), ("k_busy", "req-model"), ("k_idle", "default-free"), ("k_busy", "default-free")])

    def test_all_blocked_returns_2_and_records_failure(self):
        self.assertEqual(av.free_failover(self.ns(), self.out, "질문", "HTTP403"), 2)
        self.assertFalse(self.out.exists())
        self.assertTrue(Path("C:/work/_ops/vertex_failover.csv").read_text(encoding="utf-8").rstrip().endswith(",0"))

    def test_router_skipped_for_search_and_when_disabled(self):
        self.results[("req-model", "k_idle")] = {"ok": True, "text": "x"}
        av.free_failover(SimpleNamespace(search=True, model="req-model", who="시험"), self.out, "질문", "r")
        self.og.chat.assert_not_called()
        self.assertTrue(self.calls[0][2])  # 검색 옵션은 키 호출로 그대로 전달
        os.environ["VERTEX_NO_ROUTER"] = "1"
        av.free_failover(self.ns(), self.out, "질문", "r")
        self.og.chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
