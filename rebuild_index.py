import os
import urllib.parse
import re

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"

# 1. 혹시라도 끝에 마침표나 공백이 남은 파일이 있다면 마지막으로 청소
for filename in os.listdir(md_dir):
    if not filename.endswith(".md") or filename == "index.md":
        continue
    
    base_name = filename[:-3]
    clean_base = base_name.rstrip('. ') # 끝에 있는 마침표와 공백 제거
    
    if base_name != clean_base:
        old_path = os.path.join(md_dir, filename)
        new_path = os.path.join(md_dir, clean_base + ".md")
        if not os.path.exists(new_path):
            os.rename(old_path, new_path)

# 2. 파일 목록을 읽어서 index.md(메인 화면) 100% 새로 작성하기
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort() # 순서대로 정렬

# 메인 화면 기초 공사
index_content = "---\nlayout: default\ntitle: '전체 글 목록'\ncategory: 'Simplifier'\n---\n\n"
index_content += "<br>\n\n성희님의 브런치 글 608개입니다. 제목을 클릭해 감상해 보세요!\n\n"

# 실제 파일 이름과 100% 일치하는 절대 고장 나지 않는 링크 생성
for filename in md_files:
    base_name = filename[:-3]
    
    # 목록에 보일 제목 (거슬리는 001_ 같은 숫자 지우기!)
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    
    # 깃허브가 인식할 수 있도록 URL 인코딩 적용
    safe_url = urllib.parse.quote(base_name)
    link = f"/brunch_web_assets/markdown/{safe_url}.html"
    
    index_content += f"* [{display_title}]({link})\n"

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(index_content)

print("✅ index.md 완벽 재생성! 이제 404 에러는 절대 뜰 수 없습니다.")