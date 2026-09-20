#!/usr/bin/env python3
"""세션 시작 훅 보조: 감시(scripts/ops/watch.py)가 찾은 문제 줄을 에이전트에게 보여 준다.

왜: 에이전트가 일하다가 "안 된다"를 처음 발견하는 일이 반복됐다(2026-09-20). 세션을 시작할 때 이미 알려 준다.
상태 파일이 없거나 읽지 못하면 아무것도 출력하지 않는다(다른 PC, 감시 미설치 환경에서 조용히 통과).
감시 자체가 60분 넘게 안 돌았으면 그것을 먼저 알린다(감시의 감시).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

STATE = os.environ.get("OPS_STATE_DIR", r"C:\work\_ops")


def main():
    try:
        state = json.load(open(os.path.join(STATE, "state.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return
    kst = timezone(timedelta(hours=9))
    checked = [datetime.fromisoformat(v["checked"]) for v in state.values() if v.get("checked")]
    if not checked:
        return
    age = (datetime.now(kst) - max(checked)).total_seconds() / 60
    lines = []
    if age > 60:
        lines.append(f"⚠️ 감시가 {age:.0f}분째 안 돌고 있습니다(상태판이 낡았을 수 있음). 작업 스케줄러 simplifier-ops-watch를 확인하세요.")
    bad = [v for v in state.values() if v["status"] == "fail"]
    for v in bad[:5]:
        lines.append(f"🔴 지금 문제: {v['name']}: {v['detail']} ({v['since'][5:16].replace('T', ' ')}부터)")
    if len(bad) > 5:
        lines.append(f"🔴 그 밖에 문제 {len(bad) - 5}건")
    if lines:
        lines.append(f"상태판: {os.path.join(STATE, 'STATUS.md')}")
        print("\n".join(lines))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
