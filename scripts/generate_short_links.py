#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기존 글의 옛 긴 주소(log_assets/markdown/<제목>.html) 자리에, 진짜 주소가 된
짧은 주소(/logs/<id>/)로 즉시 이동하는 정적 리다이렉트 페이지를 만든다.

왜 방향이 바뀌었나
------------------
2026-09-06 전에는 반대 방향이었다 -- /logs/<id>/ 가 리다이렉트 스텁, 긴
주소가 진짜 페이지. 이제는 각 글의 Jekyll permalink가 /logs/<id>/로
바뀌어(scripts/normalize_new_post.py) 그쪽이 진짜 페이지가 됐다. 옛 긴
주소 자리에는 이 스크립트가 리다이렉트 스텁을 대신 채워, 이미 외부에
뿌려진 링크·북마크·구글 캐시가 안 깨지게 한다(영구 안전망 -- 나중에
"정리한다"고 지우지 않는다).

새 글(마이그레이션 이후 처음 발행되는 글)은 옛 긴 주소 자체가 존재한 적이
없으므로 스텁을 안 만든다. MIGRATION_CUTOFF_ID로 그 경계를 구분한다.

안전장치
--------
- sitemap.xml에는 넣지 않는다(진짜 주소인 짧은 쪽만 sync_sitemap_and_drafts.py가
  sitemap에 넣는다). noindex + canonical(짧은 URL)로 중복 콘텐츠 신호도
  짧은 쪽으로 정리한다.
- 카카오톡·페이스북 등 링크 미리보기 봇은 자바스크립트를 안 읽으므로,
  정적 og:title/og:image를 그대로 유지해 미리보기가 깨지지 않게 한다.
- 내용이 같으면 파일을 다시 쓰지 않는다(불필요한 커밋 방지).
"""

import html
import json
import os
import re

BASE = "https://simplifier.co.kr"
POSTS_JSON = "assets/data/posts.json"
MD_DIR = "log_assets/markdown"

# 2026-09-06 마이그레이션 시점의 마지막 글 id. 이 이하는 옛 긴 주소가 실제로
# 존재했던 적이 있어 리다이렉트 스텁이 필요하고, 이 초과는 태어날 때부터
# 짧은 주소만 썼으므로 스텁이 필요 없다.
MIGRATION_CUTOFF_ID = 618

PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - Simplifier</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{short_url}">
<meta http-equiv="refresh" content="0; url={short_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:image" content="{image}">
<meta property="og:url" content="{short_url}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:image" content="{image}">
</head>
<body>
<p>이동 중입니다 — 자동으로 안 넘어가면 <a href="{short_url}">여기를 눌러주세요</a>.</p>
</body>
</html>
"""


def absolute(path_or_url):
    if "://" in path_or_url:
        return path_or_url
    return BASE + path_or_url


def render(title, short_url, image):
    return PAGE_TEMPLATE.format(
        title=html.escape(title, quote=True),
        short_url=html.escape(absolute(short_url), quote=True),
        image=html.escape(absolute(image or "/assets/og-image.png"), quote=True),
    )


def main():
    with open(POSTS_JSON, encoding="utf-8") as f:
        posts = json.load(f)
    posts_by_id = {p["id"]: p for p in posts}

    written = 0
    for fname in sorted(os.listdir(MD_DIR)):
        if not fname.endswith(".md"):
            continue
        m = re.match(r"^(\d+)_", fname)
        if not m:
            continue
        pid = int(m.group(1))
        if pid > MIGRATION_CUTOFF_ID:
            continue  # 새 글 -- 옛 긴 주소가 존재한 적이 없음
        post = posts_by_id.get(pid)
        if not post:
            continue  # 초안 등 발행되지 않은 글

        base = fname[:-3]
        # 파일시스템 경로는 원래 Jekyll이 이 글을 빌드하던 그 자리 그대로다
        # (유니코드 파일명 그대로 -- URL의 퍼센트 인코딩은 브라우저/서버가
        # 전송할 때 하는 것이지 실제 파일명이 아니다).
        out_path = os.path.join(MD_DIR, base + ".html")
        content = render(post["title"], post["url"], post.get("image"))

        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                if f.read() == content:
                    continue

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1

    print("생성/갱신: {}개".format(written))


if __name__ == "__main__":
    main()
