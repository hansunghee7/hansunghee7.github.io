"""gemini_route.py 시험. 네트워크·gcloud·키 대장·실제 장부 접근 없음(전부 가짜 함수, 임시 폴더).

실행: python -m pytest scripts/ops/tests/test_gemini_route.py
"""
import datetime
import importlib.util
import json
import os
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
                   mock.patch.object(gr, "SEARCH_LEDGER", self.tmp / "search_ledger.csv"),
                   mock.patch.object(gr, "SEARCH_STATE", self.tmp / "search_state.json"),
                   mock.patch.dict("os.environ", {"GEMINI_WEB": "0"}, clear=False)]  # 웹앱 갈래는 기본 켜짐이라 여기선 끈다(실제 ssh 호출 방지)
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)
        for n in (gr.SEARCH_ENV, "GEMINI_SEARCH_MONTH_CAP", "GEMINI_SEARCH_DAY_CAP", "GEMINI_SEARCH_MODEL"):
            os.environ.pop(n, None)
        os.environ["HERMES_ENV_FILE"] = str(self.tmp / "no_such.env")  # 실제 설정 파일을 읽지 않게 한다
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
            r = gr.call("질문", who="핏")  # 검색 요청은 무료 키를 건너뛰므로(G1 검색 키 경로) 무료 429 낙하는 일반 호출로 본다
        self.assertEqual((r["route"], r["status"], r["exit_code"]), ("vertex-company", "ok", 0))
        self.assertEqual(r["sources"][0]["uri"], "https://e.x/a")
        self.assertIn("핏", (self.tmp / "usage.csv").read_text(encoding="utf-8"))
        self.assertTrue(quota.blocked_until(quota.load_state(), "제미나이-무료", datetime.datetime.now()))

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


