"""todo_detector.py 시험: 임시 원격·복제본으로 첫 실행 기록, 새 지시서 inbox 기록, 알림 판정을 확인한다."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import todo_detector as td  # noqa: E402


def run(*a, cwd):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8")


class PureTest(unittest.TestCase):
    def test_needs_boss(self):
        self.assertTrue(td.needs_boss("# 제목\n사장님확인: 예\n본문"))
        self.assertFalse(td.needs_boss("# 제목\n사장님확인: 아니오 (사장님 결재)\n"))
        self.assertFalse(td.needs_boss("# 제목\n발주: 클라우드"))
        self.assertFalse(td.needs_boss(""))

    def test_new_files(self):
        self.assertEqual(td.new_files(["a", "b"], {"a": 1}), ["b"])


class FlowTest(unittest.TestCase):
    def test_flow(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            origin, work = t / "origin.git", t / "work"
            run("git", "init", "-q", "--bare", "-b", "main", str(origin), cwd=t)
            run("git", "clone", "-q", str(origin), str(work), cwd=t)
            run("git", "config", "user.email", "a@b.c", cwd=work)
            run("git", "config", "user.name", "t", cwd=work)
            (work / "tasks" / "todo").mkdir(parents=True)
            (work / "tasks/todo/old.md").write_text("# old\n사장님확인: 아니오\n", encoding="utf-8")
            run("git", "add", "-A", cwd=work)
            run("git", "commit", "-qm", "x", cwd=work)
            run("git", "push", "-q", "origin", "main", cwd=work)
            sent = t / "sent.txt"
            notify = t / "notify.py"
            notify.write_text(f"import sys\nopen(r'{sent}','a',encoding='utf-8').write(sys.argv[2]+'\\n')\n", encoding="utf-8")
            td.REPO, td.SEEN, td.INBOX = work, t / "seen.json", t / "inbox.log"
            td.NOTIFY = [sys.executable, str(notify)]
            self.assertEqual(td.main(), 0)                      # 첫 실행: 기록만
            self.assertFalse(td.INBOX.exists())
            (work / "tasks/todo/no.md").write_text("# no\n사장님확인: 아니오\n", encoding="utf-8")
            (work / "tasks/todo/yes.md").write_text("# yes\n사장님확인: 예\n", encoding="utf-8")
            run("git", "add", "-A", cwd=work)
            run("git", "commit", "-qm", "y", cwd=work)
            run("git", "push", "-q", "origin", "main", cwd=work)
            self.assertEqual(td.main(), 0)
            log = td.INBOX.read_text(encoding="utf-8")
            self.assertIn("no.md", log)
            self.assertIn("yes.md", log)
            self.assertEqual(sent.read_text(encoding="utf-8").count("새 지시서 도착"), 1)  # 예만 알림
            self.assertIn("yes.md", sent.read_text(encoding="utf-8"))
            self.assertNotIn("no.md", sent.read_text(encoding="utf-8"))
            td.main()                                            # 중복 방지
            self.assertEqual(len(td.INBOX.read_text(encoding="utf-8").splitlines()), 2)
            self.assertEqual(len(json.loads(td.SEEN.read_text(encoding="utf-8"))), 3)


if __name__ == "__main__":
    unittest.main()
