#!/usr/bin/env python3
"""새로 추가된 글에 긴 줄표(em dash, en dash)가 섞여 있는지 검사한다.

왜 이 검사가 있나
-----------------
문서에 "쓰지 않는다"고 적어두는 것만으로는 안 지켜졌다. 심플리파이어 웨이
원칙 9, WRITING_GUIDE.md 6절, SNS_라이팅_가이드.md 4절에 이미 규칙이
있었는데도 2026-09-07에 이 규칙을 적은 문서 자체에서 여러 번 어겨졌다.
사람(에이전트)이 매번 기억하는 대신, 기계가 커밋마다 확인한다.

검사 범위(2026-09-16 축소, 사장님 지시)
---------------------------------------
이 규칙은 원래 방문자가 읽는 글(블로그 본문 등)의 AI 말투를 막기 위한
것이다. 그런데 저장소 전체 .md/.html에 걸어두니 진행상황.md·지시서 같은
내부 운영 문서 PR까지 막아서 내부 생산성에 방해가 됐다(2026-09-16, PR
#571 사례). **`_config.yml`의 `exclude:` 목록(Jekyll이 실제로 사이트에
안 올리는 내부 문서)에 속한 파일은 이 검사에서도 제외한다** — 그 목록이
이미 "내부 문서 대 실제 서비스 페이지"를 구분해뒀으므로 별도 목록을
새로 안 만들고 그대로 재사용한다.

무엇을 잡나
-----------
긴 줄표 두 종류: em dash(—, U+2014), en dash(–, U+2013). 둘 다 사람이
키보드로 치기 번거로운 기호라 AI가 쓴 글의 흔적으로 읽힌다. 일반 하이픈(-)은
사람이 흔히 쓰는 기호라 잡지 않는다.

PR의 변경분(base와 head 사이 새로 추가된 줄)만 본다. 기존 파일에 이미
있던 줄까지 잡으면 관련 없는 PR마다 헛경보가 뜨고, 헛경보가 잦은 검사는
무시당한다(check_exposure_changes.py와 같은 이유).

홈페이지 글 분량(2026-10-02 추가, 사장님 확정)
-----------------------------------------------
`log_assets/markdown/`에 **새로 추가된** 글 중 frontmatter `date`가
2026-10-03 이후인 글은 본문(frontmatter 제외, 공백 포함)이 1,500자를 넘으면
막는다. 목표는 1,000자 안팎이다(WRITING_GUIDE.md 5-2절). 옛 기준 "2,500자
이내"는 상한만 있어 1,540자 초안이 그대로 컨펌까지 올라간 일이 있었다
(2026-10-02 사장님 "글이 너무 길어요"). 기존 글 수정은 잡지 않는다.

사용법: python scripts/check_writing_style.py [base] [head]
기본값: base=origin/main, head=HEAD
"""
import re
import subprocess
import sys

LONG_DASH = re.compile("[—–]")

# 코드·데이터 파일은 검사 대상이 아니다. 사람이 읽는 글이 있는 확장자만 본다.
CONTENT_EXT = (".md", ".html")

# 이 스크립트 자신은 예시로 긴 줄표 문자를 담고 있어야 하니 제외한다.
SELF_PATH = "scripts/check_writing_style.py"


def excluded_prefixes(config_path="_config.yml"):
    """_config.yml의 exclude: 목록을 그대로 읽어 경로 접두어 목록으로 쓴다."""
    try:
        text = open(config_path, encoding="utf-8").read()
    except OSError:
        return []
    prefixes = []
    in_exclude = False
    for line in text.splitlines():
        if line.strip() == "exclude:":
            in_exclude = True
            continue
        if not in_exclude:
            continue
        m = re.match(r"^\s*-\s*(\S+)", line)
        if m:
            prefixes.append(m.group(1))
        elif line.strip() and not line.strip().startswith("#"):
            in_exclude = False
    return prefixes


def is_excluded(path, prefixes):
    return any(path == p or path.startswith(p) for p in prefixes)


