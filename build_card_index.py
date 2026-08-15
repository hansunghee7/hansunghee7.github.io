import os
import re
import urllib.parse
import csv

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

def clean_for_match(text):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

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

# 파일 개수를 정확히 셉니다!
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()
post_count = len(md_files) # 동적 개수

cards_html = ""
unique_categories = set()

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    title_match = re.search(r"^title:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    if title_match:
        display_title = title_match.group(1).strip()
    else:
        display_title = re.sub(r'^[\d#\._\s]+', '', filename[:-3])

    cat_match = re.search(r"^category:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    if cat_match:
        category = cat_match.group(1).strip()
    else:
        category = "기타"
        
    category = re.sub(r'^(매거진|브런치북)\s*:\s*', '', category).strip()
    if not category: category = "기타"
    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    img_url = "/brunch_web_assets/images/logo_white.png"
    img_match = re.search(r'!\[.*?\]\(([^)]+)\)', content)
    
    if not img_match:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        
    if img_match:
        raw_url = img_match.group(1).strip().split()[0].strip('"\'')
        if not raw_url.startswith('http') and not raw_url.startswith('data:'):
            if '../images/' in raw_url:
                img_url = '/brunch_web_assets/images/' + raw_url.split('../images/')[-1]
            elif 'brunch_web_assets' not in raw_url:
                clean_path = re.sub(r'^[\./]+', '', raw_url)
                img_url = '/brunch_web_assets/markdown/' + clean_path
            elif not raw_url.startswith('/'):
                img_url = '/' + raw_url
            else:
                img_url = raw_url
        else:
            img_url = raw_url

    date_str = dates_map.get(clean_for_match(display_title), "")
    if not date_str:
        date_str = dates_map.get(clean_for_match(filename[:-3]), "")

    safe_url = urllib.parse.quote(filename[:-3])
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    cards_html += f"""    <a href="{link}" class="card-item" data-category="{category}">
        <div class="card-thumb" style="background-image: url('{img_url}');"></div>
        <div class="card-content">
            <div>
                <div class="card-category">{category}</div>
                <h3 class="card-title">{display_title}</h3>
            </div>
            <div class="card-date">{date_str}</div>
        </div>
    </a>\n"""

# is_index: true 와 동적으로 세어진 subtitle을 머리말에 주입합니다.
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

print(f"✅ 글 {post_count}개 감지 완료! 목록 및 포스트 뷰 완벽 분리 적용됨.")