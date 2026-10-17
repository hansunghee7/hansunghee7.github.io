r"""
카테고리 허브 카드용 표지 썸네일(webp, 가로 640px)을 만든다.

왜 필요한가
-----------
허브 페이지(_layouts/pillar.html)는 글 표지를 카드마다 보여준다. 원본 표지는
500~700KB짜리가 많아서 허브 한 장이 18MB까지 나갔다(2026-10-17 북 QA).
카드 폭은 모바일에서도 최대 ~340px(2배 해상도 680px)이라 640px webp면
화질 차이 없이 20~60KB로 줄어든다.

규칙: _data/posts.json의 image(/log_assets/images/X.jpg)마다
      log_assets/thumbs/X.webp 를 만든다(레이아웃의 Liquid 치환과 같은 규칙).
원본은 건드리지 않는다(원본은 글 상세 커버·OG 이미지가 계속 쓴다).
이미 있으면 건너뛰므로 새 글이 생긴 뒤 다시 돌려도 된다.
썸네일이 없는 새 글은 레이아웃의 onerror가 원본으로 대신 보여준다.

자동 실행: .github/workflows/publish-pipeline.yml이 새 글이 main에 들어올 때마다
이 스크립트를 돌리고 log_assets/thumbs/를 같은 커밋에 넣는다(사람 손 없음).
그 파이프라인이 글 하나 때문에 멈추면 안 되므로, 이미지 하나가 깨져 있어도
경고만 남기고 나머지를 계속 만든다(종료 코드는 0).

사용법: python scripts/make_cover_thumbs.py
"""
import json
import os
import sys
import urllib.parse

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTH = 640
QUALITY = 72


def main():
    posts = json.load(open(os.path.join(ROOT, "_data", "posts.json"), encoding="utf8"))
    out_dir = os.path.join(ROOT, "log_assets", "thumbs")
    os.makedirs(out_dir, exist_ok=True)
    made = skipped = missing = failed = 0
    for p in posts:
        img = p.get("image") or ""
        if not img.startswith("/log_assets/images/"):
            continue
        # 레이아웃(Liquid)과 같은 치환: 폴더 교체 + 확장자를 .webp로
        thumb_url = img.replace("/log_assets/images/", "/log_assets/thumbs/")
        if thumb_url.lower().endswith(".jpg"):
            thumb_url = thumb_url[:-4] + ".webp"
        else:
            continue
        src = os.path.join(ROOT, urllib.parse.unquote(img.lstrip("/")))
        dst = os.path.join(ROOT, urllib.parse.unquote(thumb_url.lstrip("/")))
        if os.path.exists(dst):
            skipped += 1
            continue
        if not os.path.exists(src):
            missing += 1
            continue
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                if im.width > WIDTH:
                    im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
                im.save(dst, "WEBP", quality=QUALITY, method=6)
            made += 1
        except Exception as e:  # 깨진 이미지 하나가 발행 파이프라인 전체를 막지 않게
            print(f"경고: 썸네일 실패 {src}: {e}", file=sys.stderr)
            if os.path.exists(dst):
                os.remove(dst)
            failed += 1
    print(f"만듦 {made}, 이미 있음 {skipped}, 원본 없음 {missing}, 실패 {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
