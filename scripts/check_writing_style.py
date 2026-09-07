#!/usr/bin/env python3
"""새로 추가된 글에 긴 줄표(em dash, en dash)가 섞여 있는지 검사한다.

왜 이 검사가 있나
-----------------
문서에 "쓰지 않는다"고 적어두는 것만으로는 안 지켜졌다. 심플리파이어 웨이
원칙 9, WRITING_GUIDE.md 6절, SNS_라이팅_가이드.md 4절에 이미 규칙이
있었는데도 2026-09-07에 이 규칙을 적은 문서 자체에서 여러 번 어겨졌다.
사람(에이전트)이 매번 기억하는 대신, 기계가 커밋마다 확인한다.

무엇을 잡나
-----------
긴 줄표 두 종류: em dash(—, U+2014), en dash(–, U+2013). 둘 다 사람이
키보드로 치기 번거로운 기호라 AI가 쓴 글의 흔적으로 읽힌다. 일반 하이픈(-)은
사람이 흔히 쓰는 기호라 잡지 않는다.

PR의 변경분(base와 head 사이 새로 추가된 줄)만 본다. 기존 파일에 이미
있던 줄까지 잡으면 관련 없는 PR마다 헛경보가 뜨고, 헛경보가 잦은 검사는
무시당한다(check_exposure_changes.py와 같은 이유).

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
    for path in changed_files(base, head):
        if path == SELF_PATH or not path.endswith(CONTENT_EXT):
            continue
        for line_no, text in added_lines(base, path, head):
            if LONG_DASH.search(text):
                snippet = text.strip()[:90]
                findings.append((path, line_no, snippet))
    return findings


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    findings = find_violations(base, head)

    if not findings:
        print("긴 줄표(em/en dash) 없음.")
        return 0

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
