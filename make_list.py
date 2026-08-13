import os
import urllib.parse

md_dir = "brunch_web_assets/markdown"
# 마크다운 파일만 모아서 정렬 (index.md는 제외)
files = sorted([f for f in os.listdir(md_dir) if f.endswith('.md') and f != 'index.md'])

index_path = os.path.join(md_dir, "index.md")
with open(index_path, 'w', encoding='utf-8') as f:
    f.write("# 📂 전체 글 목록\n\n")
    f.write("코치님의 브런치 글 608개입니다. 제목을 클릭해 감상해 보세요!\n\n")
    
    # 마크다운 오작동 방지를 위해 안전한 HTML 리스트(<ul>, <li>, <a>) 사용
    f.write("<ul>\n")
    for filename in files:
        title = filename.replace('.md', '')
        safe_link = urllib.parse.quote(filename)
        f.write(f"  <li style='margin-bottom: 5px;'><a href='./{safe_link}'>{title}</a></li>\n")
    f.write("</ul>\n")

print(f"✅ 총 {len(files)}개의 글 목차가 HTML 방식으로 안전하게 생성되었습니다!")