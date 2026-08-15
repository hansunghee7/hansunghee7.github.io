import os
import re

md_dir = "brunch_web_assets/markdown"

# 1. 마크다운 파일 목록 불러오기
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]

# 2. 고유번호(UID)를 기준으로 파일들을 그룹화
uid_groups = {}
for filename in md_files:
    match = re.match(r'^(\d+)_', filename)
    if match:
        uid = match.group(1)
        if uid not in uid_groups:
            uid_groups[uid] = []
        uid_groups[uid].append(filename)

print("🔍 중복 파일 검사 및 청소 시작...\n")
deleted_count = 0

# 3. 같은 번호에 파일이 2개 이상 있으면, 최신 파일만 남기고 삭제
for uid, files in uid_groups.items():
    if len(files) > 1:
        # 파일들을 '수정된 시간' 순으로 정렬
        files_with_time = [(f, os.path.getmtime(os.path.join(md_dir, f))) for f in files]
        files_with_time.sort(key=lambda x: x[1])
        
        # 가장 마지막(최신) 파일만 남기고, 나머지 예전 파일들은 리스트로 뽑기
        older_files = [f[0] for f in files_with_time[:-1]]
        
        for old_file in older_files:
            old_filepath = os.path.join(md_dir, old_file)
            os.remove(old_filepath)
            print(f"🗑️ 찌꺼기 삭제 완료: {old_file}")
            deleted_count += 1

print(f"\n✅ 총 {deleted_count}개의 중복 찌꺼기 파일이 완벽하게 청소되었습니다!")