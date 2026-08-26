r"""
커버 이미지 파일명에서 "화면을 깨뜨리는 특수문자"를 자동으로 없애준다.

왜 필요한가
-----------
Decap CMS는 글 목록 그리드의 썸네일을 이렇게 그린다:

    "background-image:url(" + src + ");background-position:center center;..."

따옴표 없는 CSS url() 안에 값을 그대로 이어붙인다. CSS 규격상 따옴표 없는
url() 토큰에서는 ( ) ' " \ 와 공백을 반드시 이스케이프해야 하는데, Decap은
이스케이프 없이 encodeURI만 걸어서 넣는다. encodeURI는 공백(%20)과 " (%22),
\ (%5C)는 바꿔주지만  '  (  )  는 그대로 둔다. 그래서 파일명에 작은따옴표나
괄호가 하나라도 있으면 url() 토큰이 거기서 닫혀버려 선언 전체가 무시되고
썸네일이 빈칸이 된다. (한글·공백·쉼표는 멀쩡하다 -- 실제 범인은 이 세 글자뿐)

# 와 ? 도 같이 지운다. encodeURI가 그대로 두는데, URL에서는 각각 프래그먼트와
쿼리 시작으로 해석돼 경로가 잘려나가기 때문이다.

이 스크립트는 발행 파이프라인에서 매번 돌면서, 새로 올라온 커버 이미지에
이런 문자가 섞여 있으면 파일명을 고치고 글의 front matter도 같이 맞춰준다.
그래서 사장님이 CMS에서 어떤 이름의 이미지를 올리든 같은 증상이 재발하지
않는다.

범위
----
front matter의 image가 가리키는 "커버 이미지"만 건드린다. 본문 안에 들어가는
_img_N 이미지들은 <img src="..."> 로 렌더링돼서 이 버그와 무관하므로 그대로 둔다.

안전장치
--------
- 바꿀 게 없으면 아무 파일도 쓰지 않는다(불필요한 커밋 방지).
- 이름 충돌이 생기면 그 파일은 건너뛴다(덮어쓰지 않는다).
- front matter는 다시 파싱해서 값이 의도대로 들어갔는지 확인한 뒤에만 저장한다.
"""
import os
import re
import sys
import urllib.parse

import yaml

MD_DIR = "log_assets/markdown"
IMG_DIR = "log_assets/images"

# encodeURI가 그대로 통과시키면서 CSS url()/URL 경로를 깨뜨리는 문자들
HAZARD_CHARS = set("'()\"\\#?")

IMAGE_LINE_RE = re.compile(r"^image:.*$", re.M)


def sanitize(name):
    return "".join(c for c in name if c not in HAZARD_CHARS)


def load_front_matter(raw):
    if not raw.startswith("---"):
        return None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return None


def collect_refs():
    """{이미지 파일명: [그 이미지를 쓰는 글 파일명, ...]}"""
    refs = {}
    for fname in sorted(os.listdir(MD_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(MD_DIR, fname)
        with open(path, encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
        fm = load_front_matter(raw)
        if not fm:
            continue
        img = fm.get("image") or ""
        if not img or img.startswith("http://") or img.startswith("https://"):
            continue
        base = urllib.parse.unquote(img).rsplit("/", 1)[-1]
        if not any(c in base for c in HAZARD_CHARS):
            continue
        refs.setdefault(base, []).append(fname)
    return refs


def rewrite_front_matter(post_fname, new_base):
    path = os.path.join(MD_DIR, post_fname)
    with open(path, encoding="utf-8", errors="ignore") as fh:
        raw = fh.read()
    try:
        fm_end = raw.index("\n---", 3)
    except ValueError:
        return False
    fm_text, rest = raw[:fm_end], raw[fm_end:]

    new_value = "/log_assets/images/" + new_base
    # new_base에는 따옴표가 남아 있을 수 없으므로 작은따옴표로 감싸도 안전하다
    new_fm, count = IMAGE_LINE_RE.subn("image: '" + new_value + "'", fm_text, count=1)
    if count != 1:
        return False

    new_raw = new_fm + rest
    check = load_front_matter(new_raw)
    if check is None or check.get("image") != new_value:
        return False

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_raw)
    return True


def main():
    if not os.path.isdir(MD_DIR) or not os.path.isdir(IMG_DIR):
        print("markdown/images 폴더가 없어 건너뜁니다")
        return 0

    refs = collect_refs()
    if not refs:
        print("커버 이미지 파일명에 문제되는 특수문자 없음 - 변경 없음")
        return 0

    existing = set(os.listdir(IMG_DIR))
    planned = {}
    for base in refs:
        new_base = sanitize(base)
        if not new_base or new_base == base:
            continue
        if new_base in existing or new_base in planned.values():
            print("건너뜀(이름 충돌): {} -> {}".format(base, new_base))
            continue
        planned[base] = new_base

    renamed = updated = 0
    for base, new_base in planned.items():
        src = os.path.join(IMG_DIR, base)
        dst = os.path.join(IMG_DIR, new_base)
        if os.path.exists(src) and not os.path.exists(dst):
            os.rename(src, dst)
            renamed += 1
            existing.discard(base)
            existing.add(new_base)
        for post_fname in refs[base]:
            if rewrite_front_matter(post_fname, new_base):
                updated += 1
                print("  {} -> {}".format(post_fname, new_base))

    print("이미지 {}개 이름 변경, 글 {}개 경로 갱신".format(renamed, updated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
