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

def get_first_image(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'!\[.*?\]\((.*?)\)', content)
            if match:
                return match.group(1)
    except:
        pass
    return "/brunch_web_assets/images/logo_white.png"

# 1. CSV에서 카테고리 및 날짜 정보 읽어오기
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
                cat = row[0].strip()
                categories_map[pure_title] = cat
                if cat and cat != "미분류":
                    unique_categories.add(cat)
                
                # 날짜 데이터 추출 (3번째 열에 날짜가 존재하는 경우)
                if len(row) > 2:
                    dates_map[pure_title] = row[2].strip()
except Exception as e:
    print("❌ CSV 파일 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

# 2. index.md 내 3:2 카드뷰 HTML 작성
html_content = f"""---
layout: default
title: '전체 글 목록'
category: 'Simplifier'
---

<div style="margin-bottom: 25px; color: #666; font-weight: 300;">
    성희님의 브런치 글 {len(md_files)}개입니다. 카테고리를 선택해 글을 둘러보세요!
</div>

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
    category = categories_map.get(pure_title, "미분류")
    date_str = dates_map.get(pure_title, "") # 등록일 가져오기
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

<div class="load-more-wrap" id="loadMoreWrap">
    <button class="load-more-btn" id="loadMoreBtn">더보기 ↓</button>
</div>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        const loadMoreWrap = document.getElementById('loadMoreWrap');
        
        let itemsToShow = 20;
        let currentVisible = 0;
        let filteredCards = cards;

        function render() {
            cards.forEach(card => card.classList.remove('visible'));
            
            for(let i = 0; i < currentVisible && i < filteredCards.length; i++) {
                filteredCards[i].classList.add('visible');
            }
            
            if (currentVisible >= filteredCards.length) {
                loadMoreWrap.style.display = 'none';
            } else {
                loadMoreWrap.style.display = 'block';
            }
        }

        function applyFilter(filter) {
            if (filter === 'all') {
                filteredCards = cards;
            } else {
                filteredCards = cards.filter(card => card.getAttribute('data-category') === filter);
            }
            currentVisible = Math.min(itemsToShow, filteredCards.length);
            render();
        }

        filterBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                filterBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                applyFilter(this.getAttribute('data-filter'));
            });
        });

        loadMoreBtn.addEventListener('click', function() {
            currentVisible += itemsToShow;
            render();
        });

        applyFilter('all');
    });
</script>
"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ 3:2 카드 비율 및 날짜 표기 적용 완료!")