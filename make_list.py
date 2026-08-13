import os
import urllib.parse

md_dir = "brunch_web_assets/markdown"
# 마크다운 파일만 모아서 정렬 (index.md는 제외)
files = sorted([f for f in os.listdir(md_dir) if f.endswith('.md') and f != 'index.md'])

# markdown 폴더 안에 목차 파일(index.md) 생성
index_path = os.path.join(md_dir, "index.md")
with open(index_path, 'w', encoding='utf-8') as f:
    f.write("# 📂 전체 글 목록\n\n")
    f.write("코치님의 브런치 글 608개입니다. 제목을 클릭해 감상해 보세요!\n\n")
    
    for filename in files:
        title = filename.replace('.md', '')
        # 깃허브에서 한글/띄어쓰기 링크가 깨지지 않도록 안전하게 변환
        safe_link = urllib.parse.quote(filename)
        f.write(f"* [{title}](./{safe_link})\n")

print(f"✅ 총 {len(files)}개의 글 목차가 성공적으로 생성되었습니다!")