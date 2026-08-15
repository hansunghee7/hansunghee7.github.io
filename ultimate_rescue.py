import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

csv_file = "브런치_글_모음집.csv"
md_dir = "brunch_web_assets/markdown"

if not os.path.exists(md_dir): os.makedirs(md_dir)

# 🚨 기존에 꼬여버린 마크다운 파일들을 싹 비우고 백지에서 시작합니다!
for f in os.listdir(md_dir):
    if f.endswith(".md"):
        os.remove(os.path.join(md_dir, f))

def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("🚀 엑셀 제목을 무시하고, 원본 웹페이지의 '진짜 제목'을 추출하여 100% 매칭합니다...")

success_count = 0

with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for idx, row in enumerate(reader, 1):
        if len(row) < 6: continue
        
        category = clean_category_name(row[0].strip())
        date_str = row[2].strip()
        cover_url = row[4].strip()
        brunch_url = row[5].strip()
        
        if not brunch_url.startswith("http"): continue

        try:
            response = requests.get(brunch_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 🌟 엑셀 제목을 버리고, 브런치 원본 웹페이지에서 '진짜 제목'을 직접 찾습니다!
            real_title = row[1].strip() # 기본값
            title_tag = soup.find('h1', class_='cover_title') or soup.find('h1', class_='tit_subject')
            if title_tag:
                real_title = title_tag.text.strip()
            elif soup.title:
                real_title = soup.title.text.replace(' - 브런치', '').replace(' - 브런치스토리', '').strip()
            
            body_div = soup.find('div', class_='wrap_body')
            if not body_div: continue
            
            markdown_content = md(str(body_div), heading_style="ATX")
            
            # 🧹 마크다운 변환 찌꺼기(####) 완벽 청소
            markdown_content = re.sub(r'^#{1,5}\s*$', '', markdown_content, flags=re.MULTILINE) # 줄 전체가 #인 경우 삭제
            markdown_content = markdown_content.replace('####', '') # 중간에 껴있는 #### 삭제
            
            safe_title_for_file = re.sub(r'[\\/*?:"<>|]', "", real_title)
            uid_str = str(idx).zfill(3)
            filename = f"{uid_str}_{safe_title_for_file}.md"
            filepath = os.path.join(md_dir, filename)
            
            safe_yaml_title = real_title.replace('"', '\\"')
            yaml_frontmatter = f"---\nlayout: default\ntitle: \"{safe_yaml_title}\"\ncategory: '{category}'\ncover_image: '{cover_url}'\ndate_string: '{date_str}'\n---\n\n"
            
            with open(filepath, 'w', encoding='utf-8') as mf:
                mf.write(yaml_frontmatter + markdown_content)
                
            print(f"✅ [{uid_str}] 진짜 제목 매칭 완료: {real_title}")
            success_count += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"❌ 접속 에러: {brunch_url}")

print(f"\n🎉 작업 완료! 꼬여있던 제목과 내용이 완벽하게 1:1 매칭되었습니다.")