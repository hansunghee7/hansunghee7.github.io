# -*- coding: utf-8 -*-
"""심플리파이어 스튜디오 페이지가 insight-7b3e9f2c/STYLE_GUIDE.md를 지키는지 훑는다.

새 스튜디오 페이지를 추가하거나 기존 페이지를 고친 뒤, 커밋 전에 실행한다.
빌드/CI 없이 정적 HTML을 문자열로 직접 검사하는 가벼운 스크립트라 놓치는 것도
있다 -- 특히 여백/시각적 오류(STYLE_GUIDE.md의 "자동으로 못 잡는 것" 참고)는
브라우저로 직접 확인해야 하며, title= 관련은 항상 판단이 필요해 WARN으로만 낸다.
이 스크립트는 사람 눈으로 STYLE_GUIDE.md와 대조하는 걸 대체하지 않는다.

사용법: python scripts/check_studio_style.py
"""
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).parent.parent
STUDIO_DIR = ROOT / "insight-7b3e9f2c"

REQUIRED_LINK = '<link rel="stylesheet" href="/insight-7b3e9f2c/studio.css">'
REQUIRED_SCRIPT = '<script src="/insight-7b3e9f2c/studio.js"></script>'


def check_file(path):
    errors = []
    warns = []
    text = path.read_text(encoding="utf-8")

    if REQUIRED_LINK not in text:
        errors.append("studio.css <link>이 없습니다.")
    if REQUIRED_SCRIPT not in text:
        errors.append("studio.js <script>이 없습니다.")

    nav_match = re.search(r'<nav id="adminShellNav">(.*?)</nav>', text, re.S)
    if nav_match is None:
        errors.append('<nav id="adminShellNav">...</nav>가 없습니다.')
    elif nav_match.group(1).strip() != "":
        errors.append("adminShellNav 안에 내용이 있습니다 -- 메뉴는 studio.js가 채워야 하는데 직접 나열된 것으로 보입니다.")

    if "noindex" not in text:
        errors.append('<meta name="robots" content="noindex...">가 없습니다.')
    if 'name="referrer"' not in text:
        errors.append('<meta name="referrer" content="no-referrer">가 없습니다.')
    if "/favicon-32x32.png" not in text:
        errors.append("favicon 링크가 없습니다.")

    if re.search(r'^\s*:root\s*\{', text, re.M):
        errors.append(":root{...} 디자인 토큰을 이 파일 안에서 다시 선언하고 있습니다 -- studio.css와 중복입니다.")

    if re.search(r'function\s+setRefreshState\s*\(', text):
        errors.append("setRefreshState()를 이 파일 안에서 직접 정의하고 있습니다 -- studio.js의 Studio.setRefreshState를 써야 합니다.")

    titles = re.findall(r'\btitle="([^"]{0,80})', text)
    if titles:
        warns.append(
            'title="..." 속성 {}개 발견 -- 클릭/탭에 반응 안 하는 네이티브 툴팁입니다. '
            "이미 화면에 보이는 정보의 보조용(말줄임 등)인지, 유일한 설명 통로인지 확인하세요. "
            "후자면 STYLE_GUIDE.md의 ⓘ 버튼(.info-dot/.info-text) 패턴으로 바꿔야 합니다.".format(len(titles))
        )

    if 'class="info-dot"' in text and 'aria-label="설명 보기"' not in text:
        warns.append('info-dot 버튼이 있는데 통일된 aria-label="설명 보기"가 안 보입니다.')

    return errors, warns


def main():
    files = sorted(STUDIO_DIR.glob("*.html"))
    total_errors = 0
    total_warns = 0
    for f in files:
        errors, warns = check_file(f)
        if errors or warns:
            print("\n" + f.name)
            for e in errors:
                print("  [FAIL] " + e)
            for w in warns:
                print("  [확인필요] " + w)
        total_errors += len(errors)
        total_warns += len(warns)

    print("\n{}개 파일 점검 완료 -- FAIL {}건, 확인필요 {}건.".format(len(files), total_errors, total_warns))
    print("(여백/시각 오류 등 자동으로 못 잡는 항목은 STYLE_GUIDE.md 참고해 브라우저로 직접 확인할 것)")
    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
