"""gcp_burn.py 시험. 네트워크·gcloud·ask_vertex 호출 없음(ask 함수를 가짜로 바꿔 끼운다).

실행: python -m pytest scripts/ops/tests/test_gcp_burn.py
시험하는 것: 하루 상한 계산과 기본값, 상한 도달 시 멈춤, 성공 과제 건너뜀, 3회 재시도 한도, ask_vertex 상한(종료 3),
            --dry가 호출·기록을 하지 않음, 비밀값 모양 프롬프트 차단, ledger 한 줄 형식, 무료 키 경로 차단 환경변수.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gcp_burn", HERE.parent / "gcp_burn.py")
gb = importlib.util.module_from_spec(spec)
sys.modules["gcp_burn"] = gb
spec.loader.exec_module(gb)

TODAY = date(2026, 10, 20)  # 12/10까지 51일
OK_ERR = "청구 프로젝트: simplifier-vertex-credit\n답 저장: x (10자) 토큰 입력 1000·출력 500·검색 0건·추정 약 ₩7.1·3초\n"


class FakeAsk:
    def __init__(self, seq):
        self.seq = list(seq)  # (rc, text, stderr)
        self.calls = 0

    def __call__(self, prompt_path, out_path, model, search):
        rc, text, err = self.seq[min(self.calls, len(self.seq) - 1)]
        self.calls += 1
        Path(out_path).write_text(text, encoding="utf-8")
        return rc, err


class GcpBurnTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.q, self.l, self.r = self.d / "queue.jsonl", self.d / "ledger.jsonl", self.d / "results"

    def write_queue(self, *tasks):
        self.q.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in tasks) + "\n", encoding="utf-8")

    def run_burn(self, ask, extra=(), remain=700000.0):
        argv = ["--queue", str(self.q), "--ledger", str(self.l), "--results", str(self.r), *extra]
        return gb.main(argv, ask=ask, remain_fn=lambda: remain, today=TODAY)

    def ledger(self):
        return gb.read_jsonl(self.l)

    def test_daily_cap_formula(self):
        cap, why = gb.daily_cap(TODAY, lambda: 714000.0)
        self.assertAlmostEqual(cap, 714000 / 1400 / 51 * 0.8, places=3)  # 8.0달러
        self.assertIn("51일", why)

    def test_daily_cap_default_when_unreadable(self):
        def boom():
            raise RuntimeError("캐시 없음")
        cap, why = gb.daily_cap(TODAY, boom)
        self.assertEqual(cap, 5.0)
        self.assertIn("기본값", why)

    def test_success_writes_ledger_and_skips_next_time(self):
        self.write_queue({"id": "t1", "title": "시험", "prompt": "요약해 줘", "est_usd": 0.01})
        ask = FakeAsk([(0, "답", OK_ERR)])
        self.assertEqual(self.run_burn(ask), 0)
        calls = [r for r in self.ledger() if r["kind"] == "call"]
        self.assertEqual(len(calls), 1)
        c = calls[0]
        self.assertTrue(c["ok"])
        self.assertEqual((c["in_tok"], c["out_tok"], c["project"]), (1000, 500, "simplifier-vertex-credit"))
        self.assertAlmostEqual(c["est_usd"], 7.1 / 1400, places=5)
        self.assertTrue(Path(c["result"]).exists())
        self.assertEqual(self.run_burn(ask), 0)
        self.assertEqual(ask.calls, 1)  # 두 번째 실행은 건너뜀

    def test_retry_max_three(self):
        self.write_queue({"id": "t1", "title": "실패", "prompt": "x", "est_usd": 0.01})
        ask = FakeAsk([(2, "[호출 실패 HTTP 500] 오류", "실패")])
        self.assertEqual(self.run_burn(ask), 2)
        self.assertEqual(ask.calls, 3)
        self.assertEqual([r["attempt"] for r in self.ledger() if r["kind"] == "call"], [1, 2, 3])
        self.run_burn(ask)
        self.assertEqual(ask.calls, 3)  # 포기 상태라 더 부르지 않음

    def test_retry_then_success(self):
        self.write_queue({"id": "t1", "title": "x", "prompt": "x", "est_usd": 0.01})
        ask = FakeAsk([(2, "[호출 실패 HTTP 503]", "e"), (0, "답", OK_ERR)])
        self.assertEqual(self.run_burn(ask), 0)
        self.assertEqual(ask.calls, 2)

    def test_stops_at_daily_cap(self):
        self.write_queue({"id": "a", "title": "a", "prompt": "x", "est_usd": 3.0},
                         {"id": "b", "title": "b", "prompt": "x", "est_usd": 5.0})
        ask = FakeAsk([(0, "답", OK_ERR)])
        # 남은 ₩357,000 → 하루 상한 4달러: a(예상 3)는 되고 b(예상 5)는 넘는다
        self.assertEqual(self.run_burn(ask, remain=357000.0), 3)
        self.assertEqual(ask.calls, 1)
        self.assertTrue(any(r["kind"] == "stop" and r["task"] == "b" for r in self.ledger()))

    def test_max_usd_per_run(self):
        self.write_queue({"id": "a", "title": "a", "prompt": "x", "est_usd": 0.6},
                         {"id": "b", "title": "b", "prompt": "x", "est_usd": 0.6})
        ask = FakeAsk([(0, "답", OK_ERR.replace("₩7.1", "₩840"))])  # 실제 0.6달러 썼다고 보고
        self.assertEqual(self.run_burn(ask, extra=["--max-usd", "1.0"]), 3)
        self.assertEqual(ask.calls, 1)

    def test_ask_vertex_cap_exit3_not_counted_as_attempt(self):
        self.write_queue({"id": "a", "title": "a", "prompt": "x", "est_usd": 0.01})
        ask = FakeAsk([(3, "", "하루 상한 초과")])
        self.assertEqual(self.run_burn(ask), 3)
        self.assertEqual(ask.calls, 1)
        self.assertEqual(gb.task_state(self.ledger(), "a"), (False, 0))

    def test_dry_makes_no_calls_or_ledger(self):
        self.write_queue({"id": "a", "title": "a", "prompt": "x", "est_usd": 0.01})
        ask = FakeAsk([(0, "답", OK_ERR)])
        self.assertEqual(self.run_burn(ask, extra=["--dry"]), 0)
        self.assertEqual(ask.calls, 0)
        self.assertFalse(self.l.exists())

    def test_secret_like_prompt_blocked(self):
        fake = "AIza" + "B" * 35
        self.write_queue({"id": "a", "title": "a", "prompt": "키는 " + fake, "est_usd": 0.01})
        ask = FakeAsk([(0, "답", OK_ERR)])
        self.run_burn(ask)
        self.assertEqual(ask.calls, 0)
        rows = self.ledger()
        self.assertTrue(any(r["kind"] == "skip" for r in rows))
        self.assertNotIn(fake, self.l.read_text(encoding="utf-8"))

    def test_context_files_and_limit(self):
        f = self.d / "doc.md"
        f.write_text("가" * 100, encoding="utf-8")
        p = gb.build_prompt({"prompt": "읽어", "context_files": [str(f), str(self.d / "없음.md")], "max_context_chars": 50})
        self.assertIn("=== 자료: doc.md ===", p)
        self.assertIn("잘림", p)
        self.assertIn("자료 없음: 없음.md", p)

    def test_run_ask_blocks_free_key_paths(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(kw["env"])
            seen["cmd"] = cmd

            class R:
                returncode, stderr = 0, ""
            return R()
        orig = gb.subprocess.run
        gb.subprocess.run = fake_run
        try:
            gb.run_ask(Path("p.md"), Path("o.md"), "gemini-3.6-flash", False)
        finally:
            gb.subprocess.run = orig
        self.assertEqual(seen["VERTEX_NO_FAILOVER"], "1")
        self.assertEqual(seen["VERTEX_NO_ROUTER"], "1")
        self.assertTrue(str(seen["cmd"][1]).endswith("ask_vertex.py"))

    def test_entry_survives_pythonw_none_stdout(self):
        """pythonw처럼 stdout/stderr가 None이어도 죽지 않고 run.log와 last_run을 남긴다."""
        self.q.write_text("", encoding="utf-8")
        argv = ["--queue", str(self.q), "--ledger", str(self.l), "--results", str(self.r)]
        orig_main, so, se = gb.main, sys.stdout, sys.stderr
        gb.main = lambda a=None: orig_main(a, remain_fn=lambda: 1_000_000, today=TODAY)
        sys.stdout = sys.stderr = None
        try:
            rc = gb.entry(argv, base=self.d)
        finally:
            log = sys.stdout
            sys.stdout, sys.stderr, gb.main = so, se, orig_main
            if log not in (None, so):
                log.close()
        self.assertEqual(rc, 0)
        self.assertIn("rc=0", (self.d / "last_run").read_text(encoding="utf-8"))
        self.assertIn("끝:", (self.d / "run.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
