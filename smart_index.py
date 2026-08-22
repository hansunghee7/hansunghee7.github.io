import os
import csv
import urllib.parse
import re

md_dir = "log_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

def clean_and_pure(text):
    no_prefix = re.sub(r'^[\d#\._\s]+', '', text)
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', no_prefix)

# 1. 스프레드시트에서 카테고리 맵핑 및 고유 카테고리 목록 추출
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

# 2. 마크다운 파일 목록 가져오기 (001번부터 순서대로)
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort() 

# 3. 마법의 UI/UX 코드가 담긴 index.md 생성
index_content = """---
layout: default
title: '전체 글 목록'
category: 'Simplifier'
---

<style>
    /* 필터 버튼 디자인 */
    .category-filter { margin: 20px 0 50px 0; display: flex; flex-wrap: wrap; gap: 8px; }
    .cat-btn { 
        padding: 8px 18px; border: 1px solid #ddd; border-radius: 25px; 
        background: #fff; color: #777; font-size: 14px; font-weight: 400; 
        cursor: pointer; transition: all 0.2s; font-family: 'Noto Sans KR', sans-serif;
    }
    .cat-btn:hover { border-color: #00c73c; color: #00c73c; }
    .cat-btn.active { background: #00c73c; color: #fff; border-color: #00c73c; }
    
    /* 리스트 및 애니메이션 */
    .post-list { list-style: none; padding: 0; }
    .post-item { display: none; margin-bottom: 30px; animation: fadeIn 0.5s ease forwards; }
    .post-item.visible { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    
    /* 더보기 버튼 디자인 */
    .load-more-wrap { text-align: center; margin: 50px 0 80px 0; }
    .load-more-btn {
        padding: 12px 40px; border: 1px solid #ccc; border-radius: 30px;
        background: #fff; color: #333; font-size: 15px; cursor: pointer;
        transition: all 0.2s; font-family: 'Noto Sans KR', sans-serif;
    }
    .load-more-btn:hover { background: #f9f9f9; border-color: #999; }
</style>

<br>
<p style="font-weight:300; color:#666;">성희님의 브런치 글 {total}개입니다. 원하는 카테고리를 선택해 보세요!</p>

<!-- 카테고리 필터 버튼 영역 -->
<div class="category-filter">
    <button class="cat-btn active" data-filter="all">전체보기</button>
""".format(total=len(md_files))

# 카테고리 버튼 생성
for cat in sorted(list(unique_categories)):
    safe_cat = cat.replace('"', '&quot;')
    index_content += f'    <button class="cat-btn" data-filter="{safe_cat}">{cat}</button>\n'

index_content += "</div>\n\n<!-- 전체 글 목록 영역 -->\n<ul class=\"post-list\" id=\"postList\">\n"

# 개별 글 리스트 아이템 생성 (data-category 속성 부여)
for filename in md_files:
    base_name = filename[:-3]
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    pure_title = clean_and_pure(base_name)
    category = categories_map.get(pure_title, "미분류")
    safe_cat = category.replace('"', '&quot;')
    
    safe_url = urllib.parse.quote(base_name)
    link = f"/log_assets/markdown/{safe_url}.html"
    
    index_content += f"    <li class=\"post-item\" data-category=\"{safe_cat}\"><span class='list-category'>{category}</span><a href=\"{link}\">{display_title}</a></li>\n"

index_content += """</ul>

<!-- 더보기 버튼 영역 -->
<div class="load-more-wrap" id="loadMoreWrap">
    <button class="load-more-btn" id="loadMoreBtn">더보기 ↓</button>
</div>

<script>
    // 필터링 및 더보기 기능을 작동시키는 마법의 자바스크립트
    document.addEventListener('DOMContentLoaded', function() {
        const items = Array.from(document.querySelectorAll('.post-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        const loadMoreWrap = document.getElementById('loadMoreWrap');
        
        let currentFilter = 'all';
        let itemsToShow = 20; // 한 번에 보여줄 글 개수
        let currentVisible = 0;
        let filteredItems = items;

        function render() {
            items.forEach(item => item.classList.remove('visible')); // 모두 숨기기
            
            for(let i=0; i<currentVisible && i<filteredItems.length; i++) {
                filteredItems[i].classList.add('visible'); // 계산된 개수만큼 나타내기
            }
            
            // 보여줄 글이 더 이상 없으면 더보기 버튼 숨기기
            if (currentVisible >= filteredItems.length) {
                loadMoreWrap.style.display = 'none';
            } else {
                loadMoreWrap.style.display = 'block';
            }
        }

        function applyFilter(filter) {
            currentFilter = filter;
            if (filter === 'all') {
                filteredItems = items;
            } else {
                filteredItems = items.filter(item => item.getAttribute('data-category') === filter);
            }
            currentVisible = Math.min(itemsToShow, filteredItems.length);
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
            if (currentVisible > filteredItems.length) currentVisible = filteredItems.length;
            render();
        });

        applyFilter('all'); // 초기 화면 세팅
    });
</script>
"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(index_content)

print("✅ 상단 카테고리 필터와 '더보기' 기능이 탑재된 index.md가 성공적으로 생성되었습니다!")