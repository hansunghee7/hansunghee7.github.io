"""jitu-loop.py 훅과 scripts/ops/jitu_po.py 시험. 실행: python -m unittest .claude/hooks/test_jitu_loop.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "jitu-loop.py")
TOOL = os.path.join(HERE, "..", "..", "scripts", "ops", "jitu_po.py")

spec = importlib.util.spec_from_file_location("jitu_loop", HOOK)
jl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jl)


def run(args, stdin=None, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable] + args, input=(stdin or "").encode("utf-8"), capture_output=True, env=e)


class UnsafeMergeTest(unittest.TestCase):
    def test_piped_checks_then_merge_blocked(self):
        self.assertTrue(jl.unsafe_merge("cd x && gh pr checks 558 --watch 2>&1 | tail -4 && gh pr merge 558 --squash"))

    def test_clean_and_chain_allowed(self):
        self.assertFalse(jl.unsafe_merge("gh pr checks 559 --watch && gh pr merge 559 --squash --delete-branch"))

    def test_jq_pipe_inside_quotes_allowed(self):
        cmd = "gh pr checks 31 --json name,state --jq '.[]|[.name,.state]|@tsv'; gh pr merge 31 --squash"
        self.assertFalse(jl.unsafe_merge(cmd))

    def test_json_jq_quoted_with_double_quotes_allowed(self):
        cmd = 'bad=$(gh pr checks 35 --json name,state --jq "[.[]|select(.state!=\\"SUCCESS\\")]|length"); gh pr merge 35'
        self.assertFalse(jl.unsafe_merge(cmd))

    def test_logical_or_is_not_a_pipe(self):
        self.assertFalse(jl.unsafe_merge("gh pr checks 1 --watch || exit 1; gh pr merge 1"))

    def test_checks_pipe_without_merge_allowed(self):
        self.assertFalse(jl.unsafe_merge("gh pr checks 560 | head -3"))

    def test_heredoc_body_ignored(self):
        cmd = "cat <<'EOF'\ngh pr checks 5 | tail\ngh pr merge 5\nEOF"
        self.assertFalse(jl.unsafe_merge(cmd))


class HookModeTest(unittest.TestCase):
    def test_pre_bash_blocks_with_exit_2(self):
        data = {"tool_input": {"command": "gh pr checks 9 --watch | tail -2 && gh pr merge 9"}}
        r = run([HOOK, "pre-bash"], json.dumps(data))
        self.assertEqual(r.returncode, 2)
        self.assertIn("병합 안전 관문", r.stderr.decode("utf-8"))

    def test_pre_bash_passes_safe(self):
        data = {"tool_input": {"command": "gh pr checks 9 --watch && gh pr merge 9"}}
        self.assertEqual(run([HOOK, "pre-bash"], json.dumps(data)).returncode, 0)

    def test_bad_json_passes(self):
        self.assertEqual(run([HOOK, "pre-bash"], "not json").returncode, 0)

    def test_post_bash_merge_reminds_jitu(self):
        data = {"tool_input": {"command": "gh pr merge 9 --squash"}, "tool_response": "Merged pull request"}
        r = run([HOOK, "post-bash"], json.dumps(data), {"JITU_LOOP_FORCE_JITU": "1"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("predict add", r.stdout.decode("utf-8"))

    def test_post_bash_silent_for_other_persona(self):
        data = {"tool_input": {"command": "gh pr merge 9 --squash"}, "tool_response": "Merged pull request"}
        r = run([HOOK, "post-bash"], json.dumps(data), {"JITU_LOOP_FORCE_JITU": "0"})
        self.assertEqual(r.stdout.decode("utf-8").strip(), "")

    def test_post_bash_revert_reminds_gap(self):
        data = {"tool_input": {"command": "git revert abc123"}}
        r = run([HOOK, "post-bash"], json.dumps(data), {"JITU_LOOP_FORCE_JITU": "1"})
        self.assertIn("gap add", r.stdout.decode("utf-8"))

    def test_post_bash_failed_merge_silent(self):
        data = {"tool_input": {"command": "gh pr merge 9 --squash"}, "tool_response": "X Pull request is not mergeable"}
        r = run([HOOK, "post-bash"], json.dumps(data), {"JITU_LOOP_FORCE_JITU": "1"})
        self.assertEqual(r.stdout.decode("utf-8").strip(), "")

    def test_prompt_greeting_prints_due(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"JITU_PO_DIR": d, "JITU_PO_TODAY": "2026-10-06"}
            run([TOOL, "gap", "add", "--what", "사고", "--missing", "검사"], env=env)
            # 훅은 JITU_PO_DIR을 물려받아 같은 저장소를 본다
            r = run([HOOK, "prompt"], json.dumps({"prompt": "하이 지투"}), env)
            out = r.stdout.decode("utf-8")
            self.assertIn("지투 루프 점검", out)
            self.assertIn("검사 공백", out)

    def test_prompt_other_message_silent(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"JITU_PO_DIR": d}
            run([TOOL, "gap", "add", "--what", "사고", "--missing", "검사"], env=env)
            r = run([HOOK, "prompt"], json.dumps({"prompt": "지금 상태 알려줘"}), env)
            self.assertEqual(r.stdout.decode("utf-8").strip(), "")

    def test_prompt_nothing_due_silent(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"JITU_PO_DIR": d, "JITU_PO_TODAY": "2026-10-06"}
            run([TOOL, "kpi", "add", "--active", "2", "--views", "10", "--cites", "1", "--misses", "0", "--feedback", "0"], env=env)
            r = run([HOOK, "prompt"], json.dumps({"prompt": "하이~ 지투"}), env)
            self.assertEqual(r.stdout.decode("utf-8").strip(), "")


class LoopToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_PO_TODAY": "2026-10-06"}

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, *args, today=None):
        env = dict(self.env)
        if today:
            env["JITU_PO_TODAY"] = today
        r = run([TOOL] + list(args), env=env)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8"))
        return r.stdout.decode("utf-8")

    def test_gap_open_until_check_added(self):
        self.tool("gap", "add", "--what", "CI 실패 병합", "--missing", "종료 코드 가림")
        self.assertIn("검사 공백", self.tool("due"))
        self.tool("gap", "close", "G-1", "--added", "병합 안전 훅")
        self.assertNotIn("검사 공백", self.tool("due"))

    def test_kpi_due_after_seven_days(self):
        self.tool("kpi", "add", "--active", "2", "--views", "150", "--cites", "50", "--misses", "6", "--feedback", "0")
        self.assertEqual(self.tool("due", "--quiet", today="2026-10-12").strip(), "")
        self.assertIn("지표 측정", self.tool("due", today="2026-10-13"))

    def test_kpi_never_measured_is_due(self):
        self.assertIn("한 번도 안 쟀다", self.tool("due"))

    def test_feedback_new_is_due_next_day_not_same_day(self):
        self.tool("feedback", "add", "--source", "사용기록", "--text", "doc 이름 ux로 호출해 미스")
        self.assertNotIn("고객 신호", self.tool("due", today="2026-10-06"))
        self.assertIn("분류 안 함", self.tool("due", today="2026-10-07"))
        self.tool("feedback", "triage", "F-1", "--kind", "UX", "--action", "별칭 검토")
        self.assertNotIn("분류 안 함", self.tool("due", today="2026-10-07"))

    def test_feedback_triaged_needs_reply_after_a_week(self):
        self.tool("feedback", "add", "--source", "feedback도구", "--text", "불편")
        self.tool("feedback", "triage", "F-1", "--kind", "UX", "--state", "backlog", "--action", "백로그")
        self.assertIn("회신 안 함", self.tool("due", today="2026-10-14"))
        self.tool("feedback", "triage", "F-1", "--kind", "UX", "--state", "replied", "--reply", "컨펌 문안 발송")
        self.assertNotIn("회신 안 함", self.tool("due", today="2026-10-14"))

    def test_prediction_due_and_hit_rate(self):
        self.tool("predict", "add", "--change", "FAQ 추가", "--expect", "피드백 1건 이상", "--metric", "feedback 수", "--check-on", "2026-10-13")
        self.assertNotIn("예측 점검", self.tool("due", today="2026-10-12"))
        self.assertIn("예측 점검", self.tool("due", today="2026-10-13"))
        self.tool("predict", "check", "P-1", "--actual", "0건", "--verdict", "빗나감", "--lesson", "안내만으론 부족")
        out = self.tool("predict", "list")
        self.assertIn("적중률: 0/1", out)
        self.assertNotIn("예측 점검", self.tool("due", today="2026-10-13"))


if __name__ == "__main__":
    unittest.main()
