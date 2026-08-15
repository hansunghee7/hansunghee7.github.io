import os
import re

md_dir = "brunch_web_assets/markdown"
count = 0

print("🧹 마크다운 딥 클리닝을 시작합니다...")

for filename in os.listdir(md_dir):
    if filename.endswith(".md"):
        filepath = os.path.join(md_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 1. 과거에 생성된 쓸데없는 HTML 껍데기들(주석 포함) 통째로 날리기
        content = re.sub(r'<!-- PROMO_BANNER_START -->.*?<!-- PROMO_BANNER_END -->\n*', '', content, flags=re.DOTALL)
        content = re.sub(r'<!-- OG_CARD_START -->.*?<!-- OG_CARD_END -->(?:</div>)?\n*', '', content, flags=re.DOTALL)
        content = re.sub(r'<!-- CATEGORY_NAV_START -->.*?<!-- CATEGORY_NAV_END -->\n*', '', content, flags=re.DOTALL)

        # 2. 이번에 스캔된 예스24 이미지 찌꺼기, 트레바리 주소 완벽 삭제
        content = re.sub(r'https://image\.yes24\.com/goods/\d+/xl\'?', '', content)
        content = re.sub(r'https://trevar\.ink/[a-zA-Z0-9]+', '', content)
        content = re.sub(r'https://www\.yes24\.com/product/goods/\d+', '', content)

        # 3. 2단계로 인한 빈 줄(연속된 엔터) 다이어트
        content = re.sub(r'\n{3,}', '\n\n', content)

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content.strip() + '\n')
            count += 1
            print(f"✨ 딥 클리닝 완료: {filename}")

print(f"\n✅ 총 {count}개의 파일에서 악성 찌꺼기를 완벽하게 제거했습니다!")