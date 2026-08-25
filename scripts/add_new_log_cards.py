"""
log_assets/markdown/*.md 에는 있지만 log.html의 카드 그리드에는 아직 없는
글에 대해 카드 <a> 블록을 추가해준다.

기존 fix_thumb_mapping.py는 "이미 log.html에 있는 카드"의 썸네일만 정규식으로
패치할 뿐, 카드 자체가 없으면 아무 것도 하지 않는다 -- 그래서 새 글이
log.html에 자동으로 나타나게 하려면 이 스크립트가 필요하다.

안전장치: 이미 카드가 있는 글은 절대 건드리지 않는다(기존 585개+ 카드는
1바이트도 안 바뀜). 새 카드는 항상 <div class="card-grid" id="cardGrid">
바로 뒤에 추가한다 -- log.html의 JS가 어차피 매 로드마다 날짜/ID 기준으로
전부 다시 정렬해서 배치하므로 DOM 삽입 위치는 무관하다.
"""
import glob
import html
import os
import re
import sys
import urllib.parse

import yaml

MD_DIR = "log_assets/markdown"
LOG_HTML = "log.html"

EXISTING_HREF_RE = re.compile(r'<a href="/log_assets/markdown/([^"]+)\.html" class="card-item"')
GRID_OPEN_RE = re.compile(r'(<div class="card-grid" id="cardGrid">)')


def quote_if_local(url):
    if not url:
        return "/log_assets/images/logo_white.png"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    # 로컬 경로(/log_assets/images/...)는 기존 카드들과 같은 방식으로 인코딩
    parts = url.split("/")
    return "/".join(urllib.parse.quote(p) if p else p for p in parts)


def build_card(base, fm):
    title = html.escape(str(fm.get("title", base)), quote=False)
    category = html.escape(str(fm.get("category", "")), quote=False)
    date_val = fm.get("date")
    date_str = ""
    if hasattr(date_val, "strftime"):
        date_str = date_val.strftime("%Y%m%d")
    elif isinstance(date_val, str) and len(date_val) >= 10:
        date_str = date_val[:10].replace("-", "")
    post_id = re.match(r"^(\d+)_", base)
    post_id = post_id.group(1) if post_id else "0"
    href = "/log_assets/markdown/" + urllib.parse.quote(base) + ".html"
    thumb = quote_if_local(fm.get("cover_image"))

    return (
        f'<a href="{href}" class="card-item" data-category="{category}" '
        f'data-date="{date_str}" data-id="{post_id}">'
        f'<div class="card-thumb-wrap"><div class="card-thumb" '
        f"style=\"background-image: url('{thumb}');\"></div></div>"
        f'<div class="card-content"><div class="card-meta">'
        f'<div class="card-category">{category}</div>'
        f'<div class="card-date">{fm.get("date_string", "")}</div></div>'
        f'<h3 class="card-title">{title}</h3></div></a>'
    )


def process():
    if not os.path.exists(LOG_HTML):
        print(f"{LOG_HTML} not found")
        return 1

    with open(LOG_HTML, "r", encoding="utf-8") as fh:
        log_content = fh.read()

    existing = {urllib.parse.unquote(h) for h in EXISTING_HREF_RE.findall(log_content)}

    new_cards = []
    md_files = sorted(glob.glob(os.path.join(MD_DIR, "*.md")))
    for path in md_files:
        base = os.path.splitext(os.path.basename(path))[0]
        if base in existing:
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
        if not raw.startswith("---"):
            continue
        parts = raw.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except Exception:
            continue
        if fm.get("published") is False:
            continue
        if not re.match(r"^\d{3}_", os.path.basename(path)):
            # normalize_new_post.py가 아직 순번을 안 붙인 파일 -- 이번엔 건너뛰고
            # 다음 파이프라인 실행(정규화 이후)에서 처리
            continue
        new_cards.append(build_card(base, fm))

    if not new_cards:
        print("no new posts to add, log.html untouched")
        return 0

    def inject(m):
        return m.group(1) + "".join(new_cards)

    new_log_content, n = GRID_OPEN_RE.subn(inject, log_content, count=1)
    if n == 0:
        print("!! could not find <div class=\"card-grid\" id=\"cardGrid\"> in log.html, aborting")
        return 1

    with open(LOG_HTML, "w", encoding="utf-8") as fh:
        fh.write(new_log_content)

    print(f"added {len(new_cards)} new card(s) to log.html")
    return 0


if __name__ == "__main__":
    sys.exit(process())
