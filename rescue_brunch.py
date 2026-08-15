import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

csv_file = "브런치_글_모음집.csv"
md_dir = "brunch_web_assets/markdown"

# 폴더가 없으면 생성
if not os.path.exists(md_dir):
    os.makedirs(md_dir)

def pure_text(text):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

def clean_category_name(cat_str):
    if not cat_str: return "기타"
    cleaned = re.sub(r'^(매거진|브런치북)\s*:\s*', '', cat_str.strip())
    return cleaned if cleaned else "기타"

print("🚀 브런치 원본 100% 정확도 재수집을 시작합니다...\n")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
error_count = 0

try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        # 엑셀의 행(Row) 단위로 하나씩 처리하므로 절대 꼬이지 않습니다!
        for idx, row in enumerate(reader, 1):
            if len(row) < 6: continue
            
            raw_category = row[0].strip()
            category = clean_category_name(raw_category)
            title = row[1].strip()
            date_str = row[2].strip()
            cover_url = row[4].strip()
            brunch_url = row[5].strip()
            
            if not brunch_url.startswith("http"):
                continue

            # 파일명 생성 (앞에 001_ 번호 붙이기)
            safe_title_for_file = re.sub(r'[\\/*?:"<>|]', "", title) # 윈도우 파일명 불가 문자 제거
            uid_str = str(idx).zfill(3)
            filename = f"{uid_str}_{safe_title_for_file}.md"
            filepath = os.path.join(md_dir, filename)

            try:
                # 1. 브런치 원본 URL 접속
                response = requests.get(brunch_url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 2. 본문 영역(wrap_body) 추출
                body_div = soup.find('div', class_='wrap_body')
                if not body_div:
                    print(f"⚠️ 본문 찾기 실패: {title} ({brunch_url})")
                    error_count += 1
                    continue
                
                # 3. HTML을 마크다운으로 깔끔하게 변환
                markdown_content = md(str(body_div), heading_style="ATX")
                
                # 4. 머리말(YAML) 작성
                safe_yaml_title = title.replace('"', '\\"')
                yaml_frontmatter = f"---\nlayout: default\ntitle: \"{safe_yaml_title}\"\ncategory: '{category}'\ncover_image: '{cover_url}'\ndate_string: '{date_str}'\n---\n\n"
                
                # 5. 파일 저장
                with open(filepath, 'w', encoding='utf-8') as mf:
                    mf.write(yaml_frontmatter + markdown_content)
                
                print(f"✅ [{uid_str}] 복구 완료: {title}")
                success_count += 1
                time.sleep(0.5) # 카카오 서버 차단 방지를 위해 0.5초 대기
                
            except Exception as e:
                print(f"❌ 접속 에러 [{title}]: {e}")
                error_count += 1

except Exception as e:
    print(f"CSV 읽기 치명적 오류: {e}")

print(f"\n🎉 작업 완료! 성공: {success_count}건 / 실패: {error_count}건")
print("이제 index.md를 갱신하기 위해 'py build_card_index.py' (또는 'py sync_all.py')를 한 번만 더 실행해 주세요!")