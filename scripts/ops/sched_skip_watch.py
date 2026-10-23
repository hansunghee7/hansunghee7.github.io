# -*- coding: utf-8 -*-
"""클로드 앱 예약 실행기 '건너뜀' 감시(마야 2026-10-23).

사고: 앱의 예약 작업은 동시에 3개까지만 돌 수 있다(global_limit). 자리가 계속 차 있으면 1분마다
`Skipping dispatch ... global_limit`만 남기고 작업이 발사되지 않는다. 10/23 마루 강의록(13:40)이
424번 건너뛰어 7시간 동안 안 돌았고, 회의록 자동 브리핑도 같은 이유로 멈췄다. 앱은 알리지 않는다.

점검: 앱 메인 로그에서 최근 WINDOW_MIN분 동안 작업별 건너뜀 횟수를 센다(1분마다 한 번 기록되므로 횟수 ≈ 막힌 분).
  - global_limit 건너뜀이 GLOBAL_FAIL_MIN회 이상인 작업이 있으면 종료 코드 1(붉음).
  - per_task_limit(앞선 실행이 아직 도는 중)은 창 거의 내내(PER_TASK_FAIL_MIN회 이상)일 때만 붉음.
출력 첫 줄이 상태판에 그대로 보인다. 자리를 막은 세션은 로그에 안 나오므로 `--sessions`로 힌트를 준다.
"""
import argparse
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Claude" / "logs"
WINDOW_MIN = 30
GLOBAL_FAIL_MIN = 10
PER_TASK_FAIL_MIN = 28  # 창(30분) 거의 내내 앞선 실행이 안 끝난 경우
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[info\] \[CCDScheduledTasks\] Skipping dispatch for (\S+): (\w+) \(active=(\d+), limit=(\d+)\)")


def read_skips(now, window_min, log_dir=LOG_DIR):
    """(작업, 사유)별 건너뜀 횟수와 마지막 active/limit을 돌려준다."""
    since = now - timedelta(minutes=window_min)
    counts, last = Counter(), {}
    for name in ("main.log", "main1.log"):
        p = log_dir / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                m = LINE.match(line)
                if not m:
                    continue
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                if ts < since:
                    continue
                key = (m.group(2), m.group(3))
                counts[key] += 1
                last[key] = (m.group(4), m.group(5))
    return counts, last


def judge(counts, last, global_fail=GLOBAL_FAIL_MIN, per_task_fail=PER_TASK_FAIL_MIN):
    bad = []
    for (task, reason), n in counts.most_common():
        if reason == "global_limit" and n >= global_fail:
            a, l = last[(task, reason)]
            bad.append(f"{task} {n}분째 못 돎(동시 {a}/{l} 가득)")
        elif reason == "per_task_limit" and n >= per_task_fail:
            bad.append(f"{task} {n}분째 앞선 실행이 안 끝남")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=WINDOW_MIN)
    ap.add_argument("--sessions", action="store_true", help="자리를 막았을 후보 세션 힌트(앱 프로세스 시작 시각)를 덧붙임")
    a = ap.parse_args()
    now = datetime.now()
    counts, last = read_skips(now, a.window)
    bad = judge(counts, last, per_task_fail=min(PER_TASK_FAIL_MIN, max(a.window - 2, 1)))
    hint = "힌트: 앞선 실행이 안 끝난 작업(per_task)이 자리를 잡고 있을 수 있다. 앱에서 그 예약 세션을 닫으면 풀린다(동시 한도 3개)."
    if bad:
        print("예약 실행기 막힘: " + "; ".join(bad))
        if a.sessions:
            print(hint)
        sys.exit(1)
    total = sum(counts.values())
    print(f"예약 실행기 정상(최근 {a.window}분 건너뜀 {total}회, 기준 미만)")


if __name__ == "__main__":
    main()
