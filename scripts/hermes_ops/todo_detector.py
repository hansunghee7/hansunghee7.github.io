#!/usr/bin/env python3
"""todo_detector.py: 이 저장소 origin/main의 tasks/todo/*.md 새 지시서를 AI 호출 없이 감지한다(클로드 토큰 0).

배경(N171/N173, 사장님 2026-10-07): 클라우드 탐이 tasks/todo에 올린 지시서를 로컬 탐이 세션 시작까지 모르는 문제.
pending_detector.py(solar-bible tasks/pending*)와 같은 틀이지만 대상 저장소가 달라 섞지 않고 따로 둔다.

동작:
  1) git fetch 뒤 `git ls-tree`로 origin/main의 tasks/todo/*.md 목록만 본다(작업 트리는 건드리지 않는다).
  2) 상태 파일(todo_seen.json)에 없는 파일이 새 지시서다. 상태 파일이 없는 첫 실행은 지금 있는 것을 모두
     '본 것'으로 기록만 하고 알리지 않는다(밀린 지시서 알림 폭주 방지).
  3) 새 파일명을 todo_inbox.log에 한 줄 추가한다(탐 세션이 하이~ 때 읽는다). 지시서 내용은 싣지 않고 파일명만.
  4) 파일 둘째 줄이 `사장님확인: 예`일 때만 tg_boss.py로 마야 형식 알림을 보낸다. 아니오·없음이면 폰으로 보내지 않는다.
세션 깨우기: 이 스크립트는 SendMessage를 못 쓴다. 떠 있는 세션은 inbox 로그를 읽거나 하이~ 때 session_brief가 알린다.
  헤드리스 `claude -p`로 새 세션을 띄우는 방안은 주간 한도를 쓰므로 만들지 않았다(장점: 즉시 처리 시작 / 단점: 한도 소모·무인 실행 권한 설계 필요, 사장님 결정).

시험용 환경변수: TODO_REPO, TODO_SEEN, TODO_INBOX, TODO_NOTIFY_CMD (운영에서는 설정하지 않는다).
"""

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(os.environ.get("TODO_REPO", r"C:\work\hansunghee7.github.io"))
SEEN = Path(os.environ.get("TODO_SEEN", r"C:\work\_ops\todo_seen.json"))
INBOX = Path(os.environ.get("TODO_INBOX", r"C:\work\_ops\todo_inbox.log"))
NOTIFY = shlex.split(os.environ.get("TODO_NOTIFY_CMD", r"python C:\work\hansunghee7.github.io\scripts\ops\tg_boss.py"), posix=False)
TODO_DIR = "tasks/todo"


def git(*args, timeout=45):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout)


def needs_boss(text):
    """둘째 줄이 `사장님확인: 예`이면 True. 판정 순수 함수(시험 대상)."""
    lines = text.splitlines()
    return len(lines) >= 2 and lines[1].replace(" ", "").startswith("사장님확인:예")


def new_files(names, seen):
    return [n for n in names if n not in seen]


def load_seen():
    try:
        return json.loads(SEEN.read_text(encoding="utf-8")), True
    except (OSError, ValueError):
        return {}, False


def main():
    f = git("fetch", "-q", "origin", "main")
    if f.returncode != 0:
        print(f"[WARN] git fetch 실패: {f.stderr.strip()[:200]}")
        return 0
    ls = git("ls-tree", "--name-only", "-z", "origin/main", f"{TODO_DIR}/")
    if ls.returncode != 0:
        print(f"[WARN] ls-tree 실패: {ls.stderr.strip()[:200]}")
        return 0
    names = [n for n in ls.stdout.split("\0") if n.endswith(".md")]
    seen, existed = load_seen()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    fresh = new_files(names, seen)
    if not existed:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps({n: now for n in names}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] {now} 첫 실행: 기존 지시서 {len(names)}건을 본 것으로 기록(알림 없음)")
        return 0
    for n in fresh:
        base = os.path.basename(n)
        show = git("show", f"origin/main:{n}")
        boss = show.returncode == 0 and needs_boss(show.stdout)
        INBOX.parent.mkdir(parents=True, exist_ok=True)
        with open(INBOX, "a", encoding="utf-8") as fh:
            fh.write(f"{now}\t{base}\t사장님확인={'예' if boss else '아니오'}\n")
        if boss:
            msg = (f"[할 일] 새 지시서 도착: {base}\n선택지 없음, 확인만 필요합니다.\n"
                   f"👉 사장님 할 일: 탐 세션에서 이 지시서를 열어 달라고 한 줄만 말해 주세요.")
            try:
                subprocess.run([*NOTIFY, "text", msg, "--persona", "탐"], capture_output=True, timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except (OSError, subprocess.TimeoutExpired) as e:
                print(f"[ERROR] 알림 실패({base}): {type(e).__name__}")
                continue   # seen에 넣지 않아 다음 실행에서 재시도
        seen[n] = now
        print(f"[INFO] {now} 새 지시서 감지: {base} (알림={'예' if boss else '아니오'})")
    for gone in [n for n in seen if n not in names]:
        del seen[gone]
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
