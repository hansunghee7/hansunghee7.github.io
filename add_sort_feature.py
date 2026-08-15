import os
import re
import urllib.parse
import csv

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

def pure_text(text): return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)
def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

# 영문 월을 숫자로 바꿔 실제 비교 가능한 타임스탬프로 변환하는 함수
def parse_date(date_str):
    months = {'Jan':'01', 'Feb':'02', 'Mar':'03', 'Apr':'04', 'May':'05', 'Jun':'06', 'Jul':'07', 'Aug':'08', 'Sep':'09', 'Oct':'10', 'Nov':'11', 'Dec':'12'}
    try:
        parts = date_str.replace('.', '').replace(',', '').split()
        if len(parts) >= 3:
            m = months.get(parts[0][:3], '00')
            d = parts[1].zfill(2)
            y = parts[2]
            return f"{y}{m}{d}" # 예: 20260812
    except: pass
    return "00000000"

csv_data = {}
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 5:
                csv_data[pure_text(row[1])] = { 'category': clean_category_name(row[0]), 'date': row[2].strip() }
except: pass

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()
post_count = len(md_files)

cards_html = ""
unique_categories = set()

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    parts = filename.split('_', 1)
    uid = int(parts[0]) if len(parts) > 1 and parts[0].isdigit() else 0
    base_title = parts[1][:-3] if len(parts) > 1 else filename[:-3]
    
    match_info = csv_data.get(pure_text(base_title))
    category, date_str = (match_info['category'], match_info['date']) if match_info else ("기타", "")
    
    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    # 썸네일 경로 추출 (auto_sync.py 가 만들어준 머리말 사용)
    img_url = "/brunch_web_assets/images/logo_white.png"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        img_match = re.search(r"cover_image:\s*['\"](.*?)['\"]", content)
        if img_match: img_url = img_match.group(1)

    timestamp = parse_date(date_str) # 예: 20260812
    safe_url = urllib.parse.quote(filename[:-3])
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    # HTML에 data-date와 data-id를 심어서 자바스크립트가 정렬할 수 있게 만듭니다.
    cards_html += f"""    <a href="{link}" class="card-item" data-category="{category}" data-date="{timestamp}" data-id="{uid}">
        <div class="card-thumb" style="background-image: url('{img_url}');"></div>
        <div class="card-content">
            <div>
                <div class="card-category">{category}</div>
                <h3 class="card-title">{base_title}</h3>
            </div>
            <div class="card-date">{date_str}</div>
        </div>
    </a>\n"""

html_header = f"---\nlayout: default\ntitle: '심플리파이어의 {post_count}개의 글'\nis_index: true\n---\n"

# 카테고리 필터와 정렬 드롭다운을 양옆으로 예쁘게 배치합니다.
html_body = """
<style>
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    .card-item.visible { display: flex !important; animation: fadeInUp 0.4s ease forwards; }
    #scrollSentinel { height: 50px; margin-top: 30px; }
    
    .filter-wrap { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 20px; margin-bottom: 10px; }
    .category-filter { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
    .cat-btn { padding: 7px 16px; border: 1px solid #e1e1e1; border-radius: 20px; background: #fff; color: #666; font-size: 13px; font-weight: 300; cursor: pointer; transition: all 0.2s; font-family: 'Noto Sans KR', sans-serif; }
    .cat-btn:hover { border-color: #00c73c; color: #00c73c; }
    .cat-btn.active { background: #00c73c; color: #fff; border-color: #00c73c; font-weight: 400; }
    
    .sort-select { padding: 7px 12px; border: 1px solid #ddd; border-radius: 6px; outline: none; font-family: 'Noto Sans KR'; font-size: 13px; color: #444; cursor: pointer; background: #fafafa; }
    .sort-select:hover { border-color: #00c73c; }
</style>

<div class="filter-wrap">
    <div class="category-filter">
        <button class="cat-btn active" data-filter="all">전체보기</button>
"""

for cat in sorted(list(unique_categories)):
    html_body += f'        <button class="cat-btn" data-filter="{cat}">{cat}</button>\n'

html_body += """    </div>
    <div class="sort-filter">
        <select id="sortSelect" class="sort-select">
            <option value="desc">최신순</option>
            <option value="asc">날짜순 (오래된순)</option>
        </select>
    </div>
</div>

<div class="card-grid" id="cardGrid">
""" + cards_html + """</div>
<div id="scrollSentinel"></div>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const sortSelect = document.getElementById('sortSelect');
        const sentinel = document.getElementById('scrollSentinel');
        const grid = document.getElementById('cardGrid');
        
        let itemsPerBatch = 20, currentVisibleCount = 0;
        let filteredCards = [...cards];
        let currentFilter = 'all';
        let sortMode = 'desc'; // 최신순 기본값
        
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
            
            // 1. 필터링
            filteredCards = currentFilter === 'all' ? [...cards] : cards.filter(card => card.getAttribute('data-category') === currentFilter);
            
            // 2. 정렬 (날짜 데이터 또는 고유 번호 활용)
            filteredCards.sort((a, b) => {
                let dateA = parseInt(a.getAttribute('data-date')) || 0;
                let dateB = parseInt(b.getAttribute('data-date')) || 0;
                
                if (dateA === dateB) { // 날짜가 같거나 없으면 파일명 번호로 정렬
                    let idA = parseInt(a.getAttribute('data-id')) || 0;
                    let idB = parseInt(b.getAttribute('data-id')) || 0;
                    return sortMode === 'desc' ? idB - idA : idA - idB;
                }
                return sortMode === 'desc' ? dateB - dateA : dateA - dateB;
            });
            
            // 3. 화면(DOM) 재배치
            filteredCards.forEach(card => grid.appendChild(card));
            
            currentVisibleCount = 0;
            loadNextBatch();
        }

        // 정렬 드롭다운 이벤트
        sortSelect.addEventListener('change', function() {
            sortMode = this.value;
            applyFilterAndSort();
        });

        // 카테고리 버튼 이벤트
        filterBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                filterBtns.forEach(b => b.classList.remove('active')); this.classList.add('active');
                currentFilter = this.getAttribute('data-filter');
                applyFilterAndSort();
            });
        });

        // 무한 스크롤 이벤트
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

print("✅ 정렬(최신순/날짜순) 기능이 추가된 index.md 파일 생성 완료!")