class GenConfig(Base):
    def _bodies(self, plan, **kw):
        bodies = []

        def post(url, headers, body, timeout):
            bodies.append(body)
            for k, code in plan.items():
                if k in url:
                    return code, (OKJSON if code == 200 else None)
            return 0, None
        with mock.patch.object(gr, "_http_post", side_effect=post):
            gr.call("질문", **kw)
        return bodies

    def test_genconfig_passthrough_free_and_vertex(self):
        gc = {"maxOutputTokens": 32768, "temperature": 0.8}
        free = self._bodies({"generativelanguage": 200}, generation_config=gc)
        self.assertEqual(free[0]["generationConfig"], gc)
        vtx = self._bodies({"generativelanguage": 429, "simplifier-vertex-credit": 200}, generation_config=gc)
        self.assertEqual(vtx[-1]["generationConfig"], gc)
        rec = json.loads((self.tmp / "route.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((rec["gen_keys"], rec["max_output_tokens"]), (["maxOutputTokens", "temperature"], 32768))
        self.assertNotIn("0.8", json.dumps(rec))

    def test_genconfig_rejects_unknown_key(self):
        with self.assertRaises(ValueError):
            gr.call("질문", generation_config={"maxOutputTokens": 10, "tools": []})

    def test_genconfig_rejects_bad_max_tokens(self):
        for bad in (0, 65537, "100", 1.5, True):
            with self.assertRaises(ValueError):
                gr.call("질문", generation_config={"maxOutputTokens": bad})

    def test_no_genconfig_no_field(self):
        b = self._bodies({"generativelanguage": 200})
        self.assertNotIn("generationConfig", b[0])


SKEY = "AI" + "za" + "Sy" + "S" * 33  # 검색 전용 키 모양 가짜 값


class SearchKey(Base):
    def setUp(self):
        super().setUp()
        os.environ[gr.SEARCH_ENV] = SKEY
        os.environ["GEMINI_SEARCH_KEY_ENABLED"] = "1"  # 2026-10-20: 기본은 꺼짐(크레딧 제외 결제 방지). 이 클래스는 켠 상태를 시험한다
        self.addCleanup(os.environ.pop, "GEMINI_SEARCH_KEY_ENABLED", None)

    def test_search_key_stage_is_off_by_default(self):
        # 사장님 10/20: 유료 AI Studio 키는 크레딧이 안 덮으므로 기본 꺼짐 → 검색은 Vertex로 간다
        os.environ.pop("GEMINI_SEARCH_KEY_ENABLED")
        with self.server({"generativelanguage": 200, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=True)
        self.assertNotEqual(r["route"], "search-key")
        self.assertFalse([u for u in self.urls if "generativelanguage" in u and "search" in u.lower()])

    def _ledger_add(self, n, when=None):
        gr._search_ledger_add("시험", n, "m")
        if when:  # 날짜를 과거로 바꿔 쓴다
            t = gr.SEARCH_LEDGER.read_text(encoding="utf-8").splitlines()
            t[-1] = when + t[-1][19:]
            gr.SEARCH_LEDGER.write_text("\n".join(t) + "\n", encoding="utf-8")

    def _gen_urls(self):
        return [u for u in self.urls if "generativelanguage" in u]

    def test_search_uses_search_key_not_free(self):
        with self.server({"generativelanguage": 200}):
            r = gr.call("질문", search=True, who="핏")
        self.assertEqual((r["route"], r["exit_code"]), ("search-key", 0))
        self.assertEqual(len(self.urls), 1)  # 무료 키 호출 없음(검색 키 한 번뿐)
        rows = gr.SEARCH_LEDGER.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].split(",")[1:], ["핏", "1", "gemini-3.6-flash"])  # webSearchQueries 1개
        rec = json.loads((self.tmp / "route.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((rec["route"], rec["search"]), ("search-key", True))

    def test_no_search_key_goes_company(self):
        os.environ.pop(gr.SEARCH_ENV)
        with self.server({"generativelanguage": 200, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=True)
        self.assertEqual(r["route"], "vertex-company")
        self.assertEqual(r["tried"], [])  # 조용히 건너뜀, 시도 기록도 없음
        self.assertEqual(self._gen_urls(), [])
        self.assertFalse(gr.SEARCH_STATE.exists())

    def test_401_marks_invalid_then_skips_24h(self):
        with self.server({"generativelanguage": 401, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=True)
            self.assertEqual(r["route"], "vertex-company")
            st = json.loads(gr.SEARCH_STATE.read_text(encoding="utf-8"))
            self.assertEqual((st["status"], st["http"]), ("search-key-invalid", 401))
            self.assertEqual(len(self._gen_urls()), 1)
            r2 = gr.call("질문", search=True)
        self.assertEqual(len(self._gen_urls()), 1)  # 두 번째는 두드리지 않음
        self.assertIn(("search-key", "skipped_invalid"), r2["tried"])
        self.assertNotIn(SKEY, json.dumps(r2) + gr.SEARCH_STATE.read_text(encoding="utf-8"))

    def test_invalid_expires_after_24h(self):
        old = datetime.datetime.now() - datetime.timedelta(hours=25)
        gr.SEARCH_STATE.write_text(json.dumps({"status": "search-key-invalid", "since": f"{old:%Y-%m-%d %H:%M:%S}", "http": 403}), encoding="utf-8")
        with self.server({"generativelanguage": 200}):
            r = gr.call("질문", search=True)
        self.assertEqual(r["route"], "search-key")
        self.assertEqual(json.loads(gr.SEARCH_STATE.read_text(encoding="utf-8"))["status"], "ok")

    def test_402_403_invalid_but_429_400_not(self):
        for code, invalid in ((402, True), (403, True), (429, False), (400, False)):
            if gr.SEARCH_STATE.exists():
                gr.SEARCH_STATE.unlink()
            with self.server({"generativelanguage": code, "simplifier-vertex-credit": 200}):
                r = gr.call("질문", search=True)
            self.assertEqual(r["route"], "vertex-company")
            self.assertEqual(gr.SEARCH_STATE.exists(), invalid, code)

    def test_day_cap_falls_to_vertex(self):
        os.environ["GEMINI_SEARCH_DAY_CAP"] = "3"
        self._ledger_add(3)
        with self.server({"generativelanguage": 200, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=True)
        self.assertEqual(r["route"], "vertex-company")
        self.assertEqual(self._gen_urls(), [])
        self.assertIn("검색 키 상한", (self.tmp / "route.jsonl").read_text(encoding="utf-8"))

    def test_month_cap_sums_ledger_and_ignores_other_months(self):
        os.environ["GEMINI_SEARCH_MONTH_CAP"] = "10"
        os.environ["GEMINI_SEARCH_DAY_CAP"] = "100"
        self._ledger_add(4)
        self._ledger_add(4, when="2020-01-01 00:00:00")  # 지난 달 기록은 합산 제외
        self.assertEqual(gr._search_usage(), (4, 4))
        self._ledger_add(4)
        self.assertEqual(gr._search_usage(), (8, 8))
        with self.server({"generativelanguage": 200, "simplifier-vertex-credit": 200}):
            first = gr.call("질문", search=True)
        self.assertEqual(first["route"], "search-key")  # 8 < 10 이라 통과, 장부 +1(9)
        self._ledger_add(1)
        with self.server({"generativelanguage": 200, "simplifier-vertex-credit": 200}):
            second = gr.call("질문", search=True)
        self.assertEqual(second["route"], "vertex-company")  # 합계 10 도달

    def test_ledger_counts_search_queries_from_response(self):
        j = json.loads(json.dumps(OKJSON))
        j["candidates"][0]["groundingMetadata"]["webSearchQueries"] = ["a", "b", "c"]
        with mock.patch.object(gr, "_http_post", return_value=(200, j)):
            gr.call("질문", search=True)
        self.assertEqual(gr._search_usage()[0], 3)

    def test_model_env_override(self):
        os.environ["GEMINI_SEARCH_MODEL"] = "gemini-x-test"
        with self.server({"gemini-x-test": 200}):
            gr.call("질문", search=True)
        self.assertIn("gemini-x-test", self.urls[0])

    def test_no_key_shaped_values_anywhere(self):
        with self.server({"generativelanguage": 401, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=True, who="핏")
        os.remove(gr.SEARCH_STATE)
        with self.server({"generativelanguage": 200}):
            r2 = gr.call("질문", search=True, who="핏")
        blob = json.dumps([r, r2], ensure_ascii=False) + gr.search_status()
        for f in (self.tmp / "route.jsonl", gr.SEARCH_LEDGER):
            blob += f.read_text(encoding="utf-8")
        self.assertNotIn(SKEY, blob)
        self.assertIsNone(gr.KEY_LIKE.search(blob))

    def test_search_false_keeps_old_order(self):
        with self.server({"generativelanguage": 429, "simplifier-vertex-credit": 200}):
            r = gr.call("질문", search=False)
        self.assertEqual(r["route"], "vertex-company")
        self.assertEqual([t[0] for t in r["tried"]], ["free"])
        self.assertTrue(self._gen_urls())  # 무료 키 먼저
        self.assertFalse(gr.SEARCH_LEDGER.exists())

    def test_search_status_line(self):
        self._ledger_add(7)
        line = gr.search_status()
        self.assertIn("오늘 7/200", line)
        self.assertIn("이번 달 7/4500", line)
        self.assertIn("4993/5000", line)
        self.assertEqual(gr.main(["--search-status"]), 0)


class SearchKeyFile(Base):
    def _env(self, text):
        p = self.tmp / "h.env"
        p.write_text(text, encoding="utf-8")
        os.environ["HERMES_ENV_FILE"] = str(p)

    def test_env_wins_over_file(self):
        self._env(f"{gr.SEARCH_ENV}=FILEVAL1234\n")
        os.environ[gr.SEARCH_ENV] = SKEY
        self.assertEqual(gr._search_key(), (SKEY, "환경 변수"))
        self.assertIn("있음(환경 변수)", gr.search_status())

    def test_file_used_when_no_env(self):
        self._env(f"OTHER=zzz\n{gr.SEARCH_ENV}={SKEY}\n")
        self.assertEqual(gr._search_key(), (SKEY, "설정 파일"))
        self.assertIn("있음(설정 파일)", gr.search_status())

    def test_none_when_missing(self):
        self.assertEqual(gr._search_key(), (None, None))  # 파일 없음
        self._env("OTHER=zzz\n")
        self.assertEqual(gr._search_key(), (None, None))  # 변수 없음
        self.assertIn("검색 전용 키 없음", gr.search_status())

    def test_quotes_and_set_prefix(self):
        for line in (f'{gr.SEARCH_ENV}="{SKEY}"', f"set {gr.SEARCH_ENV}='{SKEY}'", f"  {gr.SEARCH_ENV} = {SKEY}  "):
            self._env(line + "\n")
            self.assertEqual(gr._search_key()[0], SKEY, line)

    def test_other_variables_not_read(self):
        self._env(f"GEMINI_API_KEY=OTHERSECRET99\nX_{gr.SEARCH_ENV}=NOPE12345\n")
        self.assertEqual(gr._search_key(), (None, None))

    def test_no_key_value_in_status_or_logs(self):
        self._env(f"{gr.SEARCH_ENV}={SKEY}\n")
        self.server({"generativelanguage": 200})
        gr.call("질문", search=True, who="t")
        blob = gr.search_status() + (self.tmp / "route.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(SKEY, blob)


if __name__ == "__main__":
    unittest.main()
