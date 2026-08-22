import os

# 🎯 삭제하고 싶은 첫 직장 관련 글의 키워드나 마크다운 파일명 번호를 리스트에 적어주세요.
# 예시: ["이력서", "첫직장", "401_", "394_"] 등
TARGET_KEYWORDS = ["이력서에 쓰지 않는 첫 직장이야기"]

TARGET_DIR = "log_assets/markdown"
deleted_count = 0

if os.path.exists(TARGET_DIR):
    for filename in os.listdir(TARGET_DIR):
        if filename.endswith(".md"):
            # 키워드가 파일명에 포함되어 있는지 확인
            if any(kw in filename for kw in TARGET_KEYWORDS):
                filepath = os.path.join(TARGET_DIR, filename)
                try:
                    os.remove(filepath)
                    print(f"🗑️ 삭제 완료: {filename}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ 삭제 실패 ({filename}): {e}")

    print(f"\n🎉 총 {deleted_count}개 포스트 삭제가 완료되었습니다.")
else:
    print("❌ log_assets/markdown 폴더를 찾을 수 없습니다.")