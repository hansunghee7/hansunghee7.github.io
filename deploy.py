import subprocess
import sys

def run_cmd(cmd):
    print(f"\n🚀 실행 중: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ 에러가 발생하여 작업을 중단합니다: {cmd}")
        sys.exit(1)

# 1. 커밋 메시지 입력받기 (엔터만 치면 기본 메시지 사용)
commit_msg = input("📝 커밋 메시지를 입력하세요 (엔터 치면 기본값 사용): ").strip()
if not commit_msg:
    commit_msg = "update blog content and sync index"

# 2. 4단계 자동화 명령어 연속 실행
print("\n==========================================")
print("✨ 심플리파이어 블로그 자동 배포를 시작합니다.")
print("==========================================")

run_cmd("py sync_all.py")
run_cmd("git add -A")
run_cmd(f'git commit -m "{commit_msg}"')
run_cmd("git push")

print("\n🎉 모든 변경 사항이 성공적으로 깃허브 서버에 배포되었습니다!")