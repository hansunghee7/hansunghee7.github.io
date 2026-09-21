#!/usr/bin/env python3
"""주간 로컬 LLM 가공 2건을 차례로 돌리고, 둘 다 성공했을 때만 last-run.txt를 갱신한다(2026-09-21, 백로그 44).
감시 대장(jobs.toml)이 last-run.txt의 수정 시각으로 주기 실행을 확인한다(결과물 존재로 성공 판정).
작업 스케줄러 `simplifier-weekly-local`이 월요일 09:00에 부른다. 결과는 초안이며 판정하지 않는다.
"""
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\work\_ops\weekly"


def main():
    os.makedirs(OUT, exist_ok=True)
    for script in ("weekly_archive_candidates.py", "weekly_change_summary.py"):
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # 작업 스케줄러 콘솔이 cp949라 이모지 출력에서 죽는 것을 막는다
        r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=os.path.dirname(os.path.dirname(os.path.dirname(HERE))), env=env)
        if r.returncode != 0:
            print(f"[FAIL] {script} 종료 코드 {r.returncode}")
            return r.returncode
    with open(os.path.join(OUT, "last-run.txt"), "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat(timespec="seconds") + "\n")
    print("OK 주간 가공 2건 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
