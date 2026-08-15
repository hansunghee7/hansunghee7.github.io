import os

md_dir = "brunch_web_assets/markdown"
count = 0

print("🚀 파일 이름에서 마침표(.) 등 위험한 기호를 청소합니다...")

for filename in os.listdir(md_dir):
    if filename.endswith(".md"):
        base_name = filename[:-3] # 뒤의 .md 떼어내기
        
        # 파일 이름에서 마침표(.), 물음표(?), 느낌표(!) 싹 지우기
        clean_name = base_name.replace(".", "").replace("?", "").replace("!", "").strip()
        
        # 이름이 달라졌다면(즉, 기호가 있었다면) 파일명 변경 실행
        if base_name != clean_name:
            old_path = os.path.join(md_dir, filename)
            new_path = os.path.join(md_dir, f"{clean_name}.md")
            
            os.rename(old_path, new_path)
            print(f"🧹 이름 변경 완료: {filename} ➡️ {clean_name}.md")
            count += 1

print(f"\n✅ 총 {count}개의 위험한 파일명이 안전하게 청소되었습니다!")