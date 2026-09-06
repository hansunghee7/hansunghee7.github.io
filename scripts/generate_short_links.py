#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
posts.json 기준으로 공유용 짧은 URL(/logs/<id>/) 정적 리다이렉트 페이지를 만든다.

왜 필요한가
-----------
글 URL은 한글 제목이 그대로 퍼센트 인코딩되어 들어가(log_assets/markdown/
<긴 제목>.html) 카카오톡 등으로 공유하면 링크가 비정상적으로 길어진다.
/logs/<id>/ 는 그 글로 즉시 리다이렉트하는 순수 정적 페이지일 뿐, 원본 URL을
대체하지 않는다 -- canonical과 sitemap.xml은 여전히 원본 긴 URL을 가리키므로
검색엔진 색인·순위에는 영향이 없고, 공유용 링크만 짧아진다.

안전장치
--------
- sitemap.xml에는 절대 넣지 않는다. noindex + canonical(원본 긴 URL)로
  중복 콘텐츠 신호도 방지한다.
- 카카오톡·페이스북 등 링크 미리보기 봇은 자바스크립트를 안 읽으므로,
  각 페이지 자체에 원본과 동일한 og:title/og:image를 정적으로 넣어둔다
  (그래야 리다이렉트만 있고 미리보기가 깨지는 사고를 피한다).
- 내용이 같으면 파일을 다시 쓰지 않는다(불필요한 커밋 방지, 이 파이프라인의
  다른 스크립트들과 같은 관례).
- front matter가 없는 순수 정적 HTML이라 Jekyll이 템플릿 처리 없이 그대로
  복사만 한다 -- 수백 편을 한꺼번에 만들어도 빌드 시간에 거의 영향이 없다.
"""

import html
import json
import os

BASE = "https://simplifier.co.kr"
POSTS_JSON = "assets/data/posts.json"
OUT_DIR = "logs"

PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - Simplifier</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{long_url}">
<meta http-equiv="refresh" content="0; url={long_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:image" content="{image}">
<meta property="og:url" content="{long_url}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:image" content="{image}">
</head>
<body>
<p>이동 중입니다 — 자동으로 안 넘어가면 <a href="{long_url}">여기를 눌러주세요</a>.</p>
</body>
</html>
"""


def absolute(path_or_url):
    if "://" in path_or_url:
        return path_or_url
    return BASE + path_or_url


def render(post):
    title = html.escape(post["title"], quote=True)
    long_url = html.escape(absolute(post["url"]), quote=True)
    image = html.escape(absolute(post.get("image") or "/assets/og-image.png"), quote=True)
    return PAGE_TEMPLATE.format(title=title, long_url=long_url, image=image)


def main():
    with open(POSTS_JSON, encoding="utf-8") as f:
        posts = json.load(f)

    written = 0
    for post in posts:
        pid = str(post["id"])
        out_path = os.path.join(OUT_DIR, pid, "index.html")
        content = render(post)

        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                if f.read() == content:
                    continue

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1

    print("생성/갱신: {}개".format(written))


if __name__ == "__main__":
    main()
