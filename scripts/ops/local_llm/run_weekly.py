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


SCRIPTS = ("weekly_archive_candidates.py", "weekly_change_summary.py")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def log(msg):
    """run.log에 한 줄 덧붙인다(pythonw로 뜨면 콘솔이 없어 로그가 유일한 흔적, 2026-10-20)."""
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "run.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
    except OSError:
        pass


def tail(text, n=40):
    return " | ".join((text or "").strip().splitlines()[-n:])


def run_one(script):
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # 작업 스케줄러 콘솔이 cp949라 이모지 출력에서 죽는 것을 막는다
    log(f"START {script}")
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=ROOT, env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # pythonw로 뜬 부모에서 자식 콘솔 창이 뜨지 않게(2026-09-29 N82)
        code, out, err = r.returncode, r.stdout, r.stderr
    except Exception as e:  # 실행 자체 실패(경로·권한)도 기록
        code, out, err = -1, "", f"{type(e).__name__}: {e}"
    log(f"END {script} 종료 코드 {code}")
    if out and out.strip():
        log(f"STDOUT {script}: {tail(out)}")
    if err and err.strip():
        log(f"STDERR {script}: {tail(err)}")
    return code


def main():
    os.makedirs(OUT, exist_ok=True)
    log(f"RUN 시작 python={sys.executable}")
    failed = [(s, c) for s in SCRIPTS for c in [run_one(s)] if c != 0]  # 한쪽이 실패해도 나머지는 계속 돈다
    if failed:
        for s, c in failed:
            print(f"[FAIL] {s} 종료 코드 {c}")
        log(f"RUN 실패 {len(failed)}건")
        return 1
    with open(os.path.join(OUT, "last-run.txt"), "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat(timespec="seconds") + "\n")
    log("RUN 성공")
    print("OK 주간 가공 2건 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
