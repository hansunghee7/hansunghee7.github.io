import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("g", os.path.join(os.path.dirname(__file__), "rejection-evidence-gate.py"))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class T(unittest.TestCase):
    def test_write_rejection_without_evidence_blocked(self):
        why, _ = g.check("Write", {"file_path": "C:/x/docs/a.md", "content": "- 하지 않는 것: 채널 방식(유휴 세션 미기상 이슈)"})
        self.assertIsNotNone(why)

    def test_write_with_evidence_passes(self):
        why, nm = g.check("Write", {"file_path": "C:/x/docs/a.md",
                                     "content": "- 하지 않는 것: 웹훅 [실측: C:/work/_ops/x/log.jsonl 지연 30초]"})
        self.assertIsNone(why); self.assertIsNone(nm)

    def test_no_measure_reason_passes_and_reports(self):
        why, nm = g.check("Write", {"file_path": "C:/x/docs/a.md", "content": "기각한다 [실측 불가: 계정 정지 위험]"})
        self.assertIsNone(why); self.assertEqual(nm, "계정 정지 위험")

    def test_edit_existing_line_not_reflagged(self):
        old = "- 하지 않는 것: 웹훅\n- 무엇: A"
        why, _ = g.check("Edit", {"file_path": "C:/x/docs/a.md", "old_string": old, "new_string": old + "\n- 새 줄: B"})
        self.assertIsNone(why)

    def test_edit_new_rejection_blocked(self):
        why, _ = g.check("Edit", {"file_path": "C:/x/docs/a.md", "old_string": "- A", "new_string": "- A\n- 채널은 쓰지 않기로 함"})
        self.assertIsNotNone(why)

    def test_bash_proc_add_checked(self):
        why, _ = g.check("Bash", {"command": 'python scripts/ops/proc.py add 노트 "채널 기각" --do "이슈 #44380"'})
        self.assertIsNotNone(why)

    def test_bash_other_commands_ignored(self):
        why, _ = g.check("Bash", {"command": 'grep -n "기각" docs/a.md'})
        self.assertIsNone(why)

    def test_hook_and_history_files_skipped(self):
        for p in ("C:/r/.claude/hooks/x.py", "C:/r/docs/CLAUDE_md_근거_이력.md", "C:/r/docs/_이력/a.md"):
            why, _ = g.check("Write", {"file_path": p, "content": "하지 않는 것: X"})
            self.assertIsNone(why, p)

    def test_unrelated_text_passes(self):
        why, _ = g.check("Write", {"file_path": "C:/x/docs/a.md", "content": "배포를 진행했다. 배제적이지 않은 설계."})
        self.assertIsNone(why)


if __name__ == "__main__":
    unittest.main()
