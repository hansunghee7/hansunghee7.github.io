import os
import re
import urllib.parse
import csv

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

def clean_for_match(text):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

# 1. 날짜 데이터 추출
dates_map = {}
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) > 2:
                dates_map[clean_for_match(row[1])] = row[2].strip()
except:
    pass

# 2. 마크다운 파일 목록 수집
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()
post_count = len(md_files)

cards_html = ""
unique_categories = set()

print("🔍 파일 내부 오류 교정 및 인덱스 생성 시작...")

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # ★ 핵심 1: 카드 제목과 글 내용을 100% 일치시키기 위해 '파일명'을 절대 기준으로 삼음
    base_name = filename[:-3]
    true_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    
    # [파일 내부 오류 교정] 머리말(YAML)의 title이 실제 파일명과 다르게 꼬여있다면 강제로 덮어쓰기!
    title_match = re.search(r"^title:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    if title_match and title_match.group(1).strip() != true_title:
        safe_yaml_title = true_title.replace('"', '\\"') # 따옴표 충돌 방지
        content = re.sub(r"^title:.*$", f'title: "{safe_yaml_title}"', content, flags=re.MULTILINE)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    # 카테고리 추출
    cat_match = re.search(r"^category:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    if cat_match:
        category = clean_category_name(cat_match.group(1))
    else:
        category = "기타"
    
    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    # ★ 핵심 2: 썸네일 이미지 추출기 (한글, 띄어쓰기, 복잡한 경로 완벽 대응)
    img_url = "/brunch_web_assets/images/logo_white.png"
    
    img_urls = re.findall(r'!\[.*?\]\((.*?)\)', content)
    if not img_urls:
        img_urls = re.findall(r'<img[^>]+src=["\'](.*?)["\']', content, re.IGNORECASE)
        
    if img_urls:
        for raw_url in img_urls:
            raw_url = raw_url.strip()
            # 마크다운 이미지의 부가 설명("title") 부분 제거
            if ' "' in raw_url: raw_url = raw_url.split(' "')[0]
            elif " '" in raw_url: raw_url = raw_url.split(" '")[0]
            
            if not raw_url: continue
            
            if not raw_url.startswith(('http://', 'https://', 'data:')):
                # URL에 포함된 한글과 띄어쓰기를 웹이 이해할 수 있게 변환 (예: %20)
                safe_path = urllib.parse.quote(raw_url, safe='/')
                if 'images/' in safe_path:
                    img_url = '/brunch_web_assets/images/' + safe_path.split('images/')[-1]
                else:
                    img_url = '/brunch_web_assets/markdown/' + safe_path
            else:
                img_url = raw_url
            break # 첫 번째 정상 이미지를 찾으면 종료

    # 날짜 매칭
    date_str = dates_map.get(clean_for_match(true_title), "")
    if not date_str:
        date_str = dates_map.get(clean_for_match(base_name), "")

    # 링크 생성 (파일명과 100% 동일)
    safe_url = urllib.parse.quote(base_name)
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    cards_html += f"""    <a href="{link}" class="card-item" data-category="{category}">
        <div class="card-thumb" style="background-image: url('{img_url}');"></div>
        <div class="card-content">
            <div>
                <div class="card-category">{category}</div>
                <h3 class="card-title">{true_title}</h3>
            </div>
            <div class="card-date">{date_str}</div>
        </div>
    </a>\n"""

# 3. index.md 생성
html_content = f"""---
layout: default
title: '전체 글 목록'
subtitle: '심플리파이어의 {post_count}개의 글'
is_index: true
---

<style>
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .card-item.visible {{
        display: flex !important;
        animation: fadeInUp 0.4s ease forwards;
    }}
    #scrollSentinel {{ height: 50px; margin-top: 30px; }}
</style>

<div class="category-filter">
    <button class="cat-btn active" data-filter="all">전체보기</button>
"""

for cat in sorted(list(unique_categories)):
    html_content += f'    <button class="cat-btn" data-filter="{cat}">{cat}</button>\n'

html_content += f"""</div>\n\n<div class="card-grid" id="cardGrid">\n{cards_html}</div>

<div id="scrollSentinel"></div>

<script>
    document.addEventListener('DOMContentLoaded', function() {{
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const sentinel = document.getElementById('scrollSentinel');
        
        const itemsPerBatch = 20;
        let currentVisibleCount = 0;
        let filteredCards = cards;

        function loadNextBatch() {{
            if (currentVisibleCount >= filteredCards.length) return;
            const start = currentVisibleCount;
            const end = Math.min(currentVisibleCount + itemsPerBatch, filteredCards.length);
            for (let i = start; i < end; i++) {{
                filteredCards[i].classList.add('visible');
                filteredCards[i].style.animationDelay = (i - start) * 0.03 + 's';
            }}
            currentVisibleCount = end;
        }}

        function applyFilter(filter) {{
            cards.forEach(card => {{
                card.classList.remove('visible');
                card.style.animationDelay = '0s';
            }});
            if (filter === 'all') {{
                filteredCards = cards;
            }} else {{
                filteredCards = cards.filter(card => card.getAttribute('data-category') === filter);
            }}
            currentVisibleCount = 0;
            loadNextBatch();
        }}

        const observer = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) loadNextBatch();
            }});
        }}, {{ rootMargin: '200px' }});

        if (sentinel) observer.observe(sentinel);

        filterBtns.forEach(btn => {{
            btn.addEventListener('click', function() {{
                filterBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                applyFilter(this.getAttribute('data-filter'));
            }});
        }});

        applyFilter('all');
    }});
</script>
"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ 완벽 교정 완료! 파일 내부 타이틀 수정 및 썸네일 경로 인코딩이 적용되었습니다.")