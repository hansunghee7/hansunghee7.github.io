import os
import shutil

OLD_ASSETS = "brunch_web_assets"
NEW_ASSETS = "log_assets"

# 1. 안전 복사 (Permission Denied 방지)
if os.path.exists(OLD_ASSETS) and not os.path.exists(NEW_ASSETS):
    print(f"📦 {OLD_ASSETS} -> {NEW_ASSETS} 안전 복사를 시작합니다...")
    try:
        shutil.copytree(OLD_ASSETS, NEW_ASSETS)
        print(f"✅ {NEW_ASSETS} 폴더 복사 완료!")
    except Exception as e:
        print(f"❌ 복사 중 에러: {e}")

# 2. 파일 내부 경로명 일괄 교체
print("\n🚀 파일 내 경로명 일괄 교체 작업을 시작합니다...")
target_extensions = ('.py', '.html', '.md', '.json', '.css')
updated_files_count = 0

for root, dirs, files in os.walk("."):
    if '.git' in root or 'venv' in root:
        continue
    
    for file in files:
        if file.endswith(target_extensions):
            filepath = os.path.join(root, file)
            if file == "rename_brunch.py":
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if OLD_ASSETS in content or "brunch_articles_text" in content:
                    new_content = content.replace(OLD_ASSETS, NEW_ASSETS)
                    new_content = new_content.replace("brunch_articles_text", "log_articles_text")
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    updated_files_count += 1
            except Exception:
                pass

print(f"🎉 파일 내 경로명 교체 완료 ({updated_files_count}개 파일)!")