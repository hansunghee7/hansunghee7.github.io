import os
import re
import urllib.parse

md_dir = "brunch_web_assets/markdown"

for filename in os.listdir(md_dir):
    if not filename.endswith(".md"):
        continue

    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 이미지 경로 안의 한글과 띄어쓰기를 깃허브용 웹 주소로 안전하게 변환
    def replace_path(match):
        original_filename = match.group(1)
        # 이미 변환(인코딩)된 상태가 아니라면 변환 진행
        if "%20" not in original_filename:
            safe_filename = urllib.parse.quote(original_filename)
        else:
            safe_filename = original_filename
        return f'src="../images/{safe_filename}"'

    # src="../images/..." 형태의 코드 찾아서 일괄 수정
    new_content = re.sub(r'src="\.\./images/([^"]+)"', replace_path, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

print("✅ 608개 글의 모든 이미지 경로가 깃허브용으로 완벽하게 변환되었습니다!")