import os
import csv
import re

md_dir = "brunch_web_assets/markdown"
csv_file = "브런치_글_모음집.csv"

# 앞의 숫자(예: 009_)를 제거하고 순수 글자만 남기는 마법의 함수
def clean_and_pure(text):
    # 1단계: 맨 앞의 숫자, 마침표, 언더바 제거
    no_prefix = re.sub(r'^[\d#\._\s]+', '', text)
    # 2단계: 띄어쓰기 및 특수문자 제거 (순수 한글/영문/숫자만 남김)
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', no_prefix)

categories = {}

# 1. CSV 파일에서 제목(순수 글자)과 카테고리 외우기
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f: 
        reader = csv.reader(f)
        header = next(reader)
        title_idx, cat_idx = 1, 0  
        for row in reader:
            if len(row) > max(title_idx, cat_idx):
                pure_title = clean_and_pure(row[title_idx])
                categories[pure_title] = row[cat_idx].strip()
except Exception as e:
    print("❌ CSV 파일 읽기 오류:", e)
    exit()

count = 0

# 2. 미분류 파일 찾아서 정확한 카테고리 꽂아넣기
for filename in os.listdir(md_dir):
    if not filename.endswith(".md") or filename == "index.md":
        continue

    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # '미분류'라는 단어가 포함된 파일만 색출!
    if "미분류" in content:
        title = filename.replace(".md", "")
        pure_filename = clean_and_pure(title)
        
        # 찰떡 매칭 시도
        if pure_filename in categories:
            real_category = categories[pure_filename]
            
            # 머리말의 미분류 교체
            new_content = content.replace("category: '미분류'", f"category: '{real_category}'")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            count += 1
            print(f"✔️ 복구 완료: {title} -> {real_category}")

print(f"✅ 총 {count}개의 '미분류' 글이 정확한 카테고리를 찾았습니다!")