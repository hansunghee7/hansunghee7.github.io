"""cloud_event.py의 시험(git은 바꿔 끼운 가짜, 외부 호출 없음). 실제 이벤트 모양은 2026-10-07 E2·E3 실측에서 가져왔다."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("cloud_event", Path(__file__).parent / "cloud_event.py")
ce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ce)

SHA = "a261b7b290674fe3e5cf4821858561bed48c3a84"
FILE = "mailbox/signals/E3-idle-wake.json"
# 실제로 도착한 모양: 댓글의 중괄호가 &#123; &#125;로 바뀌어 온다
COMMENT = "&#123;\"v\":1,\"event\":\"signal\",\"files\":\"%s\",\"sha\":\"%s\"&#125;" % (FILE, SHA)


def event(author="github-actions[bot]", comment=COMMENT, cid=6031197954):
    body = json.dumps({"author": author, "comment": comment, "comment_id": cid, "pr": "o/r#422"}, ensure_ascii=False)
    return ("<wake reason=\"external-event\">\n  <event source=\"github\" kind=\"issue_comment.created\" trust=\"relay\">\n"
            "    <!-- GitHub comment -->\n    " + body + "\n  </event>\n</wake>\n")


class Fake:
    """run_git 대용: 신호 파일과 origin/main 파일 목록을 흉내 낸다."""
    def __init__(self, payload=None, main_files=()):
        self.payload, self.main_files, self.calls = payload, set(main_files), []

    def __call__(self, args, cwd):
        self.calls.append(args)
        if args[0] == "fetch":
            return 0, ""
        if args[0] == "show":
            return (0, json.dumps(self.payload)) if self.payload is not None else (128, "")
        if args[0] == "ls-tree":
            ref = args[-1]
            return 0, (ref + "\n") if ref in self.main_files else ""
        return 1, ""


class CloudEventTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        ce.STATE = Path(self.tmp.name) / "seen.json"
        self.orig = ce.run_git

    def tearDown(self):
        ce.run_git = self.orig
        self.tmp.cleanup()

    def test_parse_real_shape_and_unescape(self):
        ev = ce.parse_event(event())
        self.assertEqual(ev["author"], "github-actions[bot]")
        c = ce.decode_comment(ev["comment"])
        self.assertEqual(c["v"], 1)
        self.assertEqual(c["sha"], SHA)

    def test_handled_signal_without_ref(self):
        ce.run_git = Fake({"v": 1, "event": "exp_signal", "id": "E3", "by": "cloud"})
        st, summary, rc = ce.handle(event())
        self.assertEqual((st, rc), ("HANDLED", 0))
        self.assertIn("exp_signal id=E3", summary)

    def test_untrusted_author_ignored(self):
        ce.run_git = Fake({"v": 1, "event": "task_done", "id": "x"})
        st, _, rc = ce.handle(event(author="stranger"))
        self.assertEqual((st, rc), ("IGNORED", 3))
        self.assertEqual(ce.run_git.calls, [])  # 불신 작성자는 git도 부르지 않는다

    def test_duplicate_comment_ignored(self):
        ce.run_git = Fake({"v": 1, "event": "exp_signal", "id": "E3"})
        self.assertEqual(ce.handle(event())[0], "HANDLED")
        st, _, rc = ce.handle(event())
        self.assertEqual((st, rc), ("IGNORED", 3))

    def test_same_payload_id_in_new_comment_skipped(self):
        ce.run_git = Fake({"v": 1, "event": "exp_signal", "id": "E3"})
        ce.handle(event(cid=1))
        st, summary, rc = ce.handle(event(cid=2))
        self.assertEqual((st, rc), ("HANDLED", 0))
        self.assertIn("이미 처리", summary)

    def test_ref_checked_against_main(self):
        ref = "tasks/done/2026-10-07_가나다.md"
        ce.run_git = Fake({"v": 1, "event": "task_done", "id": "t1", "by": "local-tam", "ref": ref}, main_files=[ref])
        st, summary, rc = ce.handle(event())
        self.assertEqual((st, rc), ("HANDLED", 0))
        self.assertIn("ref=ok", summary)

    def test_missing_ref_fails(self):
        ce.run_git = Fake({"v": 1, "event": "task_done", "id": "t1", "ref": "tasks/done/none.md"})
        st, _, rc = ce.handle(event())
        self.assertEqual((st, rc), ("FAILED", 4))

    def test_path_injection_ref_rejected(self):
        for bad in ("../etc/passwd", "tasks/done/../../x", "docs/CLAUDE.md", "tasks/done/a/b.md"):
            ce.STATE = Path(self.tmp.name) / ("seen_%d.json" % hash(bad))
            ce.run_git = Fake({"v": 1, "event": "task_done", "id": "t-" + bad, "ref": bad}, main_files=[bad])
            st, _, rc = ce.handle(event())
            self.assertEqual((st, rc), ("FAILED", 4), bad)

    def test_missing_or_bad_signal_file_fails(self):
        ce.run_git = Fake(None)
        self.assertEqual(ce.handle(event())[2], 4)
        ce.run_git = Fake({"v": 2, "event": "signal", "id": "z"})
        self.assertEqual(ce.handle(event(cid=9))[2], 4)

    def test_bad_sha_or_file_never_reaches_git(self):
        bad = "&#123;\"v\":1,\"files\":\"../../secret\",\"sha\":\"--upload-pack=x\"&#125;"
        ce.run_git = Fake({"v": 1, "event": "signal", "id": "q"})
        st, _, rc = ce.handle(event(comment=bad))
        self.assertEqual(rc, 4)
        self.assertEqual(ce.run_git.calls, [])

    def test_garbage_input_ignored(self):
        self.assertEqual(ce.handle("아무 말")[2], 3)


if __name__ == "__main__":
    unittest.main()
