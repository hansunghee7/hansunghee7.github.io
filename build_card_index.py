import os
import csv
import urllib.parse
import re

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

def clean_and_pure(text):
    no_prefix = re.sub(r'^[\d#\._\s]+', '', text)
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', no_prefix)

def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

def get_first_image(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'!\[.*?\]\((.*?)\)', content)
            if not match:
                match = re.search(r'<img\s+.*?src=["\'](.*?)["\']', content)
            
            if match:
                img_path = match.group(1).strip()
                if not img_path.startswith('http') and not img_path.startswith('/'):
                    img_path = '/' + img_path
                return img_path
    except Exception as e:
        pass
    return "/brunch_web_assets/images/logo_white.png"

categories_map = {}
dates_map = {}
unique_categories = set()

try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) > 1:
                pure_title = clean_and_pure(row[1])
                raw_cat = row[0].strip()
                cat = clean_category_name(raw_cat)
                
                categories_map[pure_title] = cat
                if cat and cat != "미분류" and cat != "기타":
                    unique_categories.add(cat)
                
                if len(row) > 2:
                    dates_map[pure_title] = row[2].strip()
except Exception as e:
    print("❌ CSV 파일 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

html_content = f"""---
layout: default
title: '전체 글 목록'
category: 'Simplifier'
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

<!-- 본문 안내 문구 삭제 후 바로 필터 영역 배치 -->
<div class="category-filter">
    <button class="cat-btn active" data-filter="all">전체보기</button>
"""

for cat in sorted(list(unique_categories)):
    html_content += f'    <button class="cat-btn" data-filter="{cat}">{cat}</button>\n'

html_content += """</div>

<div class="card-grid" id="cardGrid">
"""

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    base_name = filename[:-3]
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    pure_title = clean_and_pure(base_name)
    
    category = categories_map.get(pure_title, "기타")
    date_str = dates_map.get(pure_title, "")
    img_url = get_first_image(filepath)
    
    safe_url = urllib.parse.quote(base_name)
    link = f"/brunch_web_assets/markdown/{safe_url}.html"
    
    html_content += f"""    <a href="{link}" class="card-item" data-category="{category}">
        <div class="card-thumb" style="background-image: url('{img_url}');"></div>
        <div class="card-content">
            <div>
                <div class="card-category">{category}</div>
                <h3 class="card-title">{display_title}</h3>
            </div>
            <div class="card-date">{date_str}</div>
        </div>
    </a>
"""

html_content += """</div>

<div id="scrollSentinel"></div>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const sentinel = document.getElementById('scrollSentinel');
        
        const itemsPerBatch = 20;
        let currentVisibleCount = 0;
        let filteredCards = cards;

        function loadNextBatch() {
            if (currentVisibleCount >= filteredCards.length) return;

            const start = currentVisibleCount;
            const end = Math.min(currentVisibleCount + itemsPerBatch, filteredCards.length);

            for (let i = start; i < end; i++) {
                filteredCards[i].classList.add('visible');
                filteredCards[i].style.animationDelay = (i - start) * 0.03 + 's';
            }

            currentVisibleCount = end;
        }

        function applyFilter(filter) {
            cards.forEach(card => {
                card.classList.remove('visible');
                card.style.animationDelay = '0s';
            });

            if (filter === 'all') {
                filteredCards = cards;
            } else {
                filteredCards = cards.filter(card => card.getAttribute('data-category') === filter);
            }

            currentVisibleCount = 0;
            loadNextBatch();
        }

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    loadNextBatch();
                }
            });
        }, { rootMargin: '200px' });

        if (sentinel) observer.observe(sentinel);

        filterBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                filterBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                applyFilter(this.getAttribute('data-filter'));
            });
        });

        applyFilter('all');
    });
</script>
"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ 상단 타이틀 문구 반영 및 본문 안내 문구 삭제 완료!")