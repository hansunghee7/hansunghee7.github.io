import os
import csv

md_dir = "brunch_web_assets/markdown"
img_dir = "brunch_web_assets/images"
csv_file = "브런치_글_모음집.csv"

print("\n=== [1] 마크다운 1번 파일 내부 상태 ===")
md_files = [f for f in os.listdir(md_dir) if f.endswith(".md") and f != "index.md"]
md_files.sort()

if md_files:
    sample_file = md_files[0]
    print(f"📌 파일명: {sample_file}")
    with open(os.path.join(md_dir, sample_file), 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print("📌 본문 상위 15줄:")
        print("".join(lines[:15]))
        
print("\n=== [2] 이미지 폴더 확인 ===")
if os.path.exists(img_dir):
    img_files = os.listdir(img_dir)[:5]
    print(f"📌 이미지 파일 샘플 5개: {img_files}")
else:
    print("❌ 이미지 폴더를 찾을 수 없습니다!")

print("\n=== [3] CSV 파일 매칭 확인 ===")
try:
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        print("📌 헤더:", next(reader))
        print("📌 1행:", next(reader))
except Exception as e:
    print("❌ CSV 오류:", e)