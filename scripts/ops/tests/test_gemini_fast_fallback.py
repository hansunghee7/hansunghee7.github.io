"""gemini_fast.py 폴백 시험(Vertex 먼저 -> 무료 키 순환 -> Vertex 재시도). 네트워크·gcloud·키 대장 접근 없음(전부 mock).

실행: python -m pytest scripts/ops/tests/test_gemini_fast_fallback.py  (또는 python -m unittest)
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

OPS = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location("gemini_fast_under_test", OPS / "gemini_fast.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gf = load_module()
FREE_MARK = "무료 키로 전환(HTTP403): 성공"


class AskOrder(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GEMINI_FAST_ORDER", None)
        self.keys = [{"name": "a", "fp": "busy", "value": "v"}, {"name": "b", "fp": "idle", "value": "v"}]
        self.vf = mock.patch.object(gf, "vertex_fallback")
        self.vf = self.vf.start()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(gf, "load_keys", return_value=self.keys).start()
        mock.patch.object(gf, "read_counter", return_value={gf.today_pt(): {"busy": {"calls": 9}, "idle": {"calls": 1}}}).start()
        self.call = mock.patch.object(gf, "call").start()

    def test_vertex_first_success_never_touches_keys(self):
        self.vf.return_value = {"ok": True, "text": "x", "fp": "vertex"}
        self.assertTrue(gf.ask("q")["ok"])
        self.call.assert_not_called()

    def test_vertex_already_tried_free_pool_skips_key_loop(self):
        self.vf.return_value = {"ok": False, "vertex": "rc=2", "vertex_tried_free": True}
        r = gf.ask("q")
        self.assertFalse(r["ok"])
        self.call.assert_not_called()
        self.vf.assert_called_once()

    def test_vertex_failed_then_least_used_key_first_then_stops_on_success(self):
        self.vf.return_value = {"ok": False, "vertex": "rc=2", "vertex_tried_free": False}
        self.call.side_effect = [{"ok": False, "status": 429}, {"ok": True, "text": "키 답", "fp": "busy"}]
        r = gf.ask("q")
        self.assertTrue(r["ok"])
        self.assertEqual([c.args[0]["fp"] for c in self.call.call_args_list], ["idle", "busy"])  # 호출 적은 키부터

    def test_all_keys_fail_retries_vertex_once_more(self):
        self.vf.return_value = {"ok": False, "vertex": "rc=2", "vertex_tried_free": False}
        self.call.return_value = {"ok": False, "status": 429}
        r = gf.ask("q")
        self.assertFalse(r["ok"])
        self.assertEqual(self.call.call_count, 2)
        self.assertEqual(self.vf.call_count, 2)  # 처음 한 번 + 키가 다 막힌 뒤 한 번
        self.assertEqual(self.vf.call_args.args[1], {"ok": False, "status": 429})  # 마지막 키 실패 결과를 넘김

    def test_free_order_skips_first_vertex_attempt(self):
        os.environ["GEMINI_FAST_ORDER"] = "free"
        self.call.return_value = {"ok": True, "text": "x", "fp": "idle"}
        self.assertTrue(gf.ask("q")["ok"])
        self.vf.assert_not_called()

    def test_no_keys_and_vertex_failed(self):
        self.vf.return_value = {"ok": False}
        gf.load_keys.return_value = []
        self.assertEqual(gf.ask("q"), {"ok": False, "status": "사용 가능한 키 없음"})


class VertexFallbackBody(unittest.TestCase):
    """vertex_fallback: ask_vertex.py를 부르는 subprocess만 가짜로 바꿔 결과 해석을 본다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch("tempfile.gettempdir", return_value=self.tmp.name)
        p.start()
        self.addCleanup(p.stop)

    def fake_run(self, rc=0, stderr="", answer="답", raises=None):
        def run(cmd, **kw):
            self.cmd = cmd
            if raises:
                raise raises
            if answer is not None:
                Path(cmd[3]).write_text(answer, encoding="utf-8")  # cmd[3] = 답 파일
            return SimpleNamespace(returncode=rc, stderr=stderr, stdout="")
        return mock.patch("subprocess.run", side_effect=run)

    def leftovers(self):
        return list(Path(self.tmp.name).glob("gemini_fast_vx_*"))

    def test_success_counts_as_vertex_and_cleans_temp_files(self):
        with self.fake_run():
            r = gf.vertex_fallback("질문", None)
        self.assertEqual((r["ok"], r["text"], r["fp"]), (True, "답", "vertex"))
        self.assertEqual(self.leftovers(), [])
        self.assertTrue(Path(self.cmd[1]).name == "ask_vertex.py")

    def test_ask_vertex_went_free_is_not_counted_as_vertex(self):
        with self.fake_run(stderr=FREE_MARK):
            r = gf.vertex_fallback("질문", None)
        self.assertEqual((r["ok"], r["fp"]), (True, "free"))

    def test_nonzero_exit_reports_failure_and_whether_free_was_tried(self):
        with self.fake_run(rc=2, answer=None):
            r = gf.vertex_fallback("질문", {"ok": False, "status": 429})
        self.assertEqual((r["ok"], r["vertex"], r["vertex_tried_free"], r["status"]), (False, "rc=2", False, 429))
        with self.fake_run(rc=2, stderr=FREE_MARK, answer=None):
            r = gf.vertex_fallback("질문", None)
        self.assertTrue(r["vertex_tried_free"])
        self.assertEqual(self.leftovers(), [])

    def test_zero_exit_without_answer_file_is_failure(self):
        with self.fake_run(rc=0, answer=None):
            r = gf.vertex_fallback("질문", None)
        self.assertFalse(r["ok"])

    def test_subprocess_exception_is_swallowed(self):
        with self.fake_run(raises=subprocess.TimeoutExpired("cmd", 180)):
            r = gf.vertex_fallback("질문", {"ok": False, "status": 429})
        self.assertEqual((r["ok"], r["vertex"], r["status"]), (False, "TimeoutExpired", 429))
        self.assertEqual(self.leftovers(), [])


if __name__ == "__main__":
    unittest.main()
