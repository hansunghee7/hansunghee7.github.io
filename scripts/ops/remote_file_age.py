#!/usr/bin/env python3
"""원격(구PC) 하트비트 파일이 최근에 갱신됐는지 본다. 사용: remote_file_age.py <ssh별명> <경로> <허용분>
종료 코드 0 = 정상, 1 = 오래됨/파일 없음/접속 실패. 감시 대장에서 kind="cmd"로 부른다(AI 없음)."""
import subprocess
import sys


def main():
    host, path, max_min = sys.argv[1], sys.argv[2], float(sys.argv[3])
    try:
        p = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host,
                            f"stat -c %Y {path} && date +%s"], capture_output=True, timeout=40, encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"{host} 접속 실패: {type(exc).__name__}")
        return 1
    lines = p.stdout.split()
    if p.returncode != 0 or len(lines) != 2:
        print(f"{host}에서 {path}를 읽지 못함(접속 불가 또는 파일 없음)")
        return 1
    age = (int(lines[1]) - int(lines[0])) / 60
    print(f"{host} {path} 마지막 갱신 {age:.0f}분 전(허용 {max_min:.0f}분)")
    return 0 if age <= max_min else 1


if __name__ == "__main__":
    sys.exit(main())
