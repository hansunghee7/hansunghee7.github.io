import os
import re
import urllib.parse

md_dir = "brunch_web_assets/markdown"
count = 0

for filename in os.listdir(md_dir):
    if not filename.endswith(".md"):
        continue

    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 마크다운(![...](...))이든 HTML(<img src="...">)이든 가리지 않고 다 잡는 함수
    def replace_path(match):
        prefix = match.group(1) # "../images/" 부분
        original_filename = match.group(2) # 파일 이름 부분
        
        if "%20" not in original_filename:
            safe_filename = urllib.parse.quote(original_filename)
        else:
            safe_filename = original_filename
            
        return f'{prefix}{safe_filename}'

    # images/ 뒤에 오는 파일 이름을 괄호나 따옴표가 나오기 전까지 추출
    new_content = re.sub(r'((?:\.\./)?images/)([^")]+)', replace_path, content)

    # 내용이 진짜로 바뀌었을 때만 파일 덮어쓰기 및 카운트
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        count += 1

print(f"✅ 총 {count}개의 마크다운 파일에서 이미지 경로 변환을 완료했습니다!")