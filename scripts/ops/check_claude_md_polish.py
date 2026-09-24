#!/usr/bin/env python3
"""CLAUDE.md 격주 폴리싱과 [본문 반영 대기] 태그가 방치되지 않았는지 기계적으로 확인한다.
AI 없이 git 날짜와 텍스트만 본다(no-agent 헤르메스 크론용, LLM 판정 불필요).
정상이면 표준출력이 비어 조용히 끝난다(hermes cron --no-agent 관례: 빈 출력 = 알림 없음).
이상이 있을 때만 mailbox.py로 탐에게 직접 알리고 exit 1 -- watch.py의 hermes_cron stuck
판정과도 별개로, 이 알림이 "깨우기"다.

등록: scripts/ops/jobs.toml (kind=hermes_cron), CLAUDE.md#문서_다이어트_기준.md 참고.
실행 위치: 헤르메스 홈(~/.hermes/scripts/)의 사본이 실제로 크론이 읽는 파일이다.
"""
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\work\hansunghee7.github.io")
POLISH_LOG = REPO / "docs" / "폴리싱_기록.md"
PROGRESS = REPO / "docs" / "진행상황.md"
MAILBOX = Path(r"C:\work\solar-bible\mailbox\mailbox.py")

POLISH_MAX_DAYS = 14
TAG_MAX_DAYS = 7
TAG = "[본문 반영 대기]"


def git_last_commit_days(path):
    r = subprocess.run(
        ["git", "-C", str(REPO), "log", "-1", "--format=%at", "--", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    ts = r.stdout.strip()
    if not ts:
        return None
    commit_date = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - commit_date).days


def find_stale_tags():
    text = PROGRESS.read_text(encoding="utf-8")
    problems = []
    for line in text.splitlines():
        # 공지 제목 줄만 본다. 본문에 "[본문 반영 대기] 태그 해제" 같은 설명이 있으면
        # 날짜 없는 줄로 읽혀 오탐이 났다(2026-09-24, 탐 대장 N23).
        if TAG not in line or not line.startswith("## "):
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})\)\s*$", line)
        title = line.split("(확인:")[0].strip("# ").strip()
        if not m:
            problems.append(f"{title}: 날짜 형식을 못 읽음 -- 확인 필요")
            continue
        tag_date = dt.datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        age_days = (dt.datetime.now(dt.timezone.utc) - tag_date).days
        if age_days > TAG_MAX_DAYS:
            problems.append(f"{title}: {age_days}일째 [본문 반영 대기] 미해소(기준 {TAG_MAX_DAYS}일)")
    return problems


def main():
    problems = []

    polish_age = git_last_commit_days(POLISH_LOG)
    if polish_age is None:
        problems.append(f"{POLISH_LOG.name}: git 기록을 못 찾음")
    elif polish_age > POLISH_MAX_DAYS:
        problems.append(f"{POLISH_LOG.name}: 마지막 폴리싱 {polish_age}일 전(기준 {POLISH_MAX_DAYS}일) -- CLAUDE#a18e 격주 폴리싱 필요")

    problems.extend(find_stale_tags())

    if problems:
        body = "CLAUDE.md 폴리싱/반영 점검 이상:\n" + "\n".join(f"- {p}" for p in problems)
        print(body)
        try:
            subprocess.run(
                ["python", str(MAILBOX), "send", "탐", "[감시] CLAUDE.md 폴리싱 점검 이상",
                 "--from", "헤르메스", "--body", body],
                cwd=str(REPO), timeout=30, capture_output=True, text=True,
            )
        except Exception as e:  # 우편 실패해도 exit 1(감시 대장 FAIL)은 유지 -- 이중 안전망
            print(f"[WARN] 우편 알림 실패: {e}")
        return 1

    return 0  # 정상: 출력 없음 -> hermes cron --no-agent가 조용히 넘어간다


if __name__ == "__main__":
    sys.exit(main())
