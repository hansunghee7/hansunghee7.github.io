import os
import re
import urllib.parse

md_dir = "brunch_web_assets/markdown"
count = 0

for filename in os.listdir(md_dir):
    if not filename.endswith(".md") or filename == "index.md":
        continue

    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 꼬여있는 기존 머리말(Frontmatter) 제거하고 본문만 추출
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
    
    # 2. 본문 맨 위에 '제목' 강제 삽입 (파일 이름 활용)
    title = filename.replace(".md", "")
    if not body.startswith("# "):
        body = f"---\nlayout: default\ntitle: '{title}'\n---\n\n# 📝 {title}\n\n{body}"
    else:
        body = f"---\nlayout: default\ntitle: '{title}'\n---\n\n{body}"

    # 3. 마크다운 이미지 ![...](...) 절대 경로로 변환
    def replace_img(match):
        alt_text = match.group(1)
        img_path = match.group(2)
        
        # 파일 이름만 똑 떼어내기
        img_filename = img_path.split("/")[-1]
        
        # 안전한 주소로 변환
        if "%20" not in img_filename:
            safe_filename = urllib.parse.quote(img_filename)
        else:
            safe_filename = img_filename
            
        # 절대 경로로 고정!
        return f'![{alt_text}](/brunch_web_assets/images/{safe_filename})'

    new_body = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_img, body)

    # 4. HTML 이미지 <img src="..."> 절대 경로로 변환
    def replace_html_img(match):
        img_path = match.group(1)
        img_filename = img_path.split("/")[-1]
        
        if "%20" not in img_filename:
            safe_filename = urllib.parse.quote(img_filename)
        else:
            safe_filename = img_filename
            
        return f'src="/brunch_web_assets/images/{safe_filename}"'
        
    new_body = re.sub(r'src="([^"]+)"', replace_html_img, new_body)

    # 파일 덮어쓰기
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_body)
    count += 1

print(f"✅ 총 {count}개 파일의 제목 강제 삽입과 이미지 절대경로 복구를 완료했습니다!")