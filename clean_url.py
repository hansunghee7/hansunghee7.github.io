import os
import re

md_dir = "brunch_web_assets/markdown"
count = 0

print("🚀 마크다운 파일 내 URL 찌꺼기 청소를 시작합니다...")

for filename in os.listdir(md_dir):
    if filename.endswith(".md"):
        filepath = os.path.join(md_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        
        # 1. 예스24 생짜 URL 완벽 삭제 (앞뒤 공백/줄바꿈 포함)
        content = re.sub(r'https://www\.yes24\.com/product/goods/193444437\s*', '', content)
        
        # 2. 혹시 남아있을 트레바리 URL도 삭제
        content = re.sub(r'https://trevar\.ink/[a-zA-Z0-9]+\s*', '', content)

        # 3. 잘못 저장된 예전 배너/카드 껍데기들 완벽 초기화
        content = re.sub(r'<!-- PROMO_BANNER_START -->.*?<!-- PROMO_BANNER_END -->\s*', '', content, flags=re.DOTALL)
        content = re.sub(r'<!-- OG_CARD_START -->.*?<!-- OG_CARD_END -->\s*', '', content, flags=re.DOTALL)

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            count += 1
            print(f"🧹 청소 완료: {filename}")

print(f"\n✅ 총 {count}개의 파일에서 URL 찌꺼기가 깔끔하게 제거되었습니다!")