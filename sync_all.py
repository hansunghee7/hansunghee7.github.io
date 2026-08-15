import os
import re
import urllib.parse
import csv
import json

# 👇 카테고리별 기본 정렬 방식
CATEGORY_SORT_DEFAULTS = {
    "AI의 언어들": "desc",
    "Be the PO": "desc",
    "PO의 프레임웍": "asc",
    "UX의 언어들": "desc",
    "기획일상": "desc",
    "기획자의 프레임웍": "asc",
    "대한민국 스타트업 미국진출을 묻다": "asc",
    "스타트업 인사이트": "desc",
    "심플리파이어 라이프": "desc",
    "심플한 창업하고 파이어하게 일하기": "asc",
    "이력서에 쓰지 않는 첫직장 이야기": "asc",
    "잉크드인대 기획학과": "asc",
    "코치S": "asc",
    "토크세션": "desc"
}

if os.path.exists("index.md"):
    os.remove("index.md")

md_dir = "brunch_web_assets/markdown"
index_file = "index.html"
csv_file = "브런치_글_모음집.csv"

csv_dates = {}
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 3:
                clean_title = re.sub(r'[^가-힣a-zA-Z0-9]', '', row[1])
                csv_dates[clean_title] = row[2].strip()
except Exception as e:
    pass

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

