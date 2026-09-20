#!/usr/bin/env python3
"""예약 발행 보조 시계 (AI 없음, 토큰 0).

왜: 예약 발행 워크플로(scheduled-publish.yml)는 15분 간격으로 설정돼 있지만 GitHub가 예약 실행을 대량으로 누락해
실제로는 약 2시간 간격이고 4시간 넘게 안 돈 적이 있다(2026-09-20 감시가 발견). 그러면 예약 글이 몇 시간 늦게 나간다.
동작: 15분마다 작업 스케줄러가 이 스크립트를 부른다. 워크플로가 실행 중이거나 최근 STALE_MIN분 안에 돌았으면 아무것도 안 하고,
      그렇지 않으면(= GitHub가 누락) 같은 워크플로를 dry_run=false로 직접 실행한다. 발행 로직은 건드리지 않는다.
주의: 수동 실행의 기본값은 dry_run=true(출력만)라서 반드시 dry_run=false를 명시해야 실제 발행 시계 역할을 한다.
매 실행 끝에 kick.last를 갱신한다(감시가 이 파일로 보조 시계 자체가 도는지 본다).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
REPO = "hansunghee7/hansunghee7.github.io"
WORKFLOW = "scheduled-publish.yml"
STALE_MIN = 20
STATE_DIR = os.environ.get("OPS_STATE_DIR", r"C:\work\_ops")
BUSY = ("queued", "in_progress", "waiting", "pending", "requested")


def decide(runs, now, stale_min=STALE_MIN):
    """(행동, 이유). 행동은 'skip' 또는 'kick'."""
    if any(r.get("status") in BUSY for r in runs):
        return "skip", "실행 중이거나 대기 중"
    times = [datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")) for r in runs if r.get("createdAt")]
    if not times:
        return "kick", "실행 기록이 없음"
    age = (now - max(times)).total_seconds() / 60
    if age < stale_min:
        return "skip", f"{age:.0f}분 전에 정상 실행됨"
    return "kick", f"마지막 실행이 {age:.0f}분 전(GitHub 예약 누락 의심)"


def run(cmd, timeout=90):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def main():
    now = datetime.now(timezone.utc)
    gh = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    code, out = run([gh, "run", "list", "-R", REPO, "--workflow", WORKFLOW, "--limit", "5", "--json", "status,createdAt,conclusion,event"])
    if code != 0:
        line = f"조회 실패: {out[:120]}"
    else:
        action, why = decide(json.loads(out), now)
        line = f"{action}: {why}"
        if action == "kick":
            code, out = run([gh, "workflow", "run", WORKFLOW, "-R", REPO, "-f", "dry_run=false"])
            line += " -> 실행 요청 " + ("성공" if code == 0 else f"실패({out[:100]})")
    os.makedirs(STATE_DIR, exist_ok=True)
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(STATE_DIR, "kick.log"), "a", encoding="utf-8") as f:
        f.write(f"{stamp} {line}\n")
    if code == 0 or line.startswith("skip"):
        open(os.path.join(STATE_DIR, "kick.last"), "w", encoding="utf-8").write(stamp)
    return 0 if not line.startswith("조회 실패") and "실패" not in line else 1


if __name__ == "__main__":
    sys.exit(main())
