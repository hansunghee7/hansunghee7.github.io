import os
import re
import urllib.parse
import csv

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

# 숫자, 기호, 띄어쓰기를 모두 무시하고 '순수 한글/영문'만 뽑아내어 100% 일치시키는 마법의 함수
def pure_text(text):
    return re.sub(r'[^가-힣a-zA-Z]', '', text)

def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

# 1. 엑셀 데이터에서 날짜 매칭 맵 만들기
dates_map = {}
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) > 2:
                # 엑셀의 제목도 순수 글자만 뽑아서 저장 ("#1. 당신이..." -> "당신이...")
                dates_map[pure_text(row[1])] = row[2].strip()
except Exception as e:
    print("CSV 읽기 에러:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()
post_count = len(md_files)

cards_html = ""
unique_categories = set()

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    base_name = filename[:-3]
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name) # 화면에 보일 제목 (숫자 제거)
    
    cat_match = re.search(r"^category:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    category = clean_category_name(cat_match.group(1)) if cat_match else "기타"
    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    # 2. 썸네일 이중 인코딩 방지 및 완벽 경로 복원
    img_url = "/brunch_web_assets/images/logo_white.png"
    img_match = re.search(r'!\[.*?\]\(([^)]+)\)', content)
    if not img_match:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        
    if img_match:
        raw_url = img_match.group(1).strip().split()[0].strip('"\'')
        # 이미 %20 등으로 변환된 주소를 사람의 언어로 한번 풀었다가, 가장 안전한 방식으로 재포장!
        decoded_url = urllib.parse.unquote(raw_url)
        
        if decoded_url.startswith('../images/'):
            decoded_url = '/brunch_web_assets/images/' + decoded_url.split('../images/')[-1]
        elif not decoded_url.startswith('http') and not decoded_url.startswith('data:') and not decoded_url.startswith('/'):
            decoded_url = '/brunch_web_assets/markdown/' + decoded_url
            
        img_url = urllib.parse.quote(decoded_url, safe='/:?=&')

    # 3. 날짜 완벽 매칭 (파일 이름의 순수 글자와 엑셀의 순수 글자 비교)
    date_str = dates_map.get(pure_text(base_name), "")

    # 4. 링크 100% 매칭
    safe_url = urllib.parse.quote(base_name)
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

# 5. HTML 머리말 (타이틀 변경 적용) + 본문 조립
html_header = f"""---
layout: default
title: '심플리파이어의 {post_count}개의 글'
is_index: true
---
"""

html_body = """
<style>
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    .card-item.visible { display: flex !important; animation: fadeInUp 0.4s ease forwards; }
    #scrollSentinel { height: 50px; margin-top: 30px; }
</style>

<div class="category-filter">
    <button class="cat-btn active" data-filter="all">전체보기</button>
"""

for cat in sorted(list(unique_categories)):
    html_body += f'    <button class="cat-btn" data-filter="{cat}">{cat}</button>\n'

html_body += f"""</div>

<div class="card-grid" id="cardGrid">
{cards_html}</div>

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
    f.write(html_header + html_body)

print("✅ 완벽 교정 완료! 썸네일 경로, 날짜 매칭, 그리고 메인 타이틀까지 완벽하게 적용되었습니다.")