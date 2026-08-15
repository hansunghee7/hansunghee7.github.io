import os
import re

md_dir = "brunch_web_assets/markdown"

# 👇 여기서 바꾸고 싶은 기존 이름과 새 이름을 적어주세요!
OLD_CATEGORY = "스타트업의 전략들"   # 예: 현재 카테고리 이름
NEW_CATEGORY = "스타트업 인사이트"        # 예: 바꿀 카테고리 이름
count = 0
print(f"🚀 '{OLD_CATEGORY}' 카테고리를 '{NEW_CATEGORY}'(으)로 일괄 변경합니다...\n")

for filename in os.listdir(md_dir):
    if filename.endswith(".md"):
        filepath = os.path.join(md_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 정확히 이전 카테고리 이름과 일치하는 경우만 찾기
        pattern = rf"^category:\s*['\"]?{re.escape(OLD_CATEGORY)}['\"]?\s*$"
        if re.search(pattern, content, re.MULTILINE):
            # 새 카테고리 이름으로 교체
            new_content = re.sub(pattern, f"category: '{NEW_CATEGORY}'", content, flags=re.MULTILINE)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1
            print(f"🔄 변경 완료: {filename}")

print(f"\n✅ 총 {count}개의 글이 '{NEW_CATEGORY}'(으)로 일괄 변경되었습니다!")