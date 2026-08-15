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

# 1. 마크다운 파일에서 대표 이미지 URL 추출하는 함수
def get_first_image(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # 이미지 마크다운 ![...](url) 패턴 검색
            match = re.search(r'!\[.*?\]\((.*?)\)', content)
            if match:
                return match.group(1)
    except:
        pass
    # 이미지 없을 경우 기본 더미 이미지 또는 브런치 배경용 색상 처리
    return "/brunch_web_assets/images/logo_white.png"

# 2. CSV에서 카테고리 정보 추출
categories_map = {}
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
except Exception as e:
    print("❌ CSV 파일 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

# 3. index.md 내 순수 HTML 코드로 빌드
html_content = f"""---
layout: default
title: '전체 글 목록'
category: 'Simplifier'
---

<div style="margin-bottom: 25px; color: #666; font-weight: 300;">
    성희님의 브런치 글 {len(md_files)}개입니다. 카테고리를 선택해 글을 둘러보세요!
</div>

<!-- 카테고리 필터 영역 -->
<div class="category-filter">
    <button class="cat-btn active" data-filter="all">전체보기</button>
"""

for cat in sorted(list(unique_categories)):
    html_content += f'    <button class="cat-btn" data-filter="{cat}">{cat}</button>\n'

html_content += """</div>

<!-- 카드 그리드 영역 -->
<div class="card-grid" id="cardGrid">
"""

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    base_name = filename[:-3]
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    pure_title = clean_and_pure(base_name)
    category = categories_map.get(pure_title, "미분류")
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
            <div class="card-author">by Simplifier 한성희</div>
        </div>
    </a>
"""

html_content += """</div>

<!-- 더보기 버튼 -->
<div class="load-more-wrap" id="loadMoreWrap">
    <button class="load-more-btn" id="loadMoreBtn">더보기 ↓</button>
</div>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        const loadMoreWrap = document.getElementById('loadMoreWrap');
        
        let itemsToShow = 20; // 한 번에 20개씩 노출
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

print("✅ 카드 뷰 레이아웃과 필터 기능이 들어간 index.md 생성 완료!")