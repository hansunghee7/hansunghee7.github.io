"""마야 작업서 실행기 관문 시험(구PC 없이 로컬에서 돈다)."""
import hashlib, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import maya_jobrunner as jr

KST = timezone(timedelta(hours=9))


def make(tmp, **over):
    root = Path(tmp)
    d = root / "jobs/maya/files/642"
    d.mkdir(parents=True)
    (d / "t.txt").write_text("본문", encoding="utf-8")
    (d / "i.jpg").write_bytes(b"img")
    sh = lambda n: hashlib.sha256((d / n).read_bytes()).hexdigest()
    spec = {"id": "642-li", "run_at": "2026-10-24T09:00:00+09:00", "cmd": "post_linkedin", "post": True,
            "args": {"title": "제목"}, "approved_by": "사장님", "approved_quote": "642 SNS 전 채널 10/24 09:00에 등록",
            "files": {"text": {"path": "jobs/maya/files/642/t.txt", "sha256": sh("t.txt")},
                      "image": {"path": "jobs/maya/files/642/i.jpg", "sha256": sh("i.jpg")}}}
    spec.update(over)
    return root, spec


def test_ok(tmp_path):
    root, spec = make(tmp_path)
    assert jr.problems(spec, root, None) == []


def test_unapproved(tmp_path):
    root, spec = make(tmp_path, approved_by="마야")
    assert any("승인" in x for x in jr.problems(spec, root, None))


def test_cmd_not_allowed(tmp_path):
    root, spec = make(tmp_path, cmd="rm -rf")
    assert any("허용되지" in x for x in jr.problems(spec, root, None))


def test_changed_file_blocked(tmp_path):
    root, spec = make(tmp_path)
    (root / "jobs/maya/files/642/t.txt").write_text("바뀐 본문", encoding="utf-8")
    assert any("sha256" in x for x in jr.problems(spec, root, None))


def test_path_escape_blocked(tmp_path):
    root, spec = make(tmp_path)
    spec["files"]["text"]["path"] = "../outside.txt"
    assert any("밖" in x for x in jr.problems(spec, root, None))


def test_timing():
    spec = {"run_at": "2026-10-24T09:00:00+09:00", "window_min": 120}
    t0 = datetime(2026, 10, 24, 9, 0, tzinfo=KST)
    assert jr.timing(spec, t0 - timedelta(minutes=1)) == "wait"
    assert jr.timing(spec, t0 + timedelta(minutes=1)) == "run"
    assert jr.timing(spec, t0 + timedelta(minutes=121)) == "expired"


def test_argv_post_flag(tmp_path):
    root, spec = make(tmp_path)
    assert jr.build_argv(spec, Path("/x"))[-1] == "--post" or "--title" in jr.build_argv(spec, Path("/x"))
    spec["post"] = False
    assert "--post" not in jr.build_argv(spec, Path("/x"))
