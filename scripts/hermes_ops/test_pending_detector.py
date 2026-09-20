"""pending_detector.py 시험: 임시 git 저장소와 가짜 hermes로 6개 시나리오를 확인한다."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "pending_detector.py"


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8")


class DetectorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.writer = self.tmp / "writer"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.writer)], check=True, capture_output=True)
        for c in (self.writer,):
            git(c, "config", "user.email", "t@example.com")
            git(c, "config", "user.name", "t")
        for d in ("pending", "pending-long"):
            (self.writer / "tasks" / d).mkdir(parents=True)
            (self.writer / "tasks" / d / ".gitkeep").write_text("")
        git(self.writer, "add", "-A")
        git(self.writer, "commit", "-q", "-m", "init")
        git(self.writer, "push", "-q", "origin", "main")
        self.repo = self.tmp / "repo"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.repo)], check=True, capture_output=True)
        self.state = self.tmp / "state.json"
        self.log = self.tmp / "hermes_calls.log"
        self.fake = self.tmp / "fakehermes.py"
        self.fake.write_text(
            "import os, sys\n"
            "open(os.environ['FAKE_LOG'], 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
            "sys.exit(int(os.environ.get('FAKE_RC', '0')))\n"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_detector(self, rc="0", repo=None):
        env = dict(os.environ)
        env.update({
            "DETECTOR_REPO": str(repo or self.repo),
            "DETECTOR_STATE": str(self.state),
            "DETECTOR_HERMES_CMD": f'"{sys.executable}" "{self.fake}"'.replace("\\", "/"),
            "FAKE_LOG": str(self.log),
            "FAKE_RC": rc,
            "PYTHONIOENCODING": "utf-8",
        })
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True,
                           encoding="utf-8", env=env)
        return r.stdout.strip(), r.returncode

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def push_pending(self, name, lane="pending"):
        (self.writer / "tasks" / lane / name).write_text("# 시험 지시서\n")
        git(self.writer, "add", "-A")
        git(self.writer, "commit", "-q", "-m", f"add {name}")
        git(self.writer, "push", "-q", "origin", "main")

    def test_1_empty_pending_is_silent(self):
        out, rc = self.run_detector()
        self.assertEqual((out, rc), ("", 0))
        self.assertEqual(self.calls(), [])

    def test_2_new_file_wakes_poller_once(self):
        self.push_pending("a.md")
        out, rc = self.run_detector()
        self.assertEqual(rc, 0)
        self.assertIn("새 지시서 1건", out)
        self.assertEqual(self.calls(), ["cron run dbec1e96eff3"])
        out2, _ = self.run_detector()                      # 같은 파일로 반복 기동하지 않음
        self.assertEqual(out2, "")
        self.assertEqual(len(self.calls()), 1)

    def test_3_second_new_file_wakes_again(self):
        self.push_pending("a.md")
        self.run_detector()
        self.push_pending("b.md")
        out, _ = self.run_detector()
        self.assertIn("b.md", out)
        self.assertNotIn("a.md", out)
        self.assertEqual(len(self.calls()), 2)

    def test_4_removed_then_readded_wakes_again(self):
        self.push_pending("a.md")
        self.run_detector()
        git(self.writer, "rm", "-q", "tasks/pending/a.md")
        git(self.writer, "commit", "-q", "-m", "done")
        git(self.writer, "push", "-q", "origin", "main")
        self.assertEqual(self.run_detector()[0], "")        # 사라진 파일 기록 정리
        self.push_pending("a.md")
        self.assertIn("a.md", self.run_detector()[0])
        self.assertEqual(len(self.calls()), 2)

    def test_5_fetch_failure_is_warning_not_crash(self):
        bad = self.tmp / "bad"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(bad)], check=True, capture_output=True)
        git(bad, "remote", "set-url", "origin", str(self.tmp / "nowhere.git"))
        out, rc = self.run_detector(repo=bad)
        self.assertEqual(rc, 0)
        self.assertIn("[WARN] git fetch 실패", out)
        self.assertEqual(self.calls(), [])

    def test_6_poller_start_failure_retries_next_time(self):
        self.push_pending("a.md")
        out, rc = self.run_detector(rc="1")
        self.assertEqual(rc, 1)
        self.assertIn("[ERROR]", out)
        out2, rc2 = self.run_detector(rc="0")               # 실패한 파일은 기록되지 않아 다시 시도
        self.assertEqual(rc2, 0)
        self.assertIn("a.md", out2)

    def test_7_long_lane_wakes_only_the_long_poller(self):
        self.push_pending("big.md", lane="pending-long")
        out, rc = self.run_detector()
        self.assertEqual(rc, 0)
        self.assertIn("pending-long", out)
        self.assertEqual(self.calls(), ["cron run 938439795638"])   # 짧은 작업 폴러는 깨우지 않음

    def test_8_lanes_wake_independently(self):
        self.push_pending("big.md", lane="pending-long")
        self.push_pending("small.md", lane="pending")
        self.run_detector()
        self.assertEqual(sorted(self.calls()), ["cron run 938439795638", "cron run dbec1e96eff3"])
        self.assertEqual(self.run_detector()[0], "")                 # 같은 파일로 반복 기동하지 않음


if __name__ == "__main__":
    unittest.main()
