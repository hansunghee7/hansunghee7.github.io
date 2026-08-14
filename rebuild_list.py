import os
import csv
import urllib.parse
import re

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"
csv_file = "브런치_글_모음집.csv"

# 순수 알맹이(글자)만 추출하는 함수
def clean_and_pure(text):
    no_prefix = re.sub(r'^[\d#\._\s]+', '', text)
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', no_prefix)

# 1. 스프레드시트에서 카테고리 정보 외우기
categories = {}
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) > 1:
                pure_title = clean_and_pure(row[1])
                categories[pure_title] = row[0].strip()
except Exception as e:
    print("❌ CSV 파일 읽기 오류:", e)

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

index_content = "---\nlayout: default\ntitle: '전체 글 목록'\ncategory: 'Simplifier'\n---\n\n"
index_content += "<br>\n\n성희님의 브런치 글 608개입니다. 제목을 클릭해 감상해 보세요!\n\n"

# 2. 카테고리가 포함된 리스트 작성하기
for filename in md_files:
    base_name = filename[:-3]
    
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    pure_title = clean_and_pure(base_name)
    
    # 짝꿍 카테고리 찾기 (없으면 미분류)
    category = categories.get(pure_title, "미분류")
    
    safe_url = urllib.parse.quote(base_name)
    link = f"/brunch_web_assets/markdown/{safe_url}.html"
    
    # 아까 default.html에 만들어둔 'list-category' 디자인 클래스 적용
    index_content += f"* <span class='list-category'>{category}</span>[{display_title}]({link})\n"

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(index_content)

print("✅ 카테고리가 포함된 메인 목록이 완벽하게 생성되었습니다!")