import os
import re

md_dir = "brunch_web_assets/markdown"

print("🔍 마크다운 파일 내 의심스러운 찌꺼기/URL 점검을 시작합니다...\n")

found_issues = False
total_files = 0

for filename in os.listdir(md_dir):
    if not filename.endswith(".md"):
        continue
        
    total_files += 1
    filepath = os.path.join(md_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        # 1. 파일 맨 위쪽 설정값(YAML) 부분은 정상적인 이미지 주소가 있으므로 검사 패스
        if line.startswith('cover_image:') or line.startswith('layout:') or line.startswith('title:'):
            continue
            
        # 2. 이전 스크립트들이 남겼을지 모르는 숨겨진 HTML 주석(<!-- -->) 탐지
        if re.search(r'<!--.*?-->', line):
            print(f"⚠️ [HTML 찌꺼기 발견] {filename} (줄 {i+1}): {line.strip()}")
            found_issues = True
            
        # 3. 본문에 생짜로 둥둥 떠있는 URL 탐지
        # (마크다운 정상 링크 [텍스트](URL) 형태나 괄호 안에 있는 URL은 제외하고 찾음)
        urls = re.findall(r'(?<![\(\<\"])(https?://[^\s\>\)\"]+)', line)
        for url in urls:
            print(f"🔗 [생짜 URL 발견] {filename} (줄 {i+1}): {url}")
            found_issues = True

if not found_issues:
    print(f"✨ 총 {total_files}개의 파일을 검사한 결과, 의심스러운 찌꺼기나 생짜 URL이 발견되지 않았습니다. 아주 깨끗합니다!")
else:
    print("\n💡 위 목록을 확인해 보시고, 지워야 할 불필요한 패턴이 있다면 복사해서 저에게 알려주세요!")