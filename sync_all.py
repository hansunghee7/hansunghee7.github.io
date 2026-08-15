import os
import re
import urllib.parse
import csv

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

# 1. 날짜 데이터 매칭 (순수 텍스트 기준)
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
    print("CSV 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()
post_count = len(md_files)

cards_html = ""
unique_categories = set()

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 2. 마크다운 파일 내부 정보 직접 추출
    title_match = re.search(r"^title:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    cat_match = re.search(r"^category:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    cover_match = re.search(r"^cover_image:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
    
    title = title_match.group(1).strip() if title_match else filename[:-3]
    category = cat_match.group(1).strip() if cat_match else "기타"
    cover_image = cover_match.group(1).strip() if cover_match else "/brunch_web_assets/images/logo_white.png"

    # 날짜 주입 로직
    title_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', title)
    filename_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', filename[:-3])
    date_string = csv_dates.get(title_clean, csv_dates.get(filename_clean, ""))

    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    # 3. 개별 파일 머리말(YAML) 동기화 업데이트
    body_content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
    safe_title = title.replace('"', '\\"')
    
    new_yaml = f"---\nlayout: default\ntitle: \"{safe_title}\"\ncategory: '{category}'\ncover_image: '{cover_image}'\ndate_string: '{date_string}'\n---\n\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_yaml + body_content)

    # 4. 카드 HTML 조립
    safe_url = urllib.parse.quote(filename[:-3])
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    # 정렬을 위한 타임스탬프 계산
    months = {'Jan':'01', 'Feb':'02', 'Mar':'03', 'Apr':'04', 'May':'05', 'Jun':'06', 'Jul':'07', 'Aug':'08', 'Sep':'09', 'Oct':'10', 'Nov':'11', 'Dec':'12'}
    timestamp = "00000000"
    try:
        parts = date_string.replace('.', '').replace(',', '').split()
        if len(parts) >= 3:
            m = months.get(parts[0][:3], '00')
            d = parts[1].zfill(2)
            y = parts[2]
            timestamp = f"{y}{m}{d}"
    except: pass
    
    uid = 0
    uid_match = re.match(r'^(\d+)_', filename)
    if uid_match: uid = int(uid_match.group(1))

    cards_html += f"""    <a href="{link}" class="card-item" data-category="{category}" data-date="{timestamp}" data-id="{uid}">
        <div class="card-thumb" style="background-image: url('{cover_image}');"></div>
        <div class="card-content">
            <div>
                <div class="card-category">{category}</div>
                <h3 class="card-title">{title}</h3>
            </div>
            <div class="card-date">{date_string}</div>
        </div>
    </a>\n"""

# 5. index.md 생성 (★요청하신 텍스트 형태의 정렬 UI 적용★)
html_header = f"---\nlayout: default\ntitle: '심플리파이어의 {post_count}개의 글'\nis_index: true\n---\n"

html_body = """
<style>
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    .card-item.visible { display: flex !important; animation: fadeInUp 0.4s ease forwards; }
    #scrollSentinel { height: 50px; margin-top: 30px; }
    
    /* 필터 및 정렬 레이아웃 */
    .filter-wrap { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 20px; margin-bottom: 35px; }
    .category-filter { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
    .cat-btn { padding: 7px 16px; border: 1px solid #e1e1e1; border-radius: 20px; background: #fff; color: #666; font-size: 13px; font-weight: 300; cursor: pointer; transition: all 0.2s; font-family: 'Noto Sans KR', sans-serif; }
    .cat-btn:hover { border-color: #00c73c; color: #00c73c; }
    .cat-btn.active { background: #00c73c; color: #fff; border-color: #00c73c; font-weight: 400; }
    
    /* ★ 새로운 텍스트 토글 방식 정렬 UI 스타일 ★ */
    .sort-filter { display: flex; gap: 15px; align-items: center; margin-bottom: 5px; }
    .sort-text-btn { background: none; border: none; font-size: 14px; color: #a0a0a0; cursor: pointer; font-family: 'Noto Sans KR', sans-serif; font-weight: 300; display: flex; align-items: center; padding: 0; transition: color 0.2s; }
    .sort-text-btn:hover { color: #555; }
    .sort-text-btn.active { color: #333; font-weight: 400; }
    
    /* 액티브 시 나타나는 동그란 점 (Dot) */
    .sort-text-btn .dot { display: inline-block; width: 4px; height: 4px; border-radius: 50%; background-color: transparent; margin-right: 4px; margin-bottom: 2px; }
    .sort-text-btn.active .dot { background-color: #00c73c; } /* 브런치 시그니처 민트색 */
</style>

<div class="filter-wrap">
    <div class="category-filter">
        <button class="cat-btn active" data-filter="all">전체보기</button>
"""

for cat in sorted(list(unique_categories)):
    html_body += f'        <button class="cat-btn" data-filter="{cat}">{cat}</button>\n'

# 드롭다운 제거 후 텍스트 버튼으로 변경
html_body += """    </div>
    <div class="sort-filter">
        <button class="sort-text-btn active" data-sort="desc"><span class="dot"></span>최신순</button>
        <button class="sort-text-btn" data-sort="asc"><span class="dot"></span>날짜순</button>
    </div>
</div>

<div class="card-grid" id="cardGrid">\n""" + cards_html + """</div>
<div id="scrollSentinel"></div>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const sortBtns = document.querySelectorAll('.sort-text-btn'); // 텍스트 정렬 버튼 변수
        const sentinel = document.getElementById('scrollSentinel');
        const grid = document.getElementById('cardGrid');
        
        let itemsPerBatch = 20, currentVisibleCount = 0;
        let filteredCards = [...cards];
        let currentFilter = 'all';
        let sortMode = 'desc';
        
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
        
        function applyFilterAndSort() {
            cards.forEach(card => { card.classList.remove('visible'); card.style.animationDelay = '0s'; });
            
            filteredCards = currentFilter === 'all' ? [...cards] : cards.filter(card => card.getAttribute('data-category') === currentFilter);
            
            filteredCards.sort((a, b) => {
                let dateA = parseInt(a.getAttribute('data-date')) || 0;
                let dateB = parseInt(b.getAttribute('data-date')) || 0;
                
                if (dateA === dateB) { 
                    let idA = parseInt(a.getAttribute('data-id')) || 0;
                    let idB = parseInt(b.getAttribute('data-id')) || 0;
                    return sortMode === 'desc' ? idB - idA : idA - idB;
                }
                return sortMode === 'desc' ? dateB - dateA : dateA - dateB;
            });
            
            filteredCards.forEach(card => grid.appendChild(card));
            currentVisibleCount = 0;
            loadNextBatch();
        }

        // 정렬 텍스트 버튼 클릭 이벤트 연결
        sortBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                sortBtns.forEach(b => b.classList.remove('active')); 
                this.classList.add('active');
                sortMode = this.getAttribute('data-sort');
                applyFilterAndSort();
            });
        });

        filterBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                filterBtns.forEach(b => b.classList.remove('active')); this.classList.add('active');
                currentFilter = this.getAttribute('data-filter');
                applyFilterAndSort();
            });
        });

        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => { if (entry.isIntersecting) loadNextBatch(); });
        }, { rootMargin: '200px' });
        if (sentinel) observer.observe(sentinel);
        
        applyFilterAndSort();
    });
</script>
"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html_header + html_body)

print("✅ 정렬 기능 UI가 첨부하신 이미지 스타일(미니멀 텍스트 + 민트색 Dot)로 업데이트되었습니다.")