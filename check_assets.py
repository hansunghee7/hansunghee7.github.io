import os
import re
import urllib.parse

md_dir = "brunch_web_assets/markdown"
img_dir = "brunch_web_assets/images"

target_category = "심플한 창업하고 파이어하게 일하기"
print(f"\n🔍 '{target_category}' 카테고리 정밀 진단 시작...\n")

md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

count = 0
for filename in md_files:
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 타겟 카테고리가 포함된 글만 3개 뽑아서 확인
    if target_category in content:
        count += 1
        if count > 3: break 
        
        print(f"=====================================")
        print(f"📄 파일명(A): {filename}")
        
        # 1. 머리말(YAML) 제목 확인
        title_match = re.search(r"^title:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
        print(f"🏷️ 머리말 제목(B): {title_match.group(1) if title_match else '없음'}")
        
        # 2. 본문 내용 확인 (엉뚱한 글이 들어있는지 체크)
        body_text = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL) # 머리말 제거
        print(f"📝 실제 본문 첫 줄(C): {body_text.strip()[:60]}...")
        
        # 3. 이미지 존재 여부 확인
        img_match = re.search(r'!\[.*?\]\((.*?)\)', content)
        if not img_match:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
            
        if img_match:
            raw_url = img_match.group(1).strip()
            print(f"🖼️ 마크다운에 적힌 이미지 경로: {raw_url}")
            
            # 파일명만 추출하여 실제 폴더에 있는지 검사
            img_filename = raw_url.split('/')[-1]
            decoded_filename = urllib.parse.unquote(img_filename)
            
            actual_images = os.listdir(img_dir)
            if img_filename in actual_images or decoded_filename in actual_images:
                print(f"✅ 결과: 이미지 폴더에 파일이 [존재함]")
            else:
                print(f"❌ 결과: 이미지 폴더에 해당 파일이 [없음] (다운로드 누락 또는 이름 불일치)")
        else:
            print(f"🖼️ 결과: 본문에 이미지가 아예 없음")

print(f"=====================================\n진단 종료.")