# 1차 패스: 모든 글 데이터 수집 및 카테고리별 매핑
posts = []
category_posts = {}

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    pub_match = re.search(r"^published:\s*(false|true)", content, re.MULTILINE | re.IGNORECASE)
    if pub_match and pub_match.group(1).lower() == 'false':
        continue

    title_match = re.search(r"^title:\s*(.*)$", content, re.MULTILINE)
    cat_match = re.search(r"^category:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    cover_match = re.search(r"^cover_image:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    
    if title_match:
        raw_title = title_match.group(1).strip()
        if (raw_title.startswith('"') and raw_title.endswith('"')) or (raw_title.startswith("'") and raw_title.endswith("'")):
            raw_title = raw_title[1:-1]
        title = raw_title.replace('\\"', '"').replace("\\'", "'")
    else:
        title = filename[:-3]

    category = cat_match.group(1).strip() if cat_match else "기타"
    cover_image = cover_match.group(1).strip() if cover_match else "/brunch_web_assets/images/logo_white.png"

    title_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', title)
    filename_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', filename[:-3])
    date_string = csv_dates.get(title_clean, csv_dates.get(filename_clean, ""))

    safe_url = urllib.parse.quote(filename[:-3])
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    months = {'Jan':'01', 'Feb':'02', 'Mar':'03', 'Apr':'04', 'May':'05', 'Jun':'06', 'Jul':'07', 'Aug':'08', 'Sep':'09', 'Oct':'10', 'Nov':'11', 'Dec':'12'}
    timestamp = "00000000"
    try:
        parts = date_string.replace('.', '').replace(',', '').split()
        if len(parts) >= 3:
            timestamp = f"{parts[2]}{months.get(parts[0][:3], '00')}{parts[1].zfill(2)}"
    except: pass

    uid = 0
    uid_match = re.match(r'^(\d+)_', filename)
    if uid_match: uid = int(uid_match.group(1))

    body_content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
    body_content = re.sub(r'\n<!-- CATEGORY_NAV_START -->.*?<!-- CATEGORY_NAV_END -->', '', body_content, flags=re.DOTALL).strip()

    post_data = {
        'filename': filename,
        'filepath': filepath,
        'title': title,
        'category': category,
        'cover_image': cover_image,
        'date_string': date_string,
        'link': link,
        'timestamp': timestamp,
        'uid': uid,
        'body_content': body_content
    }
    posts.append(post_data)

    if category not in category_posts:
        category_posts[category] = []
    category_posts[category].append(post_data)

# 카테고리별 글 정렬
for cat in category_posts:
    category_posts[cat].sort(key=lambda x: x['uid'])

cards_html = ""
unique_categories = set()
post_count = 0

for p in posts:
    category = p['category']
    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    cat_list = category_posts.get(category, [])
    idx = -1
    for i, item in enumerate(cat_list):
        if item['filename'] == p['filename']:
            idx = i
            break

    prev_post = cat_list[idx - 1] if idx > 0 else None
    next_post = cat_list[idx + 1] if idx >= 0 and idx < len(cat_list) - 1 else None

    nav_html = "\n\n<!-- CATEGORY_NAV_START -->\n<style>\n" \
               ".category-nav-wrap { margin-top: 80px; padding: 25px 40px; border-top: 1px solid #e1e1e1; display: flex; justify-content: space-between; align-items: center; font-family: 'Noto Sans KR', sans-serif; font-size: 14px; color: #888; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }\n" \
               ".cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #666; transition: color 0.2s; max-width: 45%; }\n" \
               ".cat-nav-item:hover { color: #111; }\n" \
               ".cat-nav-item:hover .nav-title { color: #111; text-decoration: underline; }\n" \
               ".cat-nav-label { font-size: 13px; color: #999; white-space: nowrap; font-weight: 300; }\n" \
               ".nav-title { font-weight: 400; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n" \
               ".cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }\n" \
               "</style>\n<div class=\"category-nav-wrap\">\n"

    if prev_post:
        nav_html += f'  <a href="{prev_post["link"]}" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">\'{category}\'의 이전글</span><span class="nav-title">{prev_post["title"]}</span></a>\n'
    else:
        nav_html += f'  <div></div>\n'

    if next_post:
        nav_html += f'  <a href="{next_post["link"]}" class="cat-nav-item cat-nav-right"><span class="nav-title">{next_post["title"]}</span><span class="cat-nav-label">\'{category}\'의 다음글</span></a>\n'
    else:
        nav_html += f'  <div></div>\n'

    nav_html += "</div>\n<!-- CATEGORY_NAV_END -->"

    safe_title = p['title'].replace('"', '\\"')
    new_yaml = f"---\nlayout: default\ntitle: \"{safe_title}\"\ncategory: '{category}'\ncover_image: '{p['cover_image']}'\ndate_string: '{p['date_string']}'\n---\n\n"

    with open(p['filepath'], 'w', encoding='utf-8') as f:
        f.write(new_yaml + p['body_content'] + nav_html)

    cards_html += f'<a href="{p["link"]}" class="card-item" data-category="{category}" data-date="{p["timestamp"]}" data-id="{p["uid"]}"><div class="card-thumb-wrap"><div class="card-thumb" style="background-image: url(\'{p["cover_image"]}\');"></div></div><div class="card-content"><div><div class="card-category">{category}</div><h3 class="card-title">{p["title"]}</h3></div><div class="card-date">{p["date_string"]}</div></div></a>'
    post_count += 1

html_header = f"---\nlayout: default\ntitle: 'Simplifier Log {post_count}'\nis_index: true\n---\n"

default_sorts_json = json.dumps(CATEGORY_SORT_DEFAULTS, ensure_ascii=False)

# 🌟 상단 모든 구조(header, header-bg, hero, nav 등)에 딥 블랙(#111111) 강제 부여
html_body = """<style>
@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.card-item.visible { display: flex !important; animation: fadeInUp 0.4s ease forwards; }
#scrollSentinel { height: 50px; margin-top: 30px; }

/* 🖤 상단 타이틀 및 헤더 영역 전체를 딥 블랙(#111111)으로 강제 적용 */
header, .site-header, .header-wrap, .hero-section, .intro-banner, .header-bg, .top-bar, div[class*="header"], div[class*="hero"] {
    background-color: #111111 !important;
    background: #111111 !important;
    color: #ffffff !important;
}

.filter-wrap { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 20px; margin-bottom: 35px; }
.category-filter { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
.cat-btn { padding: 7px 16px; border: 1px solid #e1e1e1; border-radius: 20px; background: #fff; color: #666; font-size: 13px; font-weight: 300; cursor: pointer; transition: all 0.2s; font-family: 'Noto Sans KR', sans-serif; }
.cat-btn:hover { border-color: #111111; color: #111111; }

.cat-btn.active { background: #111111; color: #ffffff !important; border-color: #111111; font-weight: 300; }

.sort-filter { display: flex; gap: 15px; align-items: center; margin-bottom: 5px; }
.sort-text-btn { background: none; border: none; font-size: 14px; color: #a0a0a0; cursor: pointer; font-family: 'Noto Sans KR', sans-serif; font-weight: 300; display: flex; align-items: center; padding: 0; transition: color 0.2s; }
.sort-text-btn:hover { color: #555; }
.sort-text-btn.active { color: #111; font-weight: 400; }
.sort-text-btn .dot { display: inline-block; width: 4px; height: 4px; border-radius: 50%; background-color: transparent; margin-right: 4px; margin-bottom: 2px; }
.sort-text-btn.active .dot { background-color: #6CFD33; }

.card-item { border: 1px solid #e1e1e1; border-radius: 12px; overflow: hidden; transition: border-color 0.3s ease, box-shadow 0.3s ease; text-decoration: none !important; color: inherit; }
.card-thumb-wrap { width: 100%; height: 180px; overflow: hidden; position: relative; }
.card-thumb { width: 100%; height: 100%; background-size: cover; background-position: center; filter: grayscale(100%); transition: transform 0.4s ease, filter 0.4s ease; }

.card-item:hover { border-color: #6CFD33 !important; box-shadow: 0 6px 20px rgba(108, 253, 51, 0.15); }
.card-item:hover .card-thumb { transform: scale(1.08); filter: grayscale(0%); }
.card-category { color: #222; font-weight: 500; }
</style>

<div class="filter-wrap"><div class="category-filter"><button class="cat-btn active" data-filter="all">전체보기</button>"""

for cat in sorted(list(unique_categories)):
    html_body += f'<button class="cat-btn" data-filter="{cat}">{cat}</button>'

html_body += """</div><div class="sort-filter"><button class="sort-text-btn active" data-sort="desc"><span class="dot"></span>최신순</button><button class="sort-text-btn" data-sort="asc"><span class="dot"></span>날짜순</button></div></div><div class="card-grid" id="cardGrid">""" + cards_html + """</div><div id="scrollSentinel"></div><script>document.addEventListener('DOMContentLoaded', function() { const cards = Array.from(document.querySelectorAll('.card-item')); const filterBtns = document.querySelectorAll('.cat-btn'); const sortBtns = document.querySelectorAll('.sort-text-btn'); const sentinel = document.getElementById('scrollSentinel'); const grid = document.getElementById('cardGrid'); let itemsPerBatch = 20, currentVisibleCount = 0; let filteredCards = [...cards]; let currentFilter = 'all'; 

const categoryDefaults = """ + default_sorts_json + """;

function getSortMode(cat) { 
    return localStorage.getItem('brunchSort_' + cat) || categoryDefaults[cat] || 'desc'; 
} 

function saveSortMode(cat, mode) { localStorage.setItem('brunchSort_' + cat, mode); } 

const urlParams = new URLSearchParams(window.location.search); const catParam = urlParams.get('cat'); if (catParam) { const targetBtn = Array.from(filterBtns).find(b => b.getAttribute('data-filter') === catParam); if (targetBtn) { filterBtns.forEach(b => b.classList.remove('active')); targetBtn.classList.add('active'); currentFilter = catParam; } } 

let sortMode = getSortMode(currentFilter); 

function updateSortUI() { sortBtns.forEach(b => { b.classList.remove('active'); if(b.getAttribute('data-sort') === sortMode) { b.classList.add('active'); } }); } 
updateSortUI(); 

function loadNextBatch() { if (currentVisibleCount >= filteredCards.length) return; const start = currentVisibleCount; const end = Math.min(currentVisibleCount + itemsPerBatch, filteredCards.length); for (let i = start; i < end; i++) { filteredCards[i].classList.add('visible'); filteredCards[i].style.animationDelay = (i - start) * 0.03 + 's'; } currentVisibleCount = end; } 

function applyFilterAndSort() { cards.forEach(card => { card.classList.remove('visible'); card.style.animationDelay = '0s'; }); filteredCards = currentFilter === 'all' ? [...cards] : cards.filter(card => card.getAttribute('data-category') === currentFilter); filteredCards.sort((a, b) => { let dateA = parseInt(a.getAttribute('data-date')) || 0; let dateB = parseInt(b.getAttribute('data-date')) || 0; if (dateA === dateB) { let idA = parseInt(a.getAttribute('data-id')) || 0; let idB = parseInt(b.getAttribute('data-id')) || 0; return sortMode === 'desc' ? idB - idA : idA - idB; } return sortMode === 'desc' ? dateB - dateA : dateA - dateB; }); filteredCards.forEach(card => grid.appendChild(card)); currentVisibleCount = 0; loadNextBatch(); } 

sortBtns.forEach(btn => { btn.addEventListener('click', function() { sortMode = this.getAttribute('data-sort'); saveSortMode(currentFilter, sortMode); updateSortUI(); applyFilterAndSort(); }); }); 

filterBtns.forEach(btn => { btn.addEventListener('click', function() { filterBtns.forEach(b => b.classList.remove('active')); this.classList.add('active'); currentFilter = this.getAttribute('data-filter'); const newUrl = currentFilter === 'all' ? window.location.pathname : window.location.pathname + '?cat=' + encodeURIComponent(currentFilter); window.history.pushState({path:newUrl}, '', newUrl); sortMode = getSortMode(currentFilter); updateSortUI(); applyFilterAndSort(); }); }); 

const observer = new IntersectionObserver(entries => { entries.forEach(entry => { if (entry.isIntersecting) loadNextBatch(); }); }, { rootMargin: '200px' }); if (sentinel) observer.observe(sentinel); applyFilterAndSort(); });</script>"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html_header + html_body)

print("✅ 상단 모든 헤더 구조에 딥 블랙(#111111) 강제 적용 완료!")