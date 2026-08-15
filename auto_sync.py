import os
import re
import urllib.request
import urllib.parse
import csv
import time

md_dir = "brunch_web_assets/markdown"
img_dir = "brunch_web_assets/images"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

# 이미지 폴더가 없으면 생성
if not os.path.exists(img_dir):
    os.makedirs(img_dir)

# 카카오 서버가 로봇(파이썬)의 다운로드를 차단하지 못하게 일반 브라우저처럼 위장
opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
urllib.request.install_opener(opener)

def pure_text(text):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

# 1. 엑셀 데이터 매칭 준비
csv_data = {}
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 5:
                csv_data[pure_text(row[1])] = {
                    'category': clean_category_name(row[0]),
                    'date': row[2].strip(),
                    'cdn_url': row[4].strip()
                }
except Exception as e:
    print("CSV 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()
post_count = len(md_files)

cards_html = ""
unique_categories = set()

print("🚀 썸네일 고유번호(UID) 표준화 및 자동 다운로드 시작...\n")

for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    
    # 2. 마크다운 파일명에서 고유번호(001)와 실제 제목 분리
    parts = filename.split('_', 1)
    uid = parts[0] if len(parts) > 1 and parts[0].isdigit() else "000"
    base_title = parts[1][:-3] if len(parts) > 1 else filename[:-3]
    
    title_pure = pure_text(base_title)
    match_info = csv_data.get(title_pure)
    
    # 3. 새로운 로컬 이미지 경로 지정 (예: /brunch_web_assets/images/001.jpg)
    local_img_filename = f"{uid}.jpg"
    local_img_path = os.path.join(img_dir, local_img_filename)
    web_img_path = f"/brunch_web_assets/images/{local_img_filename}"
    
    category = "기타"
    date_str = ""
    
    # 4. 엑셀에서 원본 URL을 찾아 다운로드 (이미 있으면 패스)
    if match_info:
        category = match_info['category']
        date_str = match_info['date']
        cdn_url = match_info['cdn_url']
        
        if cdn_url.startswith('http') and not os.path.exists(local_img_path):
            try:
                urllib.request.urlretrieve(cdn_url, local_img_path)
                print(f"📥 다운로드 완료: {local_img_filename} ({base_title[:15]}...)")
                time.sleep(0.05) # 서버 과부하 방지
            except Exception as e:
                print(f"❌ 다운로드 실패 ({local_img_filename}): {e}")
                web_img_path = "/brunch_web_assets/images/logo_white.png"
    
    # 파일이 존재하지 않고 다운로드도 안 됐을 경우 기본 로고 처리
    if not os.path.exists(local_img_path):
        web_img_path = "/brunch_web_assets/images/logo_white.png"

    if category != "미분류" and category != "기타":
        unique_categories.add(category)

    # 5. 마크다운 머리말 갱신 (새로운 고유번호 사진 링크 적용)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    body_match = re.search(r'^---.*?---\s*(.*)', content, flags=re.DOTALL)
    body_content = body_match.group(1) if body_match else content
        
    safe_title = base_title.replace('"', '\\"')
    new_yaml = f"---\nlayout: default\ntitle: \"{safe_title}\"\ncategory: '{category}'\ncover_image: '{web_img_path}'\n---\n\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_yaml + body_content)

    # 6. index.md용 카드 HTML 작성
    safe_url = urllib.parse.quote(filename[:-3])
    link = f"/brunch_web_assets/markdown/{safe_url}.html"

    cards_html += f"""    <a href="{link}" class="card-item" data-category="{category}">
        <div class="card-thumb" style="background-image: url('{web_img_path}');"></div>
        <div class="card-content">
            <div>
                <div class="card-category">{category}</div>
                <h3 class="card-title">{base_title}</h3>
            </div>
            <div class="card-date">{date_str}</div>
        </div>
    </a>\n"""

# 7. index.md 생성 (최종 조립)
html_header = f"---\nlayout: default\ntitle: '심플리파이어의 {post_count}개의 글'\nis_index: true\n---\n"
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

html_body += f"""</div>\n<div class="card-grid" id="cardGrid">\n{cards_html}</div>\n<div id="scrollSentinel"></div>
<script>
    document.addEventListener('DOMContentLoaded', function() {{
        const cards = Array.from(document.querySelectorAll('.card-item'));
        const filterBtns = document.querySelectorAll('.cat-btn');
        const sentinel = document.getElementById('scrollSentinel');
        let itemsPerBatch = 20, currentVisibleCount = 0, filteredCards = cards;
        
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
            cards.forEach(card => {{ card.classList.remove('visible'); card.style.animationDelay = '0s'; }});
            filteredCards = filter === 'all' ? cards : cards.filter(card => card.getAttribute('data-category') === filter);
            currentVisibleCount = 0;
            loadNextBatch();
        }}
        const observer = new IntersectionObserver(entries => {{
            entries.forEach(entry => {{ if (entry.isIntersecting) loadNextBatch(); }});
        }}, {{ rootMargin: '200px' }});
        if (sentinel) observer.observe(sentinel);
        filterBtns.forEach(btn => {{
            btn.addEventListener('click', function() {{
                filterBtns.forEach(b => b.classList.remove('active')); this.classList.add('active');
                applyFilter(this.getAttribute('data-filter'));
            }});
        }});
        applyFilter('all');
    }});
</script>
"""

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html_header + html_body)

print("\n✅ 모든 썸네일 다운로드 및 고유번호(UID) 매칭이 완벽하게 끝났습니다!")
print("💡 앞으로 썸네일을 교체하고 싶으시면, images 폴더에 '001.jpg' 형식으로 이름만 바꿔서 넣으시면 끝입니다!")