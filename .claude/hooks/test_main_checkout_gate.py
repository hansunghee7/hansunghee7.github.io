import json
import os
import subprocess
import sys
import tempfile

H = os.path.join(os.path.dirname(__file__), "main-checkout-gate.py")


def run(payload, project_dir):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = project_dir
    p = subprocess.run(
        [sys.executable, H],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
    )
    return p.returncode


def primary_checkout_dir():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, ".git"))  # 디렉터리 = 원본 체크아웃
    return d


def worktree_dir():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".git"), "w") as f:
        f.write("gitdir: /somewhere/.git/worktrees/x\n")  # 파일 = 전용 워크트리
    return d


def test_blocks_checkout_branch_in_primary():
    d = primary_checkout_dir()
    assert run({"tool_name": "Bash", "tool_input": {"command": "git checkout claude/jitu-ledger-0926d"}}, d) == 2


def test_blocks_checkout_dash_b_in_primary():
    d = primary_checkout_dir()
    assert run({"tool_name": "Bash", "tool_input": {"command": "git checkout -b claude/new-thing origin/main"}}, d) == 2


def test_blocks_switch_in_primary():
    d = primary_checkout_dir()
    assert run({"tool_name": "PowerShell", "tool_input": {"command": "git switch -c claude/new-thing"}}, d) == 2


def test_allows_checkout_main_in_primary():
    d = primary_checkout_dir()
    assert run({"tool_name": "Bash", "tool_input": {"command": "git checkout main"}}, d) == 0


def test_allows_file_restore_in_primary():
    d = primary_checkout_dir()
    assert run({"tool_name": "Bash", "tool_input": {"command": "git checkout -- docs/진행상황.md"}}, d) == 0


def test_allows_branch_switch_in_worktree():
    d = worktree_dir()
    assert run({"tool_name": "Bash", "tool_input": {"command": "git checkout -b claude/new-thing origin/main"}}, d) == 0


def test_skips_when_command_changes_directory():
    d = primary_checkout_dir()
    cmd = "cd ../some-other-worktree && git checkout -b claude/new-thing origin/main"
    assert run({"tool_name": "Bash", "tool_input": {"command": cmd}}, d) == 0


def test_untouched_non_git_command():
    d = primary_checkout_dir()
    assert run({"tool_name": "Bash", "tool_input": {"command": "ls -la"}}, d) == 0


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
