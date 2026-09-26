"""saegim-gate.py 시험: 사장님 앞 3경로만 막고, 조회 기록·오류·통과 장치가 있으면 통과하는지 확인한다."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("saegim_gate", Path(__file__).parent / "saegim-gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def transcript(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for ln in lines:
        f.write(json.dumps(ln, ensure_ascii=False) + "\n")
    f.close()
    return f.name


def use(name, id_):
    return {"message": {"role": "assistant", "content": [{"type": "tool_use", "id": id_, "name": name, "input": {}}]}}


def result(id_, err=False):
    return {"message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": id_, "is_error": err, "content": "x"}]}}


ART = {"tool_name": "Artifact", "tool_input": {"action": "publish", "file_path": "a.html"}}


class GateTest(unittest.TestCase):
    def run_gate(self, event, lines, project_dir=""):
        event = dict(event, transcript_path=transcript(lines))
        return gate.decide(event, project_dir)[0]

    def test_artifact_publish_without_lookup_is_blocked(self):
        self.assertEqual(self.run_gate(ART, []), 2)

    def test_html_publish_after_lookup_only_is_blocked(self):
        # 9/26: 조회 한 번은 통과권이 아니다. 화면(HTML)은 부품별 규칙(draft_screen parts)까지
        self.assertEqual(self.run_gate(ART, [use("mcp__saegim__lookup", "t1"), result("t1")]), 2)

    def test_html_publish_after_draft_screen_with_parts_passes(self):
        d = {"message": {"role": "assistant", "content": [{"type": "tool_use", "id": "d1", "name": "mcp__saegim__draft_screen", "input": {"doc": "UX_GUIDE", "parts": ["목록", "버튼"]}}]}}
        self.assertEqual(self.run_gate(ART, [d, result("d1")]), 0)

    def test_html_publish_after_draft_screen_without_parts_is_blocked(self):
        d = {"message": {"role": "assistant", "content": [{"type": "tool_use", "id": "d1", "name": "mcp__saegim__draft_screen", "input": {"doc": "UX_GUIDE"}}]}}
        self.assertEqual(self.run_gate(ART, [d, result("d1")]), 2)

    def test_markdown_publish_after_lookup_passes(self):
        md = {"tool_name": "Artifact", "tool_input": {"action": "publish", "file_path": "a.md"}}
        self.assertEqual(self.run_gate(md, [use("mcp__saegim__lookup", "t1"), result("t1")]), 0)

    def test_mail_to_boss_is_blocked_without_lookup(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "python mailbox/mailbox.py send 사장님 \"제목\" --from 탐 --ask x"}}
        self.assertEqual(self.run_gate(ev, []), 2)

    def test_mail_to_other_agent_is_not_gated(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "python mailbox/mailbox.py send 마야 \"제목\" --from 탐"}}
        self.assertEqual(self.run_gate(ev, []), 0)

    def test_ordinary_bash_is_not_gated(self):
        self.assertEqual(self.run_gate({"tool_name": "Bash", "tool_input": {"command": "git status"}}, []), 0)

    def test_artifact_non_publish_actions_pass(self):
        for a in ("read", "list", "delete", "open", "pin"):
            self.assertEqual(self.run_gate({"tool_name": "Artifact", "tool_input": {"action": a}}, []), 0, a)

    def test_send_user_file_is_gated(self):
        self.assertEqual(self.run_gate({"tool_name": "SendUserFile", "tool_input": {"files": ["a"]}}, []), 2)

    def test_outage_when_last_saegim_call_errored(self):
        self.assertEqual(self.run_gate(ART, [use("mcp__saegim__lookup", "t1"), result("t1", err=True)]), 0)
        self.assertEqual(self.run_gate(ART, [use("mcp__saegim__cite", "t2"), result("t2", err=True)]), 0)

    def test_outage_marker_file_passes(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".claude"))
        open(os.path.join(d, ".claude", "saegim-outage"), "w").close()
        self.assertEqual(self.run_gate(ART, [], project_dir=d), 0)

    def test_unreadable_transcript_fails_open(self):
        ev = dict(ART, transcript_path="C:/does/not/exist.jsonl")
        self.assertEqual(gate.decide(ev, "")[0], 0)

    def test_reading_ux_guide_md_is_gated(self):
        ev = {"tool_name": "Read", "tool_input": {"file_path": "docs/UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, []), 2)

    def test_reading_ux_guide_md_after_lookup_is_still_gated(self):
        # 2026-09-24: 원문 열람은 대표 승인. 새김 조회를 했어도 원문은 못 연다
        ev = {"tool_name": "Read", "tool_input": {"file_path": "docs/UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, [use("mcp__saegim__lookup", "t1"), result("t1")]), 2)

    def test_reading_private_original_is_gated(self):
        ev = {"tool_name": "Read", "tool_input": {"file_path": r"C:\work\simplifier-saegim\docs\guides\UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, []), 2)

    def test_shell_cat_of_private_original_is_gated(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "cat /c/work/simplifier-saegim/docs/guides/UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, []), 2)

    def test_reading_other_docs_is_not_gated(self):
        ev = {"tool_name": "Read", "tool_input": {"file_path": "docs/진행상황.md"}}
        self.assertEqual(self.run_gate(ev, []), 0)

    def test_reading_ux_guide_md_backslash_path_is_gated(self):
        ev = {"tool_name": "Read", "tool_input": {"file_path": r"C:\work\hansunghee7.github.io\docs\UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, []), 2)

    def test_ux_guide_outage_marker_no_longer_passes(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".claude"))
        open(os.path.join(d, ".claude", "saegim-outage"), "w").close()
        ev = {"tool_name": "Read", "tool_input": {"file_path": "docs/UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, [], project_dir=d), 2)

    def test_ux_guide_boss_approval_marker_passes(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".claude"))
        open(os.path.join(d, ".claude", "uxguide-approved"), "w").close()
        ev = {"tool_name": "Read", "tool_input": {"file_path": "docs/UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, [], project_dir=d), 0)

    def test_jitu_worktree_original_passes(self):
        ev = {"tool_name": "Read", "tool_input": {"file_path": r"C:\work\jitu-saegim-wt\docs\guides\UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, []), 0)

    def test_jitu_worktree_shell_passes(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "cd /c/work/jitu-saegim-wt && grep -n '^#' docs/guides/UX_GUIDE.md"}}
        self.assertEqual(self.run_gate(ev, []), 0)

if __name__ == "__main__":
    unittest.main()
