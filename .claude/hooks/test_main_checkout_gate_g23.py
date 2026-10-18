"""main-checkout-gate.py 시험: python .claude/hooks/test_main_checkout_gate.py

임시 폴더에 메인 체크아웃(.git 디렉터리)과 연결 워크트리(.git 파일)를 만들어 판정을 확인한다.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

H = Path(__file__).with_name("main-checkout-gate.py")


def git(*a, cwd):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


tmp = Path(tempfile.mkdtemp(prefix="mcg_")).resolve()
main = tmp / "main"
wt = tmp / "wt"
other = tmp / "plain"
main.mkdir()
other.mkdir()
git("init", "-q", "-b", "main", cwd=main)
git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i", cwd=main)
git("worktree", "add", "-q", str(wt), "-b", "claude/x", cwd=main)
(main / "sub").mkdir()


def run(cmd, cwd, tool="Bash", project=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project or main))
    raw = json.dumps({"tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(cwd)}).encode("utf-8")
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True, env=env).returncode


M, W = str(main), str(wt)
# (명령, cwd, 기대 exit, 프로젝트 폴더)
cases = [
    # 메인 폴더 보호(차단)
    ("git commit -m x", main, 2, main),
    ("git checkout -b claude/new", main, 2, main),
    ("git switch -c claude/new", main, 2, main),
    ("git checkout claude/other", main, 2, main),
    ("git commit -m x", main / "sub", 2, main),
    (f"git -C {M} commit -m x", wt, 2, main),
    (f'git -C "{M}" commit -m x', wt, 2, main),
    ("git -C ../main commit -m x", wt, 2, main),
    ("git -C . commit -m x", main, 2, main),
    (f"git -C {M} checkout -b claude/n", wt, 2, main),
    (f"cd {M} && git commit -m x", wt, 2, main),
    (f"cd {M}; git commit -m x", wt, 2, main),
    ("cd ../main && git commit -m x", wt, 2, main),
    ("cd sub && git commit -m x", main, 2, main),
    ("git add -A && git commit -m x", main, 2, main),
    ("echo hi | git commit -m x", main, 2, main),
    ("git -c user.name=a commit -m x", main, 2, main),
    ("cd $SOMEWHERE && git commit -m x", wt, 2, main),
    ("git -C $REPO commit -m x", wt, 2, main),
    ("git -C ~/x commit -m x", wt, 2, main),
    ("Set-Location " + M + "; git commit -m x", wt, 2, main),
    # 워크트리 통과
    ("git commit -m x", wt, 0, main),
    ("git checkout -b claude/new", wt, 0, main),
    ("git switch -c claude/new", wt, 0, main),
    (f"git -C {W} commit -m x", main, 0, main),
    (f"git -C {W} checkout -b claude/y", main, 0, main),
    ("git -C ../wt commit -m x", main, 0, main),
    (f"cd {W} && git commit -m x", main, 0, main),
    (f"cd {W}; git checkout -b claude/z", main, 0, main),
    # 워크트리가 프로젝트 폴더여도 메인은 계속 보호
    ("git commit -m x", main, 2, wt),
    ("git commit -m x", wt, 0, wt),
    # 복합: 앞에서 워크트리로 갔다가 메인으로 되돌아가면 차단
    (f"cd {W} && git status && cd {M} && git commit -m x", main, 2, main),
    # 대상 아님
    ("git status", main, 0, main),
    ("git checkout main", main, 0, main),
    ("git checkout -- file.txt", main, 0, main),
    ("git log --oneline", main, 0, main),
    ("echo hello", main, 0, main),
    ("git commit -m x", other, 0, main),
    # 따옴표 안의 구분자는 명령을 나누지 않는다
    ('git -C ' + W + ' commit -m "a; b"', main, 0, main),
]

bad = []
for cmd, cwd, want, proj in cases:
    got = run(cmd, cwd, project=proj)
    if got != want:
        bad.append((cmd, str(cwd), want, got))
# PowerShell 도구도 동일
if run(f"git -C {M} commit -m x", wt) != 2:
    bad.append(("PowerShell git -C main", "wt", 2, "?"))
# Read 같은 다른 도구는 통과
if run("git commit", main, tool="Read") != 0:
    bad.append(("non-bash tool", "main", 0, "?"))
# 입력이 깨져도 통과(훅 자체 오류로 작업을 막지 않음)
r = subprocess.run([sys.executable, str(H)], input=b"not json", capture_output=True)
if r.returncode != 0:
    bad.append(("bad json", "", 0, r.returncode))

total = len(cases) + 3
for b in bad:
    print("FAIL", b)
print(f"main-checkout-gate: {total - len(bad)}/{total} 통과")
sys.exit(1 if bad else 0)
