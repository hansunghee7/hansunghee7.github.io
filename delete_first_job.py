import os

KEYWORDS = ["첫직장", "이력서에 쓰지 않는"]
deleted_files = []

# 프로젝트 내 log_assets 및 주요 경로 탐색
for root, dirs, files in os.walk("."):
    if '.git' in root or 'venv' in root:
        continue
    
    for file in files:
        if file.endswith(('.md', '.html')):
            filepath = os.path.join(root, file)
            
            # 1. 파일명에 키워드가 있는 경우
            is_target = any(kw in file for kw in KEYWORDS)
            
            # 2. 파일 내용(YAML 헤더)에 키워드가 있는 경우
            if not is_target:
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(1000) # 상단 1000자만 검사
                        if any(kw in content for kw in KEYWORDS):
                            is_target = True
                except Exception:
                    pass

            if is_target:
                try:
                    os.remove(filepath)
                    deleted_files.append(filepath)
                    print(f"🗑️ 삭제 완료: {filepath}")
                except Exception as e:
                    print(f"❌ 삭제 실패 ({filepath}): {e}")

print(f"\n🎉 총 {len(deleted_files)}개 관련 파일(MD/HTML) 완벽 삭제 완료!")