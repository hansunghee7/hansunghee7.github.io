import os
import csv
import urllib.parse
import re

md_dir = "brunch_web_assets/markdown"
img_dir = "brunch_web_assets/images"
csv_file = "브런치_글_모음집.csv"

def clean_title(text):
    # 짝짓기(매칭)를 위해 제목 앞의 숫자나 기호(#, ., _) 등을 임시로 걸러내는 함수
    return re.sub(r'^[\d#\._\s]+', '', text).strip()

# 1. CSV 파일에서 카테고리 정보 싹 다 외우기
categories = {}
try:
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        # 0번째가 카테고리, 1번째가 제목!
        title_idx, cat_idx = 1, 0  
            
        for row in reader:
            if len(row) > max(title_idx, cat_idx):
                clean_csv_title = clean_title(row[title_idx])
                categories[clean_csv_title] = row[cat_idx].strip()
except FileNotFoundError:
    print(f"❌ {csv_file} 파일을 찾을 수 없습니다. 파이썬 파일과 같은 폴더에 있는지 확인해주세요!")
    exit()
except UnicodeDecodeError:
    # 혹시 한글 인코딩 문제가 생길 경우를 대비한 보험
    with open(csv_file, 'r', encoding='euc-kr') as f:
        reader = csv.reader(f)
        header = next(reader)
        title_idx, cat_idx = 1, 0  
        for row in reader:
            if len(row) > max(title_idx, cat_idx):
                clean_csv_title = clean_title(row[title_idx])
                categories[clean_csv_title] = row[cat_idx].strip()

count = 0

# 2. 마크다운 파일 열어서 카테고리와 사진 꽂아넣기
for filename in os.listdir(md_dir):
    if not filename.endswith(".md") or filename == "index.md":
        continue

    # 파일 이름에서 순수 제목 추출
    title = filename.replace(".md", "")
    clean_file_title = clean_title(title)
    
    # 아까 외워둔 카테고리에서 짝꿍 찾기 (못 찾으면 미분류)
    category = categories.get(clean_file_title, "미분류")

    # 커버 이미지 파일명 찾기
    cover_img_name = f"{title}_cover.jpg"
    cover_img_path = os.path.join(img_dir, cover_img_name)
    
    img_markdown = ""
    # 커버 이미지가 폴더에 실제로 있으면 마크다운용 이미지 코드 생성!
    if os.path.exists(cover_img_path):
        safe_img_name = urllib.parse.quote(cover_img_name)
        img_markdown = f"![대표 이미지](/brunch_web_assets/images/{safe_img_name})\n\n"

    # 기존 글 내용 읽어오기
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 낡은 머리말 떼어내고 순수 본문만 남기기
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
    if body.startswith("# 📝"):
        body = body.split("\n", 1)[1].strip()

    # 3. 조립: 머리말(카테고리) + 큼직한 제목 + 커버 이미지 + 텍스트 본문
    new_content = f"---\nlayout: default\ntitle: '{title}'\ncategory: '{category}'\n---\n\n# 📝 {title}\n\n{img_markdown}{body}"

    # 파일에 확정 지어 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    count += 1

print(f"✅ 총 {count}개 파일에 카테고리 매칭과 대표 이미지(커버) 삽입을 완벽하게 끝냈습니다!")