"""check-dash.py 시험: python .claude/hooks/test_check_dash.py
임시 git 저장소(origin이 hansunghee7.github.io)를 만들어, 새로 쓴 줄의 긴 줄표는 막고(exit 2) 나머지는 통과(exit 0)시키는지 본다."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

H = Path(__file__).with_name("check-dash.py")
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *a], check=True, capture_output=True, env=ENV)


def mkrepo(root, origin="https://github.com/hansunghee7/hansunghee7.github.io.git", config=""):
    root.mkdir()
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", origin)
    if config:
        (root / "_config.yml").write_text(config, encoding="utf-8")
    return root


def run(path, tool="Write"):
    raw = json.dumps({"tool_name": tool, "tool_input": {"file_path": str(path)}}).encode()
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True, env=ENV).returncode


def put(repo, name, text):
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


bad = []
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    repo = mkrepo(td / "site", config="exclude:\n  - 내부문서/\n  - 진행상황.md\n")
    block = {
        "새 md 파일의 긴 줄표": ("a.md", "문장 — 설명\n"),
        "en dash": ("b.md", "범위 3–5\n"),
        "html도 검사": ("c.html", "<p>가 — 나</p>\n"),
        "코드 펜스 밖": ("d.md", "```\n— 코드\n```\n본문 — 이건 걸림\n"),
    }
    ok = {
        "줄표 없음": ("e.md", "쉼표, 괄호(예시)로 쓴 글\n"),
        "인용 블록": ("f.md", "> 남의 글 — 그대로\n"),
        "코드 펜스 안": ("g.md", "```\na — b\n```\n"),
        "규칙 설명 줄": ("h.md", "긴 줄표(—)는 쓰지 않는다\n"),
        "md가 아닌 파일": ("i.txt", "a — b\n"),
        "exclude 폴더": ("내부문서/j.md", "a — b\n"),
        "exclude 파일": ("진행상황.md", "a — b\n"),
    }
    for label, (n, t) in block.items():
        if run(put(repo, n, t)) != 2:
            bad.append(f"막아야함:{label}")
    for label, (n, t) in ok.items():
        if run(put(repo, n, t)) != 0:
            bad.append(f"통과해야함:{label}")
    # 이미 커밋된 줄표는 건드리지 않고, 새로 추가한 줄만 본다
    old = put(repo, "old.md", "옛 문장 — 이미 있음\n")
    git(repo, "add", "old.md"); git(repo, "commit", "-q", "-m", "old")
    if run(old) != 0:
        bad.append("통과해야함:커밋된 기존 줄표")
    old.write_text("옛 문장 — 이미 있음\n새 문장 — 방금 추가\n", encoding="utf-8")
    if run(old) != 2:
        bad.append("막아야함:기존 파일에 새로 추가한 줄표")
    # 다른 저장소(origin이 다름)는 이 정책 대상이 아님
    other = mkrepo(td / "other", origin="https://github.com/example/other.git")
    if run(put(other, "k.md", "a — b\n")) != 0:
        bad.append("통과해야함:다른 저장소")
    # 파일 없음 / 깨진 입력 / 다른 도구는 조용히 통과
    if run(repo / "없는파일.md") != 0:
        bad.append("통과해야함:없는 파일")
    if subprocess.run([sys.executable, str(H)], input=b"not json", capture_output=True, env=ENV).returncode != 0:
        bad.append("통과해야함:깨진 입력")

n = 4 + 7 + 5
print("통과" if not bad else "실패: " + ", ".join(bad), f"({n - len(bad)}/{n})")
sys.exit(1 if bad else 0)
