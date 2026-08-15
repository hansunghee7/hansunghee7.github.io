import csv
import os

csv_file = "브런치_글_모음집.csv"
target_md = "brunch_web_assets/markdown/551_남들은 다 행복한 거 같아요.md"

found = False

if os.path.exists(csv_file):
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        for row in reader:
            # CSV 행 구조 체크 (보통: ID, 제목, 날짜, 카테고리, 이미지, 본문 등)
            # 551번 글을 찾거나 제목으로 탐색
            if len(row) >= 2 and ("551" in row[0] or "남들은 다 행복한 거 같아요" in row[1]):
                title = row[1].strip() if len(row) > 1 else "남들은 다 행복한 거 같아요"
                date_str = row[2].strip() if len(row) > 2 else ""
                category = row[3].strip() if len(row) > 3 and row[3].strip() else "기획일상"
                cover_img = row[4].strip() if len(row) > 4 and row[4].strip() else "/brunch_web_assets/images/logo_white.png"
                body = row[5].strip() if len(row) > 5 else "본문 내용을 찾을 수 없습니다."
                
                # 마크다운 파일 내용 재구성
                md_content = f"""---
layout: default
title: "{title}"
category: '{category}'
cover_image: '{cover_img}'
date_string: '{date_str}'
---

{body}
"""
                with open(target_md, 'w', encoding='utf-8') as md_f:
                    md_f.write(md_content)
                
                print(f"✅ 551번 글이 CSV 데이터를 기반으로 완벽하게 복원되었습니다!")
                print(f"📌 제목: {title}")
                print(f"📌 카테고리: {category}")
                print(f"📌 커버이미지: {cover_img}")
                found = True
                break

if not found:
    print("⚠️ CSV 파일에서 551번 글 항목을 찾지 못했습니다. CSV의 컬럼 순서를 확인해주세요.")