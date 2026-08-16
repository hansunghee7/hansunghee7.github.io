import subprocess
import sys
import os

# 명령어를 리스트 형태로 받아 실행하도록 변경 (shell=True의 위험성 제거)
def run_cmd(cmd_list):
    # 출력용으로 리스트를 다시 문자열로 합쳐서 보여줌
    cmd_str = " ".join(cmd_list)
    print(f"\n🚀 실행 중: {cmd_str}")
    
    # shell=False (기본값) 상태로 리스트를 넘기면 따옴표나 특수문자가 들어가도 안전함
    result = subprocess.run(cmd_list)
    
    if result.returncode != 0:
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

# 윈도우(Windows)라면 "py", 맥(Mac)이나 리눅스라면 "python3"를 자동으로 선택하도록 처리
python_cmd = "py" if os.name == "nt" else "python3"

# 각 명령어를 띄어쓰기 기준으로 쪼개어 리스트 형태로 전달
run_cmd([python_cmd, "sync_all.py"])
run_cmd(["git", "add", "-A"])
run_cmd(["git", "commit", "-m", commit_msg]) # 커밋 메시지에 따옴표가 있어도 절대 안 깨짐!
run_cmd(["git", "push"])

print("\n🎉 모든 변경 사항이 성공적으로 깃허브 서버에 배포되었습니다!")