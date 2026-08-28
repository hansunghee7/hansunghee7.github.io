import os
import re
import json
import yaml
import urllib.parse

LOG_ASSETS_DIR = "log_assets"
MARKDOWN_DIR = os.path.join(LOG_ASSETS_DIR, "markdown")

# 🎯 예고편 -> 1화 -> 2화 순서로 회차 라벨("이전 화"/"다음 화")을 붙이고
# CTA도 생략하는 연재 웹툰 카테고리.
# (_includes/post_nav.html, _includes/post_cta.html에도 이 목록과
# 똑같은 카테고리명이 하드코딩돼 있다 -- 여기서 바꾸면 거기도 같이 바꿀 것.)
EPISODIC_CATS = ["코치S", "잉크드인대 기획학과"]

# 카테고리별 기본 정렬 방향(asc=날짜순/오래된 글부터, desc=최신순).
# log.html / index.html / concept2.html의 categoryDefaults(JS)와 반드시 동일하게
# 유지할 것 -- 여기서 어긋나면 카드 목록에 보이는 순서와 글 하단 이전글/다음글이
# 서로 다른 방향을 가리키게 된다.
CATEGORY_SORT_MODE = {
    "AI의 언어들": "asc", "Be the PO": "desc", "PO의 프레임웍": "asc", "UX의 언어들": "desc",
    "기획일상": "desc", "기획자의 프레임웍": "asc", "대한민국 스타트업 미국진출을 묻다": "asc",
    "스타트업 인사이트": "desc", "심플리파이어 라이프": "desc",
    "이력서에 쓰지 않는 첫직장 이야기": "asc",
    "잉크드인대 기획학과": "asc", "코치S": "asc", "토크세션": "desc",
}


def is_ascending_cat(cat):
    return CATEGORY_SORT_MODE.get(cat, "desc") == "asc"


# 💬 포스트 하단 문의 CTA(코칭문의/강연문의)는 더 이상 여기서 만들지 않는다.
# 예전엔 이 카테고리 목록 기준으로 <div class="post-cta">를 본문에 직접
# 찍어 넣었는데, 그러면 카테고리명만 다르고 내용은 100% 같은 HTML이
# 마크다운 594개 파일에 그대로 중복된다. 지금은 _includes/post_cta.html이
# page.category 하나만 보고 같은 분기를 Liquid로 그려서, 본문엔 아무것도
# 안 남긴다.


def date_sort_key(frontmatter, fname):
    # front matter의 date는 YAML이 상황에 따라 datetime.date / datetime.datetime
    # (타임존 포함, 예: 615번처럼 'date: 2026-08-26T16:27:00Z') / 문자열로 각각
    # 다르게 파싱해준다. 이 타입들은 서로 직접 비교하면 TypeError가 나므로,
    # 전부 'YYYY-MM-DD' 문자열로 정규화해 비교한다(ISO 형식이라 문자열
    # 정렬이 곧 날짜 정렬과 같다). date가 없거나 못 읽으면 그 글은 정렬
    # 맨 끝(desc 기준 가장 과거)으로 보내고, 같은 날짜끼리는 파일명으로
    # 안정적인 순서를 보장한다.
    raw = frontmatter.get("date")
    date_str = ""
    if hasattr(raw, "isoformat"):
        date_str = raw.isoformat()[:10]
    elif isinstance(raw, str) and len(raw) >= 10:
        date_str = raw[:10]
    return (date_str or "0000-00-00", fname)


def extract_ep_num(filename, title):
    # '예고편'은 가장 첫 번째(0화)로 간주
    if '예고편' in filename or '예고편' in title:
        return 0
    match = re.search(r'(\d+)화', title) or re.search(r'(\d+)화', filename)
    if match:
        return int(match.group(1))
    # 파일명 맨 앞의 숫자 ID 추출 (예: 475_ -> 475)
    num_prefix = re.match(r'(\d+)_', filename)
    if num_prefix:
        return int(num_prefix.group(1))
    return 9999


# front matter를 통째로 yaml.safe_dump로 재작성하면 따옴표 스타일이 달라져
# 필요 없는 전체 재작성이 일어난다(normalize_new_post.py와 같은 이유).
# 그래서 필드 하나만 정규식으로 추가/치환/제거한다. 값은 json.dumps로
# 감싸는데, YAML의 큰따옴표 문자열은 JSON 문자열과 이스케이프 규칙이
# 같아서 그대로 유효한 YAML이 되고, 따옴표/특수문자가 섞인 제목도 안전하다.
def set_front_matter_field(fm_text, key, value):
    line = f"{key}: {json.dumps(value, ensure_ascii=False)}"
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    if pattern.search(fm_text):
        return pattern.sub(line.replace("\\", "\\\\"), fm_text, count=1)
    return fm_text.rstrip("\n") + "\n" + line + "\n"


def remove_front_matter_field(fm_text, key):
    return re.sub(rf"^{re.escape(key)}:.*\n?", "", fm_text, flags=re.M)


# 예전엔 build_cta_html()이 만든 CTA와 이 nav를 합쳐서 CATEGORY_NAV_START/END
# 사이 본문에 직접 HTML로 찍어 넣었다. 지금은 prev/next의 url·title만
# front matter에 써 두고, 실제 렌더링(라벨 분기 포함)은
# _includes/post_nav.html이 page.category를 보고 Liquid로 그린다.
# 그래서 이 마커도, 본문에 남아있던 옛 HTML도 더 이상 필요 없어 제거한다.
CATEGORY_NAV_BLOCK_RE = re.compile(
    r'<!-- CATEGORY_NAV_START -->.*?<!-- CATEGORY_NAV_END -->\n*', re.DOTALL
)

print("🔄 심플리파이어 동기화 스크립트 실행 중...")

posts_by_cat = {}

if os.path.exists(MARKDOWN_DIR):
    for fname in os.listdir(MARKDOWN_DIR):
        if fname.endswith(".md"):
            filepath = os.path.join(MARKDOWN_DIR, fname)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # YAML Frontmatter 분석
            frontmatter = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                    except Exception:
                        pass

            # 비공개(published: false) 글은 실제로 빌드되지 않아 링크가 깨지므로
            # 이전글/다음글 순서에서 완전히 제외
            if frontmatter.get("published") is False:
                continue

            cat = frontmatter.get("category", "기타")
            title = frontmatter.get("title", fname.replace(".md", ""))

            # HTML 파일명 매핑
            html_name = fname.replace(".md", ".html")
            ep_num = extract_ep_num(fname, title)

            post_data = {
                'fname': fname,
                'html_name': html_name,
                'title': title,
                'category': cat,
                'ep_num': ep_num,
                'date_key': date_sort_key(frontmatter, fname),
                'filepath': filepath
            }

            if cat not in posts_by_cat:
                posts_by_cat[cat] = []
            posts_by_cat[cat].append(post_data)

    # 카테고리별 정렬 및 이전글/다음글 링크 주입
    for cat, posts in posts_by_cat.items():
        is_episodic = (cat in EPISODIC_CATS)
        ascending = is_ascending_cat(cat)

        if is_episodic:
            # 웹툰형: 예고편(0) -> 1화 -> 2화 순 오름차순 정렬 (회차 역전은 없음)
            posts.sort(key=lambda x: (x['ep_num'], x['fname']))
        else:
            # 일반 블로그형: CATEGORY_SORT_MODE를 따라 실제 date 필드 기준으로
            # 오래된 글부터(asc) 또는 최신글부터(desc) 정렬한다.
            #
            # 파일명 ID로 정렬하던 예전 방식은 틀렸다 -- 브런치에서 한 번에
            # 이관된 레거시 글들은 ID가 낮을수록 오히려 실제 날짜가 최신인
            # 경우가 카테고리마다 일관되게 나타난다(이관 스크립트가 최신순으로
            # 읽어들이며 번호를 매긴 것으로 보임). 반면 이관 이후 새로 추가된
            # 글은 ID가 클수록 최신이라, ID는 카테고리 안에서조차 방향이
            # 뒤집힐 수 있는 신호였다. log.html 카드 목록도 이미 date_key
            # 기준으로 정렬하므로, 여기서도 같은 기준을 써야 목록 순서와
            # 이전글/다음글이 같은 방향을 가리킨다.
            posts.sort(key=lambda x: x['date_key'], reverse=not ascending)

        for i, p in enumerate(posts):
            # posts는 이미 이 카테고리가 실제로 보여지는 순서(asc=오래된 글부터,
            # desc=최신글부터)로 정렬돼 있다. '이전글' = 그 목록에서 바로 앞
            # (index-1), '다음글' = 바로 뒤(index+1) -- 정렬 방향과 무관하게
            # 항상 이 식 하나로 충분하다. 목록 맨 앞 글은 '이전글'이 없고,
            # 맨 끝 글은 '다음글'이 없다.
            # (예전엔 desc 카테고리 쪽 이 두 줄이 뒤바뀌어 있어서 최신글에
            # '다음글' 대신 '이전글'만 뜨는 버그가 있었다.)
            prev_post = posts[i-1] if i > 0 else None
            next_post = posts[i+1] if i < len(posts)-1 else None

            with open(p['filepath'], 'r', encoding='utf-8', errors='ignore') as f:
                file_text = f.read()

            if not file_text.startswith('---'):
                continue
            parts = file_text.split('---', 2)
            if len(parts) < 3:
                continue
            fm_text, body = parts[1], parts[2]
            orig_fm_text, orig_body = fm_text, body

            if prev_post:
                prev_href = urllib.parse.quote(prev_post["html_name"])
                fm_text = set_front_matter_field(fm_text, 'prev_url', f'/log_assets/markdown/{prev_href}')
                fm_text = set_front_matter_field(fm_text, 'prev_title', prev_post["title"])
            else:
                fm_text = remove_front_matter_field(fm_text, 'prev_url')
                fm_text = remove_front_matter_field(fm_text, 'prev_title')

            if next_post:
                next_href = urllib.parse.quote(next_post["html_name"])
                fm_text = set_front_matter_field(fm_text, 'next_url', f'/log_assets/markdown/{next_href}')
                fm_text = set_front_matter_field(fm_text, 'next_title', next_post["title"])
            else:
                fm_text = remove_front_matter_field(fm_text, 'next_url')
                fm_text = remove_front_matter_field(fm_text, 'next_title')

            body = CATEGORY_NAV_BLOCK_RE.sub('', body)

            if fm_text != orig_fm_text or body != orig_body:
                new_text = '---' + fm_text + '---' + body
                with open(p['filepath'], 'w', encoding='utf-8') as f:
                    f.write(new_text)

print("✅ 카테고리별 정렬 및 이전글/다음글 매핑 완벽 재구성 완료!")
