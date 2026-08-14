import os
import urllib.parse
import re
import shutil

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"

print("🔍 1단계: 마침표가 들어간 불량 파일명 색출 및 강제 변경 시작...")

renamed_count = 0
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]

for filename in md_files:
    base_name = filename[:-3] # .md 제외한 순수 이름
    
    # 정규식 방어 코드: 이름 끝에 있는 띄어쓰기, 마침표(.), 쉼표(,) 등을 모조리 날려버립니다.
    clean_base = re.sub(r'[\.\s,]+$', '', base_name) 
    
    if base_name != clean_base:
        old_path = os.path.join(md_dir, filename)
        new_path = os.path.join(md_dir, clean_base + ".md")
        
        # 윈도우와 Git의 착각을 막기 위한 방어 로직:
        # 1. 임시 이름으로 먼저 바꾼다.
        temp_path = os.path.join(md_dir, clean_base + "_TEMP.md")
        os.rename(old_path, temp_path)
        # 2. 다시 깔끔한 진짜 이름으로 바꾼다. (이렇게 해야 시스템이 확실히 인식함)
        os.rename(temp_path, new_path)
        
        renamed_count += 1
        print(f"✔️ 파일명 강제 정화 완료: {filename} -> {clean_base}.md")

print("\n🔍 2단계: 정화된 파일들을 바탕으로 index.md(전체 글 목록) 완벽 재구축...")

# 정화된 파일 목록을 디렉토리에서 다시 읽어옵니다.
final_md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
final_md_files.sort()

index_content = "---\nlayout: default\ntitle: '전체 글 목록'\ncategory: 'Simplifier'\n---\n\n"
index_content += "<br>\n\n성희님의 브런치 글 608개입니다. 제목을 클릭해 감상해 보세요!\n\n"

for filename in final_md_files:
    base_name = filename[:-3]
    
    # 목록에 표시될 제목: 앞의 숫자(예: 006_) 삭제
    display_title = re.sub(r'^[\d#\._\s]+', '', base_name)
    
    # 깃허브가 100% 인식하는 안전한 URL로 변환
    safe_url = urllib.parse.quote(base_name)
    link = f"/brunch_web_assets/markdown/{safe_url}.html"
    
    index_content += f"* [{display_title}]({link})\n"

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(index_content)

print(f"\n✅ 작전 성공! 총 {renamed_count}개의 찌꺼기 파일명을 고치고 index.md를 새로 썼습니다.")