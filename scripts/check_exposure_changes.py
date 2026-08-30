#!/usr/bin/env python3
"""이 변경이 "새로 공개하는 것"이 있는지 검사한다.

왜 이 검사가 있나
-----------------
이 저장소는 main에 push되면 곧바로 라이브다. 그래서 사고는 "미완성 화면이
보인다"가 아니라 **공개로 승격하는 순간이 다른 작업에 묻어서 나가는 것**으로
났다. 2026-08-29 커밋 하나가 About 페이지 작업을 하면서 저서 페이지 2개의
noindex까지 같이 떼어내 승인 없이 검색 노출됐고, PR #9/#10으로 되돌렸다.

승격은 작은 수정 여러 개다 -- noindex 제거 + 사이트맵 추가 + GNB 링크 추가 +
preview 플래그 해제. 하나하나는 한 줄이라 리뷰에서 눈에 안 띈다.
그래서 사람이 아니라 기계가 본다.

무엇을 하나
-----------
PR의 변경분에서 "노출이 넓어지는 신호"를 찾아 목록으로 출력한다.
찾았는데 승인 표시가 없으면 실패시킨다 -- 막는 게 목적이 아니라
**모르고 지나가는 것을 막는 게** 목적이다.

승인 표시
---------
PR 제목이나 본문, 또는 커밋 메시지에 아래 문구를 넣으면 통과한다.

    노출-승인

(예: "노출-승인: 사장님과 강연 페이지 공개 합의함 2026-08-30")

이 표시는 "사장님이 승인했다"는 선언이다. 세션이 임의로 붙이면 안 되고,
CLAUDE.md의 노출 범위 규칙대로 먼저 확인을 받아야 한다.
"""
import os
import re
import subprocess
import sys

APPROVAL = re.compile(r"노출[-\s]?승인")

# 노출을 넓히는 신호. (설명, 대상 파일 판정, 추가/삭제 중 어느 쪽을 보는가)
NOINDEX = re.compile(r"noindex", re.I)
PREVIEW_FLAG = re.compile(r"^preview:\s*true\s*$")
SITEMAP_LOC = re.compile(r"<loc>\s*(\S+?)\s*</loc>")

# 블로그 글 발행은 이 사이트의 평상 업무다. 글을 쓸 때마다 사이트맵에 URL이
# 하나 늘어나는데, 그걸 "노출 범위 변경"으로 잡으면 매번 헛경보가 뜬다.
# 헛경보가 잦은 검사는 사람이 무시하게 되고, 무시되는 검사는 없는 것보다
# 나쁘다 -- 있다고 믿게 만들기 때문이다. 그래서 글 경로는 제외한다.
# 여기서 잡아야 하는 건 "새 글"이 아니라 "숨겨뒀던 페이지를 여는 것"이다.
ROUTINE_PUBLISH = re.compile(r"/log_assets/markdown/")
NAV_LINK = re.compile(r"<a\b[^>]*href=", re.I)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def changed_files(base, head="HEAD"):
    out = git("diff", "--name-only", f"{base}...{head}")
    return [f for f in out.splitlines() if f.strip()]


def diff_lines(base, path, head="HEAD"):
    """(추가된 줄, 삭제된 줄)을 돌려준다. 파일 헤더(+++/---)는 뺀다."""
    out = git("diff", "--unified=0", f"{base}...{head}", "--", path)
    added, removed = [], []
    for line in out.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def find_exposure(base, head="HEAD"):
    findings = []
    for path in changed_files(base, head):
        added, removed = diff_lines(base, path, head)

        if path == "sitemap.xml":
            new_urls = set(SITEMAP_LOC.findall("\n".join(added))) - set(
                SITEMAP_LOC.findall("\n".join(removed))
            )
            for url in sorted(new_urls):
                if ROUTINE_PUBLISH.search(url):
                    continue   # 블로그 글 발행 -- 평상 업무
                findings.append(("검색 노출", f"사이트맵에 추가: {url}"))

        elif path == "llms.txt":
            for line in added:
                if "http" in line and line.strip():
                    findings.append(("AI 노출", f"llms.txt에 추가: {line.strip()[:90]}"))

        elif path.endswith(("header.html", "header-preview.html")):
            new_links = [l for l in added if NAV_LINK.search(l)]
            for line in new_links:
                findings.append(("메뉴 노출", f"{path}에 링크 추가: {line.strip()[:90]}"))

        if path.endswith((".html", ".md")) and path != "sitemap.xml":
            # noindex를 뗐다 = 검색에 열었다
            if any(NOINDEX.search(l) for l in removed) and not any(
                NOINDEX.search(l) for l in added
            ):
                findings.append(("검색 노출", f"{path}: noindex 제거"))
            # preview 플래그를 뗐다 = 정식 페이지로 승격했다
            if any(PREVIEW_FLAG.match(l.strip()) for l in removed) and not any(
                PREVIEW_FLAG.match(l.strip()) for l in added
            ):
                findings.append(("정식 승격", f"{path}: preview 플래그 해제"))

    return findings


def approval_text(base, head="HEAD"):
    """PR 제목·본문과 이 브랜치의 커밋 메시지를 한 덩어리로 모은다."""
    parts = [os.environ.get("PR_TITLE", ""), os.environ.get("PR_BODY", "")]
    parts.append(git("log", "--format=%B", f"{base}..{head}"))
    return "\n".join(parts)


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"   # 과거 커밋 검증용
    findings = find_exposure(base, head)

    if not findings:
        print("노출 범위 변경 없음.")
        return 0

    print(f"\n이 변경은 아래를 새로 공개합니다 ({len(findings)}건):\n")
    for kind, detail in findings:
        print(f"  [{kind}] {detail}")

    if APPROVAL.search(approval_text(base, head)):
        print("\n'노출-승인' 표시를 확인했습니다. 통과합니다.")
        return 0

    print(
        "\n"
        "❌ 노출 범위가 바뀌는데 승인 표시가 없습니다.\n"
        "\n"
        "이 저장소는 main에 병합되면 곧바로 라이브입니다. 위 항목은 병합 즉시\n"
        "실사용자와 검색엔진에 보이게 됩니다.\n"
        "\n"
        "다음 중 하나를 하세요:\n"
        "  1) 의도한 변경이 아니면 -- 위 항목을 되돌리세요. 다른 작업에 묻어\n"
        "     들어간 경우가 대부분입니다.\n"
        "  2) 의도한 변경이면 -- 사장님께 먼저 확인을 받고, PR 본문이나 커밋\n"
        "     메시지에 이유와 함께 '노출-승인'을 적으세요.\n"
        "     예: 노출-승인: 강연 페이지 공개 합의 (2026-08-30)\n"
        "\n"
        "  ⚠️ 확인 없이 표시만 붙이지 마세요. 그러면 이 검사가 무의미해집니다."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
