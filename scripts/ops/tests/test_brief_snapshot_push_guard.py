"""brief_snapshot.push 가드: main이 아닌 브랜치면 커밋·push 없이 1을 돌려준다."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import brief_snapshot  # noqa: E402


def _git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout.strip()


def _repo(tmp_path, branch):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], stdin=subprocess.DEVNULL, capture_output=True, check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], stdin=subprocess.DEVNULL, capture_output=True, check=True)
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "remote", "add", "origin", str(bare))
    (work / "a.txt").write_text("a")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-qm", "init")
    _git(work, "push", "-q", "origin", "main")
    if branch != "main":
        _git(work, "checkout", "-q", "-b", branch)
    snap = work / "snap.json"
    snap.write_text("{}")
    return work, bare, snap


def test_non_main_branch_is_refused(tmp_path):
    work, bare, snap = _repo(tmp_path, "note/other")
    before = _git(work, "rev-parse", "HEAD")
    assert brief_snapshot.push(snap, "2026-10-20", cxo=work) == 1
    assert _git(work, "rev-parse", "HEAD") == before
    assert _git(work, "diff", "--cached", "--name-only") == ""
    assert _git(bare, "rev-parse", "main") == before


def test_main_branch_pushes(tmp_path):
    work, bare, snap = _repo(tmp_path, "main")
    assert brief_snapshot.push(snap, "2026-10-20", cxo=work) == 0
    assert _git(bare, "rev-parse", "main") == _git(work, "rev-parse", "HEAD")
