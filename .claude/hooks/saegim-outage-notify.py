#!/usr/bin/env python3
"""PostToolUse 훅: .claude/saegim-outage 파일이 생성되면 사장님과 지투에게 즉시 우편으로 통보한다.

왜: UX_GUIDE 지름길(로컬 docs/UX_GUIDE.md 직접 읽기)을 saegim-gate.py가 막되, 완전
차단(동기 승인 대기)은 기술적으로 못 한다 -- 승인자 세션이 그 순간 꺼져 있으면 일이
무한정 멈춘다. 대신 "만들면 즉시 통보"로 구현한다(사장님 확정, 2026-09-23. "UX가이드
문서는 사장 승인받고 쓰게 하라" + "불편해야지 개선합니다" -- 그래서 지투 한 명이 아니라
사장님께도 같이 보낸다. 우회가 조용히 넘어가지 않게 하는 게 목적이다). 지투가 사후에
"진짜 장애였는지 아니면 그냥 귀찮아서 우회한 건지"를 판단하고, 방치되면 직접 지운다.

실패해도 세션을 막지 않는다(알림 실패는 작업을 막을 이유가 아니다) -- 항상 exit 0,
예외는 전부 삼킨다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def _is_outage_file(tinput):
    path = (tinput.get("file_path") or "").replace("\\", "/")
    return path.endswith(".claude/saegim-outage")


def _find_mailbox_script(project_dir):
    # solar-bible은 이 저장소와 형제 폴더로 구성된다(C:/work/solar-bible).
    candidates = []
    if project_dir:
        candidates.append(Path(project_dir).parent / "solar-bible" / "mailbox" / "mailbox.py")
    candidates.append(Path.home() / "work" / "solar-bible" / "mailbox" / "mailbox.py")
    for c in candidates:
        if c.exists():
            return c
    return None


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0

    tool = event.get("tool_name", "")
    tinput = event.get("tool_input") or {}
    if tool != "Write" or not _is_outage_file(tinput):
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    mailbox_py = _find_mailbox_script(project_dir)
    if mailbox_py is None:
        return 0

    branch = "알 수 없음"
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_dir or None,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            branch = out.stdout.strip() or branch
    except Exception:
        pass

    body = (
        f".claude/saegim-outage 파일이 생성됐습니다(자동 통보, saegim-outage-notify.py). "
        f"브랜치: {branch}. 이 파일이 있으면 새김 조회 없이도 사장님 보고·UX_GUIDE.md 직접 읽기가 "
        f"통과됩니다. 정말 새김 장애였는지 확인이 필요합니다 -- 아니면 지적한 뒤 지워주세요. 복구되면 "
        f"만든 세션이 직접 지우는 게 원칙입니다."
    )

    for to in ("지투", "사장님"):
        try:
            subprocess.run(
                [
                    sys.executable if sys.executable else "python",
                    str(mailbox_py),
                    "send",
                    to,
                    "새김 우회 파일 생성 자동 통보",
                    "--from",
                    "시스템(자동)",
                    "--body",
                    body,
                ],
                timeout=15,
                capture_output=True,
            )
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
