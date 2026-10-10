"""gemini_web.py 시험. ssh·브라우저·실제 장부 접근 없음(원격 실행은 가짜 응답, 임시 폴더).

실행: python -m pytest scripts/ops/tests/test_gemini_web.py
시험하는 것: 하루 상한, 호출 간격, 차단 문구 시 그 계정만 중지(다른 계정은 계속), 출처 파싱, 질문 길이 제한,
            라우터 낙하 순서(기본 꺼짐 / 켜면 무료 키 뒤·Vertex 앞 / 웹 실패 시 Vertex로 낙하 / 검색 아닌 요청은 건너뜀).
"""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
import gemini_web as gw  # noqa: E402

spec = importlib.util.spec_from_file_location("gemini_route_under_test2", OPS / "gemini_route.py")
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)
import ask_vertex as av  # noqa: E402
import quota  # noqa: E402

OK = {"status": "ok", "text": "오늘은 2026-10-11 입니다", "sources": [{"title": "달력", "uri": "https://e.x/cal"}, {"title": "x", "uri": ""}], "secs": 12, "note": ""}
OKJSON = {"candidates": [{"content": {"parts": [{"text": "버텍스 답"}]}}], "usageMetadata": {}}


class Web(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.t = [1000.0]
        patches = [mock.patch.object(gw, "STATE", self.tmp / "state.json"), mock.patch.object(gw, "LOG", self.tmp / "log.jsonl"),
                   mock.patch.dict("os.environ", {"GEMINI_WEB_PORTS": "9001,9002"}, clear=False),
                   mock.patch.object(gw, "time", types.SimpleNamespace(time=lambda: self.t[0]))]
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)
        self.calls = []

    def remote(self, *results):
        it = iter(results)

        def fake(port, q, timeout):
            self.calls.append(port)
            return next(it)
        return mock.patch.object(gw, "_run_remote", side_effect=fake)

    def test_success_parses_text_and_sources(self):
        with self.remote(OK):
            r = gw.ask("오늘 서울 날짜는? 한 줄로.", who="탐")
        self.assertEqual((r["route"], r["status"], r["exit_code"]), ("gemini-web", "ok", 0))
        self.assertEqual(r["sources"], [{"title": "달력", "uri": "https://e.x/cal"}])  # 빈 uri 는 버린다
        log = json.loads((self.tmp / "log.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((log["who"], log["port"], log["status"]), ("탐", "9001", "ok"))
        self.assertNotIn("text", log)  # 질문·답은 기록하지 않는다

    def test_min_gap_then_other_account_then_throttled(self):
        with self.remote(OK, OK):
            self.assertEqual(gw.ask("q")["port"], "9001")
            self.t[0] += 5  # 간격 미달이면 호출 적은 다른 계정
            self.assertEqual(gw.ask("q")["port"], "9002")
            self.t[0] += 5  # 둘 다 간격 미달 -> 호출하지 않고 거절
            r = gw.ask("q")
        self.assertEqual((r["status"], r["exit_code"]), ("throttled", 2))
        self.assertEqual(self.calls, ["9001", "9002"])

    def test_day_cap(self):
        with mock.patch.object(gw, "DAY_CAP", 2), self.remote(OK, OK, OK, OK):
            for _ in range(4):
                self.t[0] += 200
                self.assertEqual(gw.ask("q")["status"], "ok")
            self.t[0] += 200
            r = gw.ask("q")
        self.assertEqual(r["status"], "throttled")
        self.assertIn("일상한", r["text"])

    def test_block_phrase_stops_only_that_account_for_the_day(self):
        blocked = {"status": "blocked", "text": "", "sources": [], "secs": 9, "note": "차단 문구: 한도"}
        with self.remote(blocked, OK, OK):
            r = gw.ask("q")
            self.assertEqual((r["status"], r["port"]), ("blocked", "9001"))
            self.assertIn("중지", r["text"])
            self.t[0] += 200
            r2 = gw.ask("q")  # 다른 계정은 계속(계정별 중지, 전면 중단 아님)
            self.assertEqual((r2["status"], r2["port"]), ("ok", "9002"))
            self.t[0] += 200
            r3 = gw.ask("q")  # 중지된 9001 로 되돌아가지 않는다
            self.assertEqual(r3["port"], "9002")
        self.assertEqual(self.calls, ["9001", "9002", "9002"])

    def test_login_and_mismatch_also_stop_account(self):
        for st in ("login", "mismatch", "consent"):
            gw.STATE.unlink(missing_ok=True)
            with self.remote({"status": st, "text": "", "sources": [], "secs": 1, "note": ""}):
                r = gw.ask("q")
            self.assertEqual(r["status"], st)
            self.assertIn("중지", gw.load_state()[gw._today()]["9001"]["stopped"] + "중지")
            self.assertTrue(gw.load_state()[gw._today()]["9001"]["stopped"].startswith(st))

    def test_timeout_does_not_stop_account(self):
        with self.remote({"status": "timeout", "text": "", "sources": [], "secs": 150, "note": ""}):
            r = gw.ask("q")
        self.assertEqual(r["status"], "timeout")
        self.assertNotIn("stopped", gw.load_state()[gw._today()]["9001"])

    def test_question_length_limit_no_call(self):
        with self.remote() as m:
            r = gw.ask("가" * (gw.MAX_Q + 1))
            r0 = gw.ask("   ")
        self.assertEqual((r["status"], r0["status"]), ("rejected", "rejected"))
        m.assert_not_called()

    def test_empty_answer_is_failure(self):
        with self.remote({"status": "ok", "text": " ", "sources": [], "secs": 3, "note": ""}):
            r = gw.ask("q")
        self.assertEqual((r["status"], r["exit_code"]), ("empty", 2))


class RouteFall(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patches = [mock.patch.object(gr, "ROUTE_LOG", self.tmp / "route.jsonl"), mock.patch.object(av, "LOG", self.tmp / "usage.csv"),
                   mock.patch.object(quota, "STATE", self.tmp / "quota_state.json"),
                   mock.patch.object(gr, "_free_keys", return_value=[("K", "k")]),
                   mock.patch.object(gr, "_token", return_value="t"), mock.patch.object(gr, "_day_krw", return_value=0.0),
                   mock.patch.object(av, "total_since", return_value=0.0), mock.patch.object(gw, "STATE", self.tmp / "ws.json"),
                   mock.patch.object(gw, "LOG", self.tmp / "wl.jsonl")]
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)
        self.urls = []

    def post(self, plan):
        def f(url, headers, body, timeout):
            self.urls.append(url)
            for k, code in plan.items():
                if k in url:
                    return code, (OKJSON if code == 200 else None)
            return 0, None
        return mock.patch.object(gr, "_http_post", side_effect=f)

    def test_default_off_goes_straight_to_vertex(self):
        with mock.patch.dict("os.environ", {}, clear=False) as e, mock.patch.object(gw, "_run_remote") as rr, \
                self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            e.pop("GEMINI_WEB", None)
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "vertex-company")
        rr.assert_not_called()

    def test_on_search_free_429_uses_web_before_vertex(self):
        with mock.patch.dict("os.environ", {"GEMINI_WEB": "1", "GEMINI_WEB_PORTS": "9001"}), mock.patch.object(gw, "_run_remote", return_value=OK), \
                self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True, who="탐")
        self.assertEqual((r["route"], r["exit_code"]), ("gemini-web", 0))
        self.assertEqual(r["sources"][0]["uri"], "https://e.x/cal")
        self.assertFalse(any("aiplatform" in u for u in self.urls))  # Vertex 호출 없음

    def test_on_web_fail_falls_to_company_vertex(self):
        bad = {"status": "blocked", "text": "", "sources": [], "secs": 2, "note": "차단 문구"}
        with mock.patch.dict("os.environ", {"GEMINI_WEB": "1", "GEMINI_WEB_PORTS": "9001"}), mock.patch.object(gw, "_run_remote", return_value=bad), \
                self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "vertex-company")
        self.assertEqual([t[0] for t in r["tried"]], ["free", "gemini-web"])

    def test_on_but_not_search_skips_web(self):
        with mock.patch.dict("os.environ", {"GEMINI_WEB": "1"}), mock.patch.object(gw, "_run_remote") as rr, \
                self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=False)
        self.assertEqual(r["route"], "vertex-company")
        rr.assert_not_called()

    def test_free_success_never_touches_web(self):
        with mock.patch.dict("os.environ", {"GEMINI_WEB": "1"}), mock.patch.object(gw, "_run_remote") as rr, self.post({"generativelanguage": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "free")
        rr.assert_not_called()

    def test_web_exception_does_not_break_fall(self):
        with mock.patch.dict("os.environ", {"GEMINI_WEB": "1"}), mock.patch.object(gw, "ask", side_effect=RuntimeError("boom")), \
                self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "vertex-company")


if __name__ == "__main__":
    unittest.main()
