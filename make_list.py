import os
import urllib.parse

md_dir = "brunch_web_assets/markdown"
files = sorted([f for f in os.listdir(md_dir) if f.endswith('.md') and f != 'index.md'])

index_path = os.path.join(md_dir, "index.md")
with open(index_path, 'w', encoding='utf-8') as f:
    f.write("# 📂 전체 글 목록\n\n")
    f.write("코치님의 브런치 글 608개입니다. 제목을 클릭해 감상해 보세요!\n\n")
    
    f.write("<ul>\n")
    for filename in files:
        title = filename.replace('.md', '')
        # 핵심 변경: 링크 주소를 .md가 아닌 .html로 연결해 줍니다!
        html_filename = filename.replace('.md', '.html')
        safe_link = urllib.parse.quote(html_filename)
        
        f.write(f"  <li style='margin-bottom: 5px;'><a href='./{safe_link}'>{title}</a></li>\n")
    f.write("</ul>\n")

print(f"✅ 총 {len(files)}개의 글 목차가 .html 연결 방식으로 수정되었습니다!")