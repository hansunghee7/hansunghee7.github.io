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

# 1. CSV 정보 읽어오기
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
                
                if len(row) > 2:
                    dates_map[pure_title] = row[2].strip()
except Exception as e:
    print("❌ CSV 파일 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

# 2. index.md 생성 (무한 스크롤 & 카드 상승 애니메이션 포함)
html_content = f"""---
layout: default
title: '전체 글 목록'
category: 'Simplifier'
---

<style>
    /* 🎬 카드가 스르륵 올라오는 애니메이션 정의 */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(30px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    .card-item.visible {{
        display: flex !important;
        animation: fadeInUp 0.5s cubic-bezier(0.25, 1, 0.5, 1) forwards;
    }}

    /* 무한 스크롤 감지용 센서 영역 */
    #scrollSentinel {{
        height: 60px;
        margin-top: 40px;
    }}
</style>

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

<!-- 바닥 감지용 무한 스크롤 감지기 -->
<div id="scrollSentinel"></div>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const sentinel = document.getElementById('scrollSentinel');
        
        const itemsPerBatch = 20; // 스크롤 시 추가 노출 개수
        let currentVisibleCount = 0;
        let filteredCards = cards;

        // 다음 배치 로드 함수
        function loadNextBatch() {
            if (currentVisibleCount >= filteredCards.length) return;

            const start = currentVisibleCount;
            const end = Math.min(currentVisibleCount + itemsPerBatch, filteredCards.length);

            for (let i = start; i < end; i++) {
                filteredCards[i].classList.add('visible');
                // 카드마다 약간의 시간차(Stagger)를 주어 순차적으로 솟아오르는 효과
                filteredCards[i].style.animationDelay = (i - start) * 0.04 + 's';
            }

            currentVisibleCount = end;
        }

        // 필터 변경 처리
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

        // 🚀 IntersectionObserver를 활용한 무한 스크롤 구현 (고성능)
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    loadNextBatch();
                }
            });
        }, {
            rootMargin: '200px' // 화면 바닥 도착 200px 전에 미리 로딩 시작
        });

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

print("✅ 무한 스크롤 및 카드 등장 애니메이션 적용 완료!")