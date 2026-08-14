import os
import re

md_dir = "brunch_web_assets/markdown"
count = 0

for filename in os.listdir(md_dir):
    if not filename.endswith(".md") or filename == "index.md":
        continue

    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 머리말에서 카테고리 이름 빼오기
    match = re.search(r"category:\s*'(.*?)'", content)
    if match:
        category_name = match.group(1)
        
        # 2. 이미 카테고리를 넣은 파일이 아니라면, 글 제목 바로 밑에 예쁘게 추가하기
        category_text = f"📂 **{category_name}**"
        if category_text not in content:
            # '# 📝 제목' 부분을 찾아서 그 밑에 카테고리를 달아줍니다.
            new_content = re.sub(r"(# 📝 .*?\n)", f"\\1\n{category_text}\n\n", content, count=1)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1

print(f"✅ 총 {count}개 파일의 본문에 카테고리 텍스트를 강제 노출시켰습니다!")