import os
import stat
import hashlib
import json
import subprocess
import sys
import shutil
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
SCRIPT = BASE / "dirty_snapshot.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    root = BASE / "test_tmp"
    if root.exists():
        shutil.rmtree(root, onerror=lambda f,pth,e:(os.chmod(pth,stat.S_IWRITE),f(pth)))
    root.mkdir()
    try:
        repo = root / "repo"
        archive = root / "archive"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=str(repo), check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), check=True)
        tracked = {
            "a/tstate.json": "before-state\n",
            "docs/d.md": "before-doc\n",
        }
        for name, content in tracked.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="ascii")
        subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=str(repo), check=True)
        (repo / "a/tstate.json").write_text("changed-state\n", encoding="ascii")
        (repo / "docs/d.md").write_text("changed-doc\n", encoding="ascii")
        additions = {
            "h_send/m.txt": "message\n",
            "reports/r.md": "report\n",
            "new/leak.txt": "sk-AAAAAAAAAAAAAAAAAAAA\n",
        }
        for name, content in additions.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="ascii")
        originals = {path: digest(path) for path in repo.rglob("*") if path.is_file() and ".git" not in path.parts}
        run_result = subprocess.run(
            [sys.executable, str(SCRIPT), str(repo), str(archive)],
            capture_output=True, text=True, encoding="ascii",
        )
        if run_result.returncode:
            raise AssertionError("snapshot returned nonzero")
        if any(digest(path) != value for path, value in originals.items()):
            raise AssertionError("an original file changed")
        day = __import__("datetime").date.today().isoformat()
        output = archive / day
        report = json.loads((output / "dirty_report.json").read_text(encoding="ascii"))
        by_path = {item["path"]: item for item in report["files"]}
        if by_path["a/tstate.json"]["class"] != "runtime" or by_path["a/tstate.json"]["action"] != "copied":
            raise AssertionError("tstate classification or copy failed")
        if by_path["new/leak.txt"]["action"] != "blocked" or (output / "new/leak.txt").exists():
            raise AssertionError("secret pattern was not blocked")
        if report["counts"]["files"] != len(report["files"]):
            raise AssertionError("report counts mismatch")
        if len(report["files"]) != 5 or report["counts"]["copied"] != 4 or report["counts"]["blocked"] != 1:
            raise AssertionError("unexpected report totals")
    finally:
        shutil.rmtree(root, onerror=lambda f,pth,e:(os.chmod(pth,stat.S_IWRITE),f(pth)))


if __name__ == "__main__":
    try:
        run()
        print("TEST PASS")
    except Exception as error:
        print("TEST FAIL: " + str(error))
        raise SystemExit(1)

