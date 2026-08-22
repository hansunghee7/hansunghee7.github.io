import os
import re
import urllib.parse
import csv
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

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

BASE_URL = "https://hansunghee7.github.io" 
index_file = "log.html"
csv_file = "브런치_글_모음집.csv"
md_dir = "brunch_web_assets/markdown"

if os.path.exists("index.md"):
    os.remove("index.md")

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

og_cache_file = "og_cache_v2.json"
og_cache = {}
if os.path.exists(og_cache_file):
    try:
        with open(og_cache_file, 'r', encoding='utf-8') as f:
            og_cache = json.load(f)
    except: pass

def get_og_card(url):
    url = url.strip()
    if url in og_cache:
        return og_cache[url]
    
    print(f"🔗 링크 정보 수집 중: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        title_tag = soup.find('meta', property='og:title')
        title = title_tag['content'] if title_tag and title_tag.get('content') else soup.title.string if soup.title else url
        
        desc_tag = soup.find('meta', property='og:description')
        desc = desc_tag['content'] if desc_tag and desc_tag.get('content') else ""
        
        img_tag = soup.find('meta', property='og:image')
        img = img_tag['content'] if img_tag and img_tag.get('content') else ""
        
        if img and img.startswith('/'):
            parsed_uri = urllib.parse.urlparse(url)
            img = f"{parsed_uri.scheme}://{parsed_uri.netloc}{img}"
            
        domain = urllib.parse.urlparse(url).netloc
        
        img_html = f'<div style="width:25%; min-width:160px; background:url(\'{img}\') center/cover no-repeat; border-left:1px solid #e1e1e1;"></div>' if img else ''
        
        card_html = f'''<a href="{url}" target="_blank" style="display:flex; border:1px solid rgba(245,243,238,0.08); background-color:#111; overflow:hidden; text-decoration:none !important; color:#f5f3ee; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:\'Pretendard Variable\', sans-serif; border-radius: 8px;" onmouseover="this.style.borderColor=\'rgba(245,243,238,0.4)\'" onmouseout="this.style.borderColor=\'rgba(245,243,238,0.08)\'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:20px; font-weight:500; color:#f5f3ee; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">{title}</div>
        <div style="font-size:14px; font-weight:300; color:#8f8b82; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;">{desc}</div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#736f67;">{domain}</div>
    </div>
    {img_html}
</a>'''
        
        og_cache[url] = card_html.strip()
        time.sleep(0.3)
        return og_cache[url]
    except Exception:
        return url

def replace_raw_url(match):
    url = match.group(1).strip()
    card = get_og_card(url)
    return card if card else url

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
    date_match = re.search(r"^date_string:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    md_date = date_match.group(1).strip() if date_match else ""
    
    if title_match:
        raw_title = title_match.group(1).strip()
        if (raw_title.startswith('"') and raw_title.endswith('"')) or (raw_title.startswith("'") and raw_title.endswith("'")):
            raw_title = raw_title[1:-1]
        title = raw_title.replace('\\"', '"').replace("\\'", "'")
    else:
        title = filename[:-3]

    category = cat_match.group(1).strip() if cat_match else "기획일상"
    if "\n" in category or len(category) > 30:
        category = category.split("\n")[0].split("|")[0].strip().strip("'\"")
    if not category:
        category = "기획일상"

    # 💡 트레바리 카테고리 강제 변경 규칙
    if category == "트레바리":
        category = "토크세션"

    cover_image = cover_match.group(1).strip() if cover_match else "/brunch_web_assets/images/logo_white.png"

    title_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', title)
    filename_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', filename[:-3])
    
    csv_date = csv_dates.get(title_clean, csv_dates.get(filename_clean, ""))
    date_string = csv_date if csv_date else md_date

    safe_url = urllib.parse.quote(filename[:-3])
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    timestamp = "00000000"
    try:
        clean_date = date_string.replace('.', ' ').replace(',', ' ').strip()
        parts = clean_date.split()
        if len(parts) >= 3:
            if len(parts[0]) == 4 and parts[0].isdigit():
                timestamp = f"{parts[0]}{parts[1].zfill(2)}{parts[2].zfill(2)}"
            else:
                months = {'Jan':'01', 'Feb':'02', 'Mar':'03', 'Apr':'04', 'May':'05', 'Jun':'06', 'Jul':'07', 'Aug':'08', 'Sep':'09', 'Oct':'10', 'Nov':'11', 'Dec':'12'}
                timestamp = f"{parts[2]}{months.get(parts[0][:3], '00')}{parts[1].zfill(2)}"
    except: pass

    uid = 0
    uid_match = re.match(r'^(\d+)_', filename)
    if uid_match: uid = int(uid_match.group(1))

    body_content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
    
    body_content = re.sub(r'<!-- PROMO_BANNER_START -->.*?<!-- PROMO_BANNER_END -->', '', body_content, flags=re.DOTALL)
    body_content = re.sub(r'<!-- CATEGORY_NAV_START -->.*?<!-- CATEGORY_NAV_END -->', '', body_content, flags=re.DOTALL)
    body_content = re.sub(r'<!-- OG_CARD_START -->.*?<!-- OG_CARD_END -->', '', body_content, flags=re.DOTALL)
    body_content = re.sub(r'<!-- POST_DATE_START -->.*?<!-- POST_DATE_END -->', '', body_content, flags=re.DOTALL)
    body_content = re.sub(r'<!-- CAT_LINK_SCRIPT_START -->.*?<!-- CAT_LINK_SCRIPT_END -->', '', body_content, flags=re.DOTALL)
    
    body_content = re.sub(r'^https://www\.yes24\.com/product/goods/\d+\s*$', '', body_content, flags=re.MULTILINE)
    body_content = re.sub(r'^https://trevar\.ink/[a-zA-Z0-9]+\s*$', '', body_content, flags=re.MULTILINE)

    body_content = re.sub(r'^\s*(https?://[^\s<>]+)\s*$', replace_raw_url, body_content, flags=re.MULTILINE)
    body_content = body_content.strip()

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

for cat in category_posts:
    category_posts[cat].sort(key=lambda x: x['uid'])

with open(og_cache_file, 'w', encoding='utf-8') as f:
    json.dump(og_cache, f, ensure_ascii=False, indent=2)

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

    cat_script = f"""<!-- CAT_LINK_SCRIPT_START -->
<script>
document.addEventListener('DOMContentLoaded', function() {{
    const catPill = document.querySelector('.cover-category-pill');
    if(catPill) {{
        catPill.style.cursor = 'pointer';
        catPill.style.transition = 'all 0.2s ease';
        catPill.addEventListener('mouseenter', function() {{
            this.style.backgroundColor = '#f5f3ee';
            this.style.color = '#080808';
        }});
        catPill.addEventListener('mouseleave', function() {{
            this.style.backgroundColor = 'transparent';
            this.style.color = '#f5f3ee';
        }});
        catPill.addEventListener('click', function() {{
            window.location.href = '/log.html?cat=' + encodeURIComponent('{category}');
        }});
    }}
}});
</script>
<!-- CAT_LINK_SCRIPT_END -->\n\n"""

    # 💡 이전글/다음글 컨테이너 여백(margin-top, margin-bottom) 대폭 축소
    nav_html = "\n\n<!-- CATEGORY_NAV_START -->\n<style>\n" \
               ".category-nav-wrap { margin-top: 20px; margin-bottom: 20px; padding: 25px 40px; border-top: 1px solid rgba(245,243,238,0.1); display: flex; justify-content: space-between; align-items: center; font-family: 'Pretendard Variable', sans-serif; font-size: 14px; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }\n" \
               ".cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #8f8b82; transition: color 0.2s; max-width: 45%; }\n" \
               ".cat-nav-item:hover { color: #f5f3ee; }\n" \
               ".cat-nav-item:hover .nav-title { color: #f5f3ee; text-decoration: underline; }\n" \
               ".cat-nav-label { font-size: 13px; color: #736f67; white-space: nowrap; font-weight: 300; }\n" \
               ".nav-title { font-weight: 400; color: #c9c8c2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n" \
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

    nav_html += "</div>\n<!-- CATEGORY_NAV_END -->\n"

    safe_title = p['title'].replace('"', '\\"')
    new_yaml = f"---\nlayout: default\ntitle: \"{safe_title}\"\ncategory: '{category}'\ncover_image: '{p['cover_image']}'\ndate_string: '{p['date_string']}'\n---\n\n"

    # 💡 글로벌 프로모션(Simplifier Choice) 변수 아예 제외하고 파일 저장
    with open(p['filepath'], 'w', encoding='utf-8') as f:
        f.write(new_yaml + cat_script + p['body_content'] + nav_html)

    cards_html += f'<a href="{p["link"]}" class="card-item" data-category="{category}" data-date="{p["timestamp"]}" data-id="{p["uid"]}"><div class="card-thumb-wrap"><div class="card-thumb" style="background-image: url(\'{p["cover_image"]}\');"></div></div><div class="card-content"><div><div class="card-category">{category}</div><h3 class="card-title">{p["title"]}</h3></div><div class="card-date">{p["date_string"]}</div></div></a>'
    post_count += 1

html_header = f"---\nlayout: default\ntitle: 'Simplifier Log {post_count}'\nis_index: true\n---\n"

default_sorts_json = json.dumps(CATEGORY_SORT_DEFAULTS, ensure_ascii=False)

html_body = """<style>
/* 1. 상단 무거운 "Simplifier Log" 배너 영역 완전 숨김 */
.cover-wrap.index-mode { display: none !important; }

/* 2. 전체 페이지 배경을 다크 테마(#080808)로 고정 */
body { background-color: #080808 !important; color: #f5f3ee !important; }

/* 3. 본문 영역 컨테이너 여백 및 배경 조정 */
.article-body { max-width: 1200px !important; margin: 0 auto; padding: 60px 32px 120px !important; background-color: #080808 !important; }

/* 4. 카테고리 필터 & 정렬 영역 스타일 */
.filter-wrap { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 20px; margin-bottom: 40px; }
.category-filter { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
.cat-btn { padding: 8px 18px; border: 1px solid rgba(245,243,238,0.12); border-radius: 20px; background: transparent; color: #8f8b82; font-size: 13.5px; font-weight: 400; cursor: pointer; transition: all 0.2s; font-family: 'Pretendard Variable', sans-serif; }
.cat-btn:hover { border-color: rgba(245,243,238,0.4); color: #f5f3ee; }
.cat-btn.active { background: #f5f3ee; color: #080808 !important; border-color: #f5f3ee; font-weight: 600; }

/* 5. 정렬 버튼 (최신순 / 날짜순) 다크 테마 */
.sort-filter { display: flex; gap: 15px; align-items: center; margin-bottom: 5px; }
.sort-text-btn { background: none; border: none; font-size: 14px; color: #8f8b82; cursor: pointer; font-family: 'Pretendard Variable', sans-serif; font-weight: 300; display: flex; align-items: center; padding: 0; transition: color 0.2s; }
.sort-text-btn:hover { color: #f5f3ee; }
.sort-text-btn.active { color: #f5f3ee; font-weight: 500; }
.sort-text-btn .dot { display: inline-block; width: 4px; height: 4px; border-radius: 50%; background-color: transparent; margin-right: 6px; margin-bottom: 2px; }
.sort-text-btn.active .dot { background-color: #f5f3ee !important; }

/* 6. 로그 카드 그리드 다크 테마 디자인 */
.card-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin-top: 20px; }
@media (max-width: 1024px) { .card-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 768px) { .card-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .card-grid { grid-template-columns: repeat(1, 1fr); } }

.card-item { display: none; background: #111 !important; border: 1px solid rgba(245,243,238,0.08) !important; border-radius: 12px; overflow: hidden; transition: transform 0.3s ease, border-color 0.3s ease !important; text-decoration: none !important; color: inherit; flex-direction: column; }
.card-thumb-wrap { width: 100%; height: 180px; overflow: hidden; position: relative; border-bottom: 1px solid rgba(245,243,238,0.05); }
.card-thumb { width: 100%; height: 100%; background-size: cover; background-position: center; transition: transform 0.4s ease; }

.card-item:hover { border-color: rgba(245,243,238,0.25) !important; transform: translateY(-4px); box-shadow: none !important; }
.card-item:hover .card-thumb { transform: scale(1.05); }

.card-content { padding: 20px; display: flex; flex-direction: column; justify-content: space-between; flex-grow: 1; }
.card-category { font-size: 11.5px; color: #8f8b82 !important; font-weight: 500; margin-bottom: 8px; font-family: 'Pretendard Variable', sans-serif; text-transform: uppercase; letter-spacing: 0.05em; }
.card-title { font-family: 'Pretendard Variable', sans-serif; font-size: 15.5px; font-weight: 500; color: #f5f3ee !important; line-height: 1.45; margin: 0 0 16px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-date { font-size: 12px; color: #736f67 !important; margin-top: auto; font-weight: 300; font-family: 'Pretendard Variable', sans-serif; }

@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.card-item.visible { display: flex !important; animation: fadeInUp 0.4s ease forwards; }
#scrollSentinel { height: 50px; margin-top: 30px; }
</style>

<div class="filter-wrap"><div class="category-filter"><button class="cat-btn active" data-filter="all">전체보기</button>"""

for cat in sorted(list(unique_categories)):
    html_body += f'<button class="cat-btn" data-filter="{cat}">{cat}</button>'

html_body += """</div><div class="sort-filter"><button class="sort-text-btn active" data-sort="desc"><span class="dot"></span>최신순</button><button class="sort-text-btn" data-sort="asc"><span class="dot"></span>날짜순</button></div></div><div class="card-grid" id="cardGrid">""" + cards_html + """</div><div id="scrollSentinel"></div><script>document.addEventListener('DOMContentLoaded', function() { 

document.querySelectorAll('header, .site-header, .page-header, .post-header, .masthead, .intro-header').forEach(el => {
    el.style.setProperty('background-color', '#080808', 'important');
    el.style.setProperty('background-image', 'none', 'important');
    el.style.setProperty('background', '#080808', 'important');
});

const cards = Array.from(document.querySelectorAll('.card-item')); const filterBtns = document.querySelectorAll('.cat-btn'); const sortBtns = document.querySelectorAll('.sort-text-btn'); const sentinel = document.getElementById('scrollSentinel'); const grid = document.getElementById('cardGrid'); let itemsPerBatch = 20, currentVisibleCount = 0; let filteredCards = [...cards]; let currentFilter = 'all'; 

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

# ==========================================
# 🌟 1. SEO 강화를 위한 sitemap.xml 자동 생성
# ==========================================
print("🗺️ SEO를 위한 sitemap.xml 및 robots.txt 생성을 시작합니다...")

today_str = datetime.now().strftime("%Y-%m-%d")
sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

for page in ["", "/log.html"]:
    sitemap_xml += '  <url>\n'
    sitemap_xml += f'    <loc>{BASE_URL}{page}</loc>\n'
    sitemap_xml += f'    <lastmod>{today_str}</lastmod>\n'
    sitemap_xml += '    <changefreq>daily</changefreq>\n'
    sitemap_xml += '    <priority>1.0</priority>\n'
    sitemap_xml += '  </url>\n'

for p in posts:
    lastmod = today_str
    if p['timestamp'] and len(p['timestamp']) == 8 and p['timestamp'] != "00000000":
        lastmod = f"{p['timestamp'][:4]}-{p['timestamp'][4:6]}-{p['timestamp'][6:]}"
        
    sitemap_xml += '  <url>\n'
    sitemap_xml += f'    <loc>{BASE_URL}{p["link"]}</loc>\n'
    sitemap_xml += f'    <lastmod>{lastmod}</lastmod>\n'
    sitemap_xml += '    <changefreq>weekly</changefreq>\n'
    sitemap_xml += '    <priority>0.8</priority>\n'
    sitemap_xml += '  </url>\n'

sitemap_xml += '</urlset>'

with open("sitemap.xml", 'w', encoding='utf-8') as f:
    f.write(sitemap_xml)

# ==========================================
# 🌟 2. 검색 엔진 크롤링 허용을 위한 robots.txt 생성
# ==========================================
robots_txt = f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n"
with open("robots.txt", 'w', encoding='utf-8') as f:
    f.write(robots_txt)

print("✅ sitemap.xml 및 robots.txt 생성 완료!")
print("✅ HTML 태그 이스케이프 깨짐 방지 및 흑백 필터 제거 완료!")