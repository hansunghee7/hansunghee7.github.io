#!/usr/bin/env python3
"""pending_poller.py: solar-bible tasks/pending(-long) 처리를 AI 에이전트 대화 루프 대신
파이썬 스크립트가 기계적인 부분(git pull, 파일 목록, 이동, 커밋, push, 우편 알림)을 하고,
실제 작업 내용만 `hermes chat --oneshot` 한 번(작업마다)으로 처리한다.

배경(탐, 2026-09-22, 백로그: 폴러 토큰 다이어트 2단계): 기존 방식은 크론이 매번 상위 에이전트
대화를 열어 git pull/ls/mv/commit/push/알림까지 전부 도구 호출로 했다. 종단 시험 1회 실측
15번 호출·입력 토큰 합계 약 19만. 이 스크립트는 그 오케스트레이션을 AI 없이 처리해
작업이 있을 때도 "실제 작업 처리" 1회 호출만 남긴다. 작업이 없으면 호출이 0이다
(기존 `pending_detector.py`가 이미 그렇게 하는 것과 같은 원리).

`hermes cron edit <id> --no-agent --script pending_poller.py`로 등록한다(no-agent 모드:
이 스크립트의 표준출력이 그대로 전달되고, 상위 에이전트 턴은 열리지 않는다).

사용: python pending_poller.py --lane pending|pending-long [--repo PATH] [--hermes-cmd "hermes"]
시험용 환경변수: POLLER_REPO, POLLER_HERMES_CMD, POLLER_MAILBOX_CMD (실제 운영에서는 설정하지 않는다).

⚠️ 이 파일은 버전 관리용 사본이다. 실제 실행본은 헤르메스 홈
(`C:/Users/PC/AppData/Local/hermes/scripts/pending_poller.py`)에 있고 `hermes cron`이 거기서
읽는다. 이 사본을 고치면 실행본에도 같은 내용을 반영해야 동작이 바뀐다(자동 동기화 없음).
"""

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

LANES = {
    "pending": {"dir": "tasks/pending", "notify": False},
    "pending-long": {"dir": "tasks/pending-long", "notify": True},
}


def run(cmd, cwd, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)


def git(repo, *args, timeout=60):
    return run(["git", *args], cwd=repo, timeout=timeout)


def git_push_with_retry(repo, log):
    p = git(repo, "push", "origin", "main")
    if p.returncode == 0:
        return True
    log.append(f"[WARN] push 1차 실패, pull --rebase 후 재시도: {p.stderr.strip()[:200]}")
    git(repo, "pull", "-q", "--rebase", "origin", "main")
    p2 = git(repo, "push", "origin", "main")
    if p2.returncode != 0:
        log.append(f"[ERROR] push 재시도도 실패: {p2.stderr.strip()[:300]}")
        return False
    return True


def process_one(repo, path, hermes_cmd, log):
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        log.append(f"[SKIP] {path.name}: 빈 파일")
        return False
    # 2026-09-22 탐: 기본 모델(solar-pro4)이 한도에 걸리면 qwen 14B(컨텍스트 32K)까지 밀려
    # 다단계 작업에서 응답이 깨지는 사고가 실측됨(백로그 30·31 처리 실패, 문서 미확정 텍스트로
    # 끝남). gemini-fast(빠른 키 순환)로 고정해 그 페일오버 체인을 건너뛴다.
    p = run([*hermes_cmd, "chat", "-q", text, "-Q", "--provider", "gemini-fast", "-m", "gemini-3.6-flash"],
            cwd=repo, timeout=1200)
    out = (p.stdout or "").strip()
    if p.returncode != 0:
        log.append(f"[ERROR] {path.name}: hermes chat 실패(exit {p.returncode}): {(p.stderr or out)[:300]}")
        return False
    log.append(f"[OK] {path.name}: 처리 완료 ({len(out)}자 응답)")
    return True


def notify(repo, mailbox_cmd, fname, log):
    m = re.search(r"\(([^)]*?)\s*->\s*헤르메스\)", fname) or re.search(r"^#\s*(\S+)", fname)
    to = (m.group(1).strip() if m else "탐") or "탐"
    body = f"tasks/done/{fname} 확인. 보고서 경로는 지시서에 적힌 그대로."
    p = run([*mailbox_cmd, "send", to, f"{fname} 완료", "--from", "헤르메스", "--body", body], cwd=repo, timeout=30)
    if p.returncode != 0:
        log.append(f"[WARN] 우편 알림 실패: {(p.stderr or p.stdout)[:200]}")
    else:
        log.append(f"[MAIL] {to}에게 완료 알림")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True, choices=LANES)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--hermes-cmd", default=None)
    ap.add_argument("--mailbox-cmd", default=None)
    args = ap.parse_args()

    import os
    repo = Path(args.repo or os.environ.get("POLLER_REPO", r"C:\work\solar-bible"))
    hermes_cmd = shlex.split(args.hermes_cmd or os.environ.get("POLLER_HERMES_CMD", "hermes"), posix=False)
    mailbox_cmd = shlex.split(
        args.mailbox_cmd or os.environ.get("POLLER_MAILBOX_CMD", f"python {repo / 'mailbox' / 'mailbox.py'}"),
        posix=False,
    )
    lane = LANES[args.lane]
    lane_dir = repo / lane["dir"]
    log = []

    p = git(repo, "fetch", "-q", "origin", "main")
    if p.returncode != 0:
        print(f"[WARN] git fetch 실패: {p.stderr.strip()[:200]}")
        return 0
    git(repo, "reset", "-q", "--hard", "origin/main")  # 작업 트리를 원격과 맞춤(로컬 미커밋 변경 없음을 전제)

    files = sorted(f for f in lane_dir.glob("*.md") if f.name != ".gitkeep" and not f.name.startswith("."))
    if not files:
        return 0  # 조용히 종료(no-agent 모드에서 빈 출력은 조용함)

    processed = []
    for f in files:
        ok = process_one(repo, f, hermes_cmd, log)
        if not ok:
            continue
        done_dir = repo / "tasks" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        dest = done_dir / f.name
        if dest.exists():
            log.append(f"[WARN] {f.name}: tasks/done에 이미 존재, pending에서만 제거")
            f.unlink()
        else:
            f.rename(dest)
        git(repo, "add", "-A")
        c = git(repo, "commit", "-q", "-m", f"done: {f.stem}")
        if c.returncode != 0 and "nothing to commit" not in (c.stdout + c.stderr):
            log.append(f"[ERROR] {f.name}: commit 실패: {c.stderr.strip()[:200]}")
            continue
        if not git_push_with_retry(repo, log):
            continue
        processed.append(f.name)
        if lane["notify"]:
            notify(repo, mailbox_cmd, f.name, log)

    print(f"[{args.lane}] 처리 {len(processed)}/{len(files)}건: {', '.join(processed) or '없음'}")
    for line in log:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
