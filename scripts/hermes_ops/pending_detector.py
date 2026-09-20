#!/usr/bin/env python3
"""pending_detector.py: solar-bible tasks/pending의 새 지시서를 AI 호출 없이 감지해 폴러를 깨운다.

배경(백로그 28, 2026-09-20 사장님 승인): 기존 폴러(solar-bible-tasks-poller)는 3분마다 AI 에이전트를
부르는 방식이라 간격을 줄이면 AI 호출과 무료 모델 한도가 그대로 늘어난다. 이 스크립트는
`hermes cron create ... --no-agent --script pending_detector.py`로 1분마다 돌리는 값싼 감지기다.

동작:
  1) git fetch로 origin/main의 tasks/pending/*.md 목록만 본다(작업 트리는 건드리지 않는다).
  2) 이미 깨운 적 있는 파일이면 무시. 새 파일이 있으면 `hermes cron run <폴러 id>`로 폴러를 부른다.
  3) 깨운 파일 이름과 시각을 상태 파일에 기록한다(같은 파일로 폴러를 반복 호출하지 않는다).
  4) 새 파일이 없으면 아무것도 출력하지 않는다(no-agent 모드에서 빈 출력은 조용함).
기존 폴러는 삭제하지 않고 안전망(느린 주기)으로 남긴다.

시험용 환경변수: DETECTOR_REPO, DETECTOR_STATE, DETECTOR_HERMES_CMD (실제 운영에서는 설정하지 않는다).
"""

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(os.environ.get("DETECTOR_REPO", r"C:\work\solar-bible"))
STATE = Path(os.environ.get("DETECTOR_STATE", r"C:\Users\PC\AppData\Local\hermes\pending_detector_state.json"))
POLLER_ID = "dbec1e96eff3"
HERMES_CMD = [t.strip('"') for t in shlex.split(os.environ.get("DETECTOR_HERMES_CMD", "hermes"), posix=False)]
PENDING_DIR = "tasks/pending"


def git(*args, timeout=45):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"triggered": {}}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    f = git("fetch", "-q", "origin", "main")
    if f.returncode != 0:
        print(f"[WARN] git fetch 실패: {f.stderr.strip()[:200]}")
        return 0
    ls = git("ls-tree", "-r", "--name-only", "origin/main", "--", PENDING_DIR)
    if ls.returncode != 0:
        print(f"[WARN] ls-tree 실패: {ls.stderr.strip()[:200]}")
        return 0
    names = [n for n in ls.stdout.splitlines() if n.endswith(".md")]
    state = load_state()
    triggered = state.setdefault("triggered", {})
    # 이미 처리돼 pending에서 사라진 파일은 기록에서 지운다(같은 이름이 다시 오면 다시 깨운다).
    for gone in [n for n in triggered if n not in names]:
        del triggered[gone]
    new = [n for n in names if n not in triggered]
    if not new:
        save_state(state)
        return 0
    try:
        r = subprocess.run([*HERMES_CMD, "cron", "run", POLLER_ID], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        failed = r.returncode != 0
        failure = (r.stderr or r.stdout).strip()[:200] or f"종료 코드 {r.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:   # hermes를 못 찾거나 응답이 없는 경우
        failed = True
        failure = f"{type(e).__name__}: {e}"[:200]
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    if failed:
        print(f"[ERROR] 폴러 기동 실패(다음 실행에서 재시도): {failure}")
        save_state(state)
        return 1
    for n in new:
        triggered[n] = now
    save_state(state)
    print(f"[INFO] {now} 새 지시서 {len(new)}건 감지, 폴러 기동: " + ", ".join(os.path.basename(n) for n in new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
