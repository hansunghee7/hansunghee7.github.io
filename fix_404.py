import os
import urllib.parse

md_dir = "brunch_web_assets/markdown"
index_file = "index.md"

count = 0
renamed_files = []

# 1. 파일 이름 끝에 있는 마침표(.) 또는 공백 제거하기
for filename in os.listdir(md_dir):
    if not filename.endswith(".md") or filename == "index.md":
        continue

    # 파일 이름에서 .md 앞부분(순수 제목) 추출
    base_name = filename[:-3]
    
    # 이름 끝에 마침표나 공백이 있다면 깔끔하게 잘라내기
    if base_name.endswith('.') or base_name.endswith(' '):
        clean_base = base_name.rstrip('. ')
        new_filename = clean_base + ".md"
        
        old_path = os.path.join(md_dir, filename)
        new_path = os.path.join(md_dir, new_filename)
        
        # 파일 이름 실제 변경
        os.rename(old_path, new_path)
        renamed_files.append((filename, new_filename))
        count += 1
        print(f"✔️ 이름 수정됨: {filename} -> {new_filename}")

# 2. index.md (메인 화면)의 깨진 링크들을 새 이름으로 업데이트하기
if os.path.exists(index_file) and renamed_files:
    with open(index_file, 'r', encoding='utf-8') as f:
        index_content = f.read()
        
    for old_file, new_file in renamed_files:
        # .html 로 연결된 링크, .md 로 연결된 링크 모두 찾아서 교체
        old_html = old_file.replace(".md", ".html")
        new_html = new_file.replace(".md", ".html")
        
        index_content = index_content.replace(old_html, new_html)
        index_content = index_content.replace(old_file, new_file)
        
        # URL 인코딩(%20 등)된 링크도 놓치지 않고 교체
        index_content = index_content.replace(urllib.parse.quote(old_html), urllib.parse.quote(new_html))
        index_content = index_content.replace(urllib.parse.quote(old_file), urllib.parse.quote(new_file))

    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_content)
    print("\n✅ index.md 파일 내의 깨진 링크도 모두 새로운 주소로 수정 완료했습니다!")

if count == 0:
    print("💡 수정할 파일이 없습니다. 이미 파일 이름들이 깔끔합니다!")