import os
import re
import yaml
import html

LOG_ASSETS_DIR = "log_assets"
MARKDOWN_DIR = os.path.join(LOG_ASSETS_DIR, "markdown")

# 🎯 오름차순(연재형: 예고편 -> 1화 -> 2화)으로 순서를 엮어야 하는 카테고리 지정
ASCENDING_CATS = ["코치S", "잉크드인대 기획학과", "잉크드인대"]

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
                'filepath': filepath
            }

            if cat not in posts_by_cat:
                posts_by_cat[cat] = []
            posts_by_cat[cat].append(post_data)

    # 카테고리별 정렬 및 이전글/다음글 링크 주입
    for cat, posts in posts_by_cat.items():
        is_ascending = (cat in ASCENDING_CATS)
        
        if is_ascending:
            # 웹툰형: 예고편(0) -> 1화 -> 2화 순 오름차순 정렬
            posts.sort(key=lambda x: (x['ep_num'], x['fname']))
        else:
            # 일반 블로그형: 최신글 우선 내림차순 정렬
            posts.sort(key=lambda x: x['fname'], reverse=True)

        for i, p in enumerate(posts):
            # '이전글/다음글'은 절대적인 신구(新舊) 순서가 아니라, 이 카테고리를
            # 훑어보는 자연스러운 방향을 따른다.
            # - 연재형(오름차순: 예고편→1화→2화...): 다음 화 = posts[i+1] (더 최신 화)
            # - 일반 블로그형(내림차순: 최신글이 목록 맨 앞): 다음글 = posts[i-1]
            #   (목록을 계속 훑어볼 때 다음으로 만나는, 더 과거의 글).
            #   그래야 목록 맨 앞의 최신글을 열었을 때 '다음글'이 뜨고,
            #   가장 오래된 글에 도달하면 '다음글'이 사라진다.
            if is_ascending:
                prev_post = posts[i-1] if i > 0 else None
                next_post = posts[i+1] if i < len(posts)-1 else None
            else:
                prev_post = posts[i+1] if i < len(posts)-1 else None
                next_post = posts[i-1] if i > 0 else None

            nav_html = '<div class="category-nav-wrap">\n'

            # 왼쪽 영역 (이전글 / 이전 화)
            if prev_post:
                label = "이전 화" if is_ascending else "이전글"
                nav_html += f'  <a href="/log_assets/markdown/{prev_post["html_name"]}" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">❮ {label}</span><span class="nav-title">{html.escape(prev_post["title"], quote=False)}</span></a>\n'
            else:
                nav_html += '  <div></div>\n'

            # 오른쪽 영역 (다음글 / 다음 화)
            if next_post:
                label = "다음 화" if is_ascending else "다음글"
                nav_html += f'  <a href="/log_assets/markdown/{next_post["html_name"]}" class="cat-nav-item cat-nav-right"><span class="nav-title">{html.escape(next_post["title"], quote=False)}</span><span class="cat-nav-label">{label} ❯</span></a>\n'
            else:
                nav_html += '  <div></div>\n'

            nav_html += '</div>'

            # 마크다운 파일 업데이트
            with open(p['filepath'], 'r', encoding='utf-8', errors='ignore') as f:
                file_text = f.read()

            if "<!-- CATEGORY_NAV_START -->" in file_text:
                file_text = re.sub(
                    r'<!-- CATEGORY_NAV_START -->.*?<!-- CATEGORY_NAV_END -->',
                    f'<!-- CATEGORY_NAV_START -->\n{nav_html}\n<!-- CATEGORY_NAV_END -->',
                    file_text,
                    flags=re.DOTALL
                )
                with open(p['filepath'], 'w', encoding='utf-8') as f:
                    f.write(file_text)

print("✅ 카테고리별 정렬 및 이전글/다음글 매핑 완벽 재구성 완료!")