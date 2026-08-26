#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sitemap.xml과 log.html을 실제 발행 상태에 맞춰 정리합니다.

왜 필요한가
-----------
1) 발행 -> 초안 되돌림
   CMS에서 이미 발행된 글을 "공개 여부: 끔"으로 바꾸면 Jekyll은 그 글을
   빌드하지 않아 URL이 404가 됩니다. 그런데 log.html 카드와 sitemap.xml
   항목은 그대로 남습니다. 결과적으로 없는 페이지를 검색엔진에 제출하고,
   로그 목록에는 눌러도 404가 뜨는 카드가 남습니다.
   (기존 스크립트들은 "새 글 추가" 시점에만 초안을 걸러서 이 경우를 못 잡습니다.)

2) 새 글이 sitemap.xml에 안 들어감
   발행 파이프라인이 log.html과 posts.json은 갱신하지만 sitemap.xml은
   건드리지 않아, 새 글이 계속 사이트맵에서 빠집니다.

이 스크립트는 두 방향을 모두 맞춥니다.

기준 데이터
-----------
- 발행된 글 = assets/data/posts.json
  (파이프라인에서 fix_thumb_mapping.py가 먼저 갱신하며, 초안은 이미 빠져 있습니다)
- 초안 = log_assets/markdown/*.md 중 front matter가 published: false 인 것

안전장치
--------
- 손대는 sitemap 항목은 /log_assets/markdown/ 아래 글뿐입니다.
  홈, /log.html 같은 항목은 절대 건드리지 않습니다.
- 바뀔 게 없으면 파일을 쓰지 않습니다(불필요한 커밋 방지).
- 발행된 글을 지우는 경로는 없습니다. 지우는 대상은 초안뿐입니다.
"""

import json
import os
import re
import sys
import urllib.parse

BASE = "https://simplifier.co.kr"
MARKDOWN_DIR = "log_assets/markdown"
POSTS_JSON = "assets/data/posts.json"
SITEMAP = "sitemap.xml"
LOG_HTML = "log.html"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def to_iso(date_text):
    """'Aug 19. 2026' -> '2026-08-19'. 형식이 다르면 None."""
    m = re.match(r"([A-Za-z]{3})\s+(\d{1,2})\.\s*(\d{4})", (date_text or "").strip())
    if not m or m.group(1) not in MONTHS:
        return None
    return "{}-{:02d}-{:02d}".format(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))


def find_drafts():
    """published: false 인 글의 슬러그(확장자 뺀 파일명) 목록."""
    drafts = []
    if not os.path.isdir(MARKDOWN_DIR):
        return drafts
    for name in sorted(os.listdir(MARKDOWN_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(MARKDOWN_DIR, name)
        with open(path, encoding="utf-8", errors="replace") as f:
            head = f.read(2000)
        if re.search(r"^published:\s*false\s*$", head, re.M | re.I):
            drafts.append(name[:-3])
    return drafts


def load_published():
    """posts.json 기준 발행 글: [(디코딩된 url, iso날짜, 원본 url)]"""
    with open(POSTS_JSON, encoding="utf-8") as f:
        posts = json.load(f)
    if isinstance(posts, dict):
        posts = posts.get("posts", [])
    out = []
    for p in posts:
        url = p.get("url")
        if not url:
            continue
        out.append((urllib.parse.unquote(url), to_iso(p.get("date")), url))
    return out


def sitemap_entry(url, iso_date):
    return (
        "  <url>\n"
        "    <loc>{}{}</loc>\n"
        "    <lastmod>{}</lastmod>\n"
        "    <changefreq>weekly</changefreq>\n"
        "    <priority>0.8</priority>\n"
        "  </url>\n"
    ).format(BASE, url, iso_date)


def drop_sitemap_block(xml, needle):
    """needle을 담은 <url>...</url> 블록을 통째로 제거. 제거했으면 (xml, True)."""
    i = xml.find(needle)
    if i < 0:
        return xml, False
    start = xml.rfind("<url>", 0, i)
    end = xml.find("</url>", i)
    if start < 0 or end < 0:
        return xml, False
    end += len("</url>")
    while end < len(xml) and xml[end] in "\r\n":
        end += 1
    while start > 0 and xml[start - 1] in " \t":
        start -= 1
    return xml[:start] + xml[end:], True


def drop_log_card(html, needle):
    """needle을 담은 카드 <a ...>...</a>를 제거. 제거했으면 (html, True)."""
    i = html.find(needle)
    if i < 0:
        return html, False
    start = html.rfind('<a href="/log_assets/markdown/', 0, i)
    end = html.find("</a>", i)
    if start < 0 or end < 0:
        return html, False
    return html[:start] + html[end + 4:], True


def main():
    for required in (POSTS_JSON, SITEMAP, LOG_HTML):
        if not os.path.exists(required):
            print("SKIP: {} 이 없어 아무것도 하지 않습니다.".format(required))
            return 0

    drafts = find_drafts()
    published = load_published()

    xml = open(SITEMAP, encoding="utf-8").read()
    html = open(LOG_HTML, encoding="utf-8", errors="replace").read()
    xml_before, html_before = xml, html

    removed_sitemap, removed_cards = [], []

    # 1) 초안이 sitemap / log.html에 남아 있으면 제거
    for slug in drafts:
        for needle in (urllib.parse.quote(slug), slug):
            while True:
                xml, hit = drop_sitemap_block(xml, needle)
                if not hit:
                    break
                removed_sitemap.append(slug)
            while True:
                html, hit = drop_log_card(html, needle)
                if not hit:
                    break
                removed_cards.append(slug)

    # 2) 발행됐는데 sitemap에 없는 글 추가
    have = set()
    for loc in re.findall(r"<loc>(.*?)</loc>", xml, re.S):
        have.add(urllib.parse.unquote(loc.strip()).replace(BASE, ""))

    added, undated = [], []
    blocks = []
    for decoded_url, iso, raw_url in published:
        if decoded_url in have:
            continue
        if not iso:
            undated.append(decoded_url)
            continue
        blocks.append(sitemap_entry(raw_url, iso))
        added.append(decoded_url)

    if blocks:
        idx = xml.rindex("</urlset>")
        xml = xml[:idx] + "".join(blocks) + xml[idx:]

    # 3) 바뀐 게 있을 때만 쓰기
    changed = False
    if xml != xml_before:
        open(SITEMAP, "w", encoding="utf-8", newline="").write(xml)
        changed = True
    if html != html_before:
        open(LOG_HTML, "w", encoding="utf-8", newline="").write(html)
        changed = True

    print("초안 {}건 / 발행 {}건".format(len(drafts), len(published)))
    if removed_sitemap:
        print("sitemap에서 초안 제거: {}".format(sorted(set(removed_sitemap))))
    if removed_cards:
        print("log.html에서 초안 카드 제거: {}".format(sorted(set(removed_cards))))
    if added:
        print("sitemap에 새 글 추가: {}건".format(len(added)))
        for u in added[:20]:
            print("   + {}".format(u))
    if undated:
        print("WARNING: 날짜를 못 읽어 sitemap에 못 넣은 글 {}건".format(len(undated)))
        for u in undated[:10]:
            print("   ! {}".format(u))
    if not changed:
        print("변경 없음 - 이미 정합합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