def git(*args):
    # -c core.quotepath=false: 한글 파일명(예: 진행상황.md)을 이스케이프된
    # 8진수 문자열이 아니라 있는 그대로 출력시킨다. 기본값이면 파일명 비교가
    # 전부 어긋난다.
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        capture_output=True,
        text=True,
    ).stdout


def changed_files(base, head="HEAD"):
    out = git("diff", "--name-only", f"{base}...{head}")
    return [f for f in out.splitlines() if f.strip()]


def added_lines(base, path, head="HEAD"):
    out = git("diff", "--unified=0", f"{base}...{head}", "--", path)
    added = []
    line_no = None
    for line in out.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            line_no = int(match.group(1)) if match else None
            continue
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            if line_no is not None:
                added.append((line_no, line[1:]))
                line_no += 1
    return added


def find_violations(base, head="HEAD"):
    findings = []
    prefixes = excluded_prefixes()
    for path in changed_files(base, head):
        if path == SELF_PATH or not path.endswith(CONTENT_EXT):
            continue
        if is_excluded(path, prefixes):
            continue
        for line_no, text in added_lines(base, path, head):
            if LONG_DASH.search(text):
                snippet = text.strip()[:90]
                findings.append((path, line_no, snippet))
    return findings


POST_DIR = "log_assets/markdown/"
LENGTH_LIMIT = 1500
LENGTH_FROM_DATE = "2026-10-03"


def added_post_files(base, head="HEAD"):
    out = git("diff", "--name-only", "--diff-filter=A", f"{base}...{head}")
    return [f for f in out.splitlines() if f.startswith(POST_DIR) and f.endswith(".md")]


def post_body_length(path):
    """(본문 글자 수, date 문자열)을 돌려준다. frontmatter가 없으면 (None, None)."""
    text = open(path, encoding="utf-8").read()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None
    m = re.search(r"^date:\s*(\S+)", parts[1], re.M)
    return len(parts[2].strip()), (m.group(1) if m else "")


def find_long_posts(base, head="HEAD"):
    long_posts = []
    for path in added_post_files(base, head):
        length, date = post_body_length(path)
        if length is None or date[:10] < LENGTH_FROM_DATE:
            continue
        if length > LENGTH_LIMIT:
            long_posts.append((path, length))
    return long_posts


def verify_refs(base, head):
    """커밋을 못 찾거나 공통 조상이 없으면 '줄표 없음'으로 통과하지 않고 실패한다(10/6 H1 P1)."""
    for ref in (base, head):
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], capture_output=True).returncode:
            print(f"검사 불가: 커밋 {ref}을 찾을 수 없습니다.")
            return False
    if subprocess.run(["git", "merge-base", base, head], capture_output=True).returncode:
        print(f"검사 불가: {base}와 {head}의 공통 조상이 없습니다(얕은 clone이면 fetch-depth를 늘리세요).")
        return False
    return True


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    if not verify_refs(base, head):
        return 1
    findings = find_violations(base, head)
    long_posts = find_long_posts(base, head)

    if long_posts:
        print(f"\n새 홈페이지 글 분량이 {LENGTH_LIMIT}자를 넘습니다(목표 1,000자 안팎, WRITING_GUIDE.md 5-2절):\n")
        for path, length in long_posts:
            print(f"  {path}  {length}자")
        print("\n주제에서 벗어난 문단부터 빼서 줄이세요.")

    if not findings:
        print("긴 줄표(em/en dash) 없음.")
        return 1 if long_posts else 0

    print(f"\n새로 추가된 줄에서 긴 줄표를 발견했습니다 ({len(findings)}건):\n")
    for path, line_no, snippet in findings:
        print(f"  {path}:{line_no}  {snippet}")

    print(
        "\n"
        "긴 줄표(—, en/em dash)는 심플리파이어 웨이 원칙 9, WRITING_GUIDE.md 6절\n"
        "규칙 위반입니다. 쉼표, 줄바꿈, 괄호, 마침표로 잇는 문장으로 바꾸세요.\n"
        "사람이 실제로 쓰는 문장부호가 아니라 AI가 쓴 흔적으로 바로 티가 납니다."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
