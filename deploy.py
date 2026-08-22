import subprocess
import sys
import os

# ignore_error 파라미터 추가
def run_cmd(cmd_list, ignore_error=False):
    cmd_str = " ".join(cmd_list)
    print(f"\n🚀 실행 중: {cmd_str}")
    
    result = subprocess.run(cmd_list)
    
    # 에러가 발생했고, 무시하라는 설정이 없을 때만 중단
    if result.returncode != 0 and not ignore_error:
        print(f"❌ 에러가 발생하여 작업을 중단합니다: {cmd_str}")
        sys.exit(1)

# 1. 커밋 메시지 입력받기
commit_msg = input("📝 커밋 메시지를 입력하세요 (엔터 치면 기본값 사용): ").strip()
if not commit_msg:
    commit_msg = "update blog content and sync index"

# 2. 4단계 자동화 명령어 연속 실행
print("\n==========================================")
print("✨ 심플리파이어 블로그 자동 배포를 시작합니다.")
print("==========================================")

python_cmd = "py" if os.name == "nt" else "python3"

run_cmd([python_cmd, "sync_all.py"])
run_cmd(["git", "add", "-A"])
# 커밋은 '변경사항 없음' 에러가 날 수 있으므로 예외 처리 추가
run_cmd(["git", "commit", "-m", commit_msg], ignore_error=True) 
run_cmd(["git", "push"])

print("\n🎉 모든 변경 사항이 성공적으로 깃허브 서버에 배포되었습니다!")