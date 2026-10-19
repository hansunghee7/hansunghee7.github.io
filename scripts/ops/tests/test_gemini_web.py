"""gemini_web.py 시험. ssh·브라우저·실제 장부 접근 없음(원격 실행은 가짜 응답, 임시 폴더).

실행: python -m pytest scripts/ops/tests/test_gemini_web.py
시험하는 것: 하루 상한, 호출 간격, 차단 문구 시 그 계정만 중지(다른 계정은 계속), 출처 파싱, 질문 길이 제한,
            라우터 낙하 순서(검색 키 -> 웹앱 기본 켜짐, GEMINI_WEB=0 만 끔 -> Vertex / 검색 아닌 요청은 건너뜀).
"""
import importlib.util
import json
import sys
import tempfile
import threading
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


    def test_workspace_ports_hard_rejected_even_if_env_sets_them(self):
        with mock.patch.dict("os.environ", {"GEMINI_WEB_PORTS": "9222,9223,9226,9225"}), self.remote(OK):
            r = gw.ask("q")
        self.assertEqual(r["port"], "9225")
        self.assertEqual(self.calls, ["9225"])
        self.assertIn("port_rejected", (self.tmp / "log.jsonl").read_text(encoding="utf-8"))
        with mock.patch.dict("os.environ", {"GEMINI_WEB_PORTS": "9222,9226"}), self.remote() as m:
            self.assertEqual(gw.ask("q")["status"], "throttled")
        m.assert_not_called()

    def test_concurrent_asks_never_pick_same_port(self):
        got, gate = [], threading.Barrier(2)

        def fake(port, q, timeout):
            got.append(port)
            threading.Event().wait(0.3)
            return OK
        res = []

        def go():
            gate.wait()
            res.append(gw.ask("q"))
        with mock.patch.object(gw, "_run_remote", side_effect=fake):
            ts = [threading.Thread(target=go) for _ in range(2)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(sorted(got), ["9001", "9002"])

    def test_stale_lock_reclaimed(self):
        lk = Path(str(gw.STATE) + ".lock")
        lk.write_text("x")
        import os
        old = os.path.getmtime(lk) - 60
        os.utime(lk, (old, old))
        with self.remote(OK):
            self.assertEqual(gw.ask("q")["status"], "ok")

    def test_total_budget_default_60_and_env(self):
        seen = []
        with mock.patch.object(gw, "_run_remote", side_effect=lambda p, q, t: seen.append(t) or OK):
            gw.ask("q")
            self.t[0] += 200
            with mock.patch.dict("os.environ", {"GEMINI_WEB_TIMEOUT": "30"}):
                gw.ask("q")
        self.assertEqual(seen, [60, 30])


class RemoteLogic(unittest.TestCase):
    """구PC 실행기의 새 응답 판정(가짜 DOM). 브라우저 없음."""
    @classmethod
    def setUpClass(cls):
        sp = importlib.util.spec_from_file_location("gwa", OPS.parents[1] / "tools" / "gemini_web" / "gemini_web_ask.py")
        cls.m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(cls.m)

    def run_wait(self, reads, body="", timeout=40):
        clock = [0.0]
        it = iter(reads)
        cur = [reads[0]]

        def read():
            try:
                cur[0] = next(it)
            except StopIteration:
                pass
            return cur[0]
        return self.m.wait_answer(read, lambda: False, lambda: body, lambda s: clock.__setitem__(0, clock[0] + s), lambda: clock[0],
                                  self.m.h("이전 답"), 1, timeout)

    def test_only_old_answer_no_new_node_is_error(self):
        st, txt, _s, note = self.run_wait([{"text": "이전 답", "sources": [], "n": 1}] * 30)
        self.assertEqual(st, "error")
        self.assertEqual(txt, "")

    def test_new_node_is_ok(self):
        old = {"text": "이전 답", "sources": [], "n": 1}
        new = {"text": "4", "sources": [{"title": "t", "uri": "https://e.x"}], "n": 2}
        st, txt, src, _n = self.run_wait([old, old] + [new] * 10)
        self.assertEqual((st, txt, src[0]["uri"]), ("ok", "4", "https://e.x"))

    def test_same_node_count_but_changed_hash_is_ok(self):
        st, txt, _s, _n = self.run_wait([{"text": "다른 답", "sources": [], "n": 1}] * 10)
        self.assertEqual((st, txt), ("ok", "다른 답"))

    def test_long_block_notice_detected_in_first_600_chars(self):
        long_txt = "죄송합니다. 도와드릴 수 없습니다. " + "안내 " * 300
        self.assertGreater(len(long_txt), 200)
        st, _t, _s, note = self.run_wait([{"text": long_txt, "sources": [], "n": 2}] * 10)
        self.assertEqual(st, "blocked")

    def test_block_word_after_600_chars_ignored_and_normal_answer_ok(self):
        txt = "정상 답변 " * 150 + " 정책에 따라"
        st, *_ = self.run_wait([{"text": txt, "sources": [], "n": 2}] * 10)
        self.assertEqual(st, "ok")
        self.assertEqual(self.m.block_phrase("서울은 오늘 맑습니다"), "")

    def test_stops_if_screen_shows_block_before_any_answer(self):
        st, *_ = self.run_wait([{"text": "", "sources": [], "n": 1}] * 20, body="요청이 너무 많아 한도에 도달했습니다")
        self.assertEqual(st, "blocked")


class RouteFall(unittest.TestCase):
    """검색 요청 최종 순서: 검색 전용 키 -> 웹앱(기본 켜짐) -> 회사 Vertex -> 개인 Vertex. 무료 키는 검색에서 안 부른다."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patches = [mock.patch.object(gr, "ROUTE_LOG", self.tmp / "route.jsonl"), mock.patch.object(av, "LOG", self.tmp / "usage.csv"),
                   mock.patch.object(quota, "STATE", self.tmp / "quota_state.json"),
                   mock.patch.object(gr, "SEARCH_LEDGER", self.tmp / "sl.csv"), mock.patch.object(gr, "SEARCH_STATE", self.tmp / "ss.json"),
                   mock.patch.object(gr, "_free_keys", return_value=[("K", "k")]),
                   mock.patch.object(gr, "_search_key", return_value=("sk", "env")),
                   mock.patch.object(gr, "_token", return_value="t"), mock.patch.object(gr, "_day_krw", return_value=0.0),
                   mock.patch.object(av, "total_since", return_value=0.0), mock.patch.object(gw, "STATE", self.tmp / "ws.json"),
                   mock.patch.object(gw, "LOG", self.tmp / "wl.jsonl")]
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)
        self.urls = []

    def post(self, plan):
        def f(url, headers, body, timeout):
            self.urls.append((url, headers.get("x-goog-api-key")))
            for k, code in plan.items():
                if k in url:
                    return code, (OKJSON if code == 200 else None)
            return 0, None
        return mock.patch.object(gr, "_http_post", side_effect=f)

    ENV_ON = {"GEMINI_WEB_PORTS": "9001", "GEMINI_SEARCH_KEY_ENABLED": "1"}  # 검색키 단계는 기본 꺼짐(유료 AI Studio 경로 차단, 10/20), 이 시험은 켠 상태를 시험한다

    def test_search_key_ok_never_touches_web(self):
        with mock.patch.dict("os.environ", self.ENV_ON), mock.patch.object(gw, "_run_remote") as rr, self.post({"generativelanguage": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "search-key")
        rr.assert_not_called()
        self.assertEqual([k for u, k in self.urls], ["sk"])  # 무료 키("k")는 검색에서 안 쓴다

    def test_search_key_fails_then_web_before_vertex(self):
        with mock.patch.dict("os.environ", self.ENV_ON), mock.patch.object(gw, "_run_remote", return_value=OK),                 self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True, who="탐")
        self.assertEqual((r["route"], r["exit_code"]), ("gemini-web", 0))
        self.assertEqual(r["sources"][0]["uri"], "https://e.x/cal")
        self.assertFalse(any("aiplatform" in u for u, _k in self.urls))

    def test_web_on_by_default_when_env_unset(self):
        with mock.patch.dict("os.environ", self.ENV_ON) as e, mock.patch.object(gw, "_run_remote", return_value=OK), self.post({"generativelanguage": 429}):
            e.pop("GEMINI_WEB", None)
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "gemini-web")

    def test_web_off_only_when_zero(self):
        with mock.patch.dict("os.environ", {"GEMINI_WEB": "0"}), mock.patch.object(gw, "_run_remote") as rr,                 self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "vertex-company")
        rr.assert_not_called()

    def test_web_fail_falls_to_company_vertex(self):
        bad = {"status": "blocked", "text": "", "sources": [], "secs": 2, "note": "차단 문구"}
        with mock.patch.dict("os.environ", self.ENV_ON), mock.patch.object(gw, "_run_remote", return_value=bad),                 self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "vertex-company")
        self.assertEqual([t[0] for t in r["tried"]], ["search-key", "gemini-web"])

    def test_non_search_skips_web_keeps_old_order(self):
        with mock.patch.dict("os.environ", self.ENV_ON), mock.patch.object(gw, "_run_remote") as rr,                 self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=False)
        self.assertEqual(r["route"], "vertex-company")
        self.assertEqual(self.urls[0][1], "k")  # 비검색은 무료 키 먼저
        rr.assert_not_called()

    def test_web_exception_does_not_break_fall(self):
        with mock.patch.dict("os.environ", self.ENV_ON), mock.patch.object(gw, "ask", side_effect=RuntimeError("boom")),                 self.post({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("q", search=True)
        self.assertEqual(r["route"], "vertex-company")


if __name__ == "__main__":
    unittest.main()
