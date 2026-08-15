import os
import re

md_dir = "brunch_web_assets/markdown"
count = 0

print("🚀 깨진 홍보용 링크 일괄 청소를 시작합니다...")

for filename in os.listdir(md_dir):
    if filename.endswith(".md"):
        filepath = os.path.join(md_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        
        # 1. 예스24 텍스트 블록 삭제
        content = re.sub(r'\[\*\*UX의 언어들.*?https://www\.yes24\.com/product/goods/\d+\)[\r\n]*', '', content, flags=re.DOTALL)
        # 2. 트레바리 텍스트 블록 삭제 (앞에 주소가 붙은 형태)
        content = re.sub(r'https://trevar\.ink/[a-zA-Z0-9]+[\r\n]*\[\*\*기획자들은.*?https://trevar\.ink/[a-zA-Z0-9]+\)[\r\n]*', '', content, flags=re.DOTALL)
        # 3. 트레바리 일반 블록 삭제
        content = re.sub(r'\[\*\*기획자들은.*?https://trevar\.ink/[a-zA-Z0-9]+\)[\r\n]*', '', content, flags=re.DOTALL)
        # 4. 괄호가 깨져서 남은 트레바리 찌꺼기 주소 삭제
        content = re.sub(r'https://m\.trevari\.co\.kr/product/.*?\]\(https://trevar\.ink/[a-zA-Z0-9]+\)[\r\n]*', '', content)
        # 5. 허공에 둥둥 떠있는 trevar.ink 짧은 링크 삭제
        content = re.sub(r'^https://trevar\.ink/[a-zA-Z0-9]+[\r\n]*', '', content, flags=re.MULTILINE)

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            count += 1
            print(f"🧹 청소 완료: {filename}")

print(f"\n✅ 총 {count}개의 파일에서 깨진 홍보 링크가 깔끔하게 제거되었습니다!")