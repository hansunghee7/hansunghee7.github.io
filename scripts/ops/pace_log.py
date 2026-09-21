#!/usr/bin/env python3
"""토큰(주간 한도) 페이스를 기록하고 판정한다 (2026-09-22 사장님 지시: 탐이 놓치지 말고 챙긴다).

왜: 사장님 목표는 주간 한도 초기화(현재 토 9/26 18:00 KST)까지 탐을 쓰는 것이다. 한도가 먼저 바닥나면 못 쓴다.
페이스 = 주간 사용률(%) ÷ 주간 기간 경과율(%). 1.0이면 딱 맞는 속도, 넘으면 한도를 일찍 다 쓴다.

사용(세션 시작과 종료 때 `get_usage` 값으로 실행):
  pace_log.py --week 47 --five 30 --reset 2026-09-26T09:00:00Z [--ctx 64] [--note "세션 시작"]
  --reset 값은 get_usage의 "Weekly · all models" resetsAt 그대로(UTC). 창 길이는 7일로 본다.

출력: 한 줄 판정(정상/주의/경고)과 하루 권장 사용률. 기록은 C:\\work\\_ops\\pace\\usage.csv에 쌓고,
      last-run.txt를 갱신한다(감시 대장이 이 파일의 나이를 본다: 기록이 오래 없으면 붉어진다).
판정 기준 1.0(주의)/1.3(경고)은 백로그의 제안값이며 사장님 확정 전이다.
"""
import argparse
import csv
import datetime as dt
import os
import sys

STATE = os.environ.get("PACE_STATE", r"C:\work\_ops\pace")
WARN, ALERT = 1.0, 1.3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_utc(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def evaluate(week_pct, reset_utc, now_utc):
    start = reset_utc - dt.timedelta(days=7)
    elapsed = (now_utc - start).total_seconds() / (7 * 86400)
    elapsed = min(max(elapsed, 0.0001), 1.0)
    pace = (week_pct / 100.0) / elapsed
    days_left = max((reset_utc - now_utc).total_seconds() / 86400, 0.01)
    per_day = (100.0 - week_pct) / days_left
    return elapsed, pace, days_left, per_day


def label(pace):
    if pace > ALERT:
        return "경고"
    if pace > WARN:
        return "주의"
    return "정상"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=float, required=True, help="주간 전체 모델 사용률 퍼센트")
    ap.add_argument("--five", type=float, default=None, help="5시간 한도 사용률 퍼센트")
    ap.add_argument("--reset", required=True, help="주간 초기화 시각 UTC ISO (get_usage resetsAt)")
    ap.add_argument("--ctx", type=float, default=None, help="이 세션 컨텍스트 사용률 퍼센트")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    elapsed, pace, days_left, per_day = evaluate(a.week, parse_utc(a.reset), now)
    lab = label(pace)
    os.makedirs(STATE, exist_ok=True)
    path = os.path.join(STATE, "usage.csv")
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["기록시각_UTC", "주간%", "5시간%", "컨텍스트%", "경과율%", "페이스", "판정", "남은일수", "하루권장%", "메모"])
        w.writerow([now.isoformat(timespec="seconds"), a.week, a.five if a.five is not None else "", a.ctx if a.ctx is not None else "",
                    round(elapsed * 100, 1), round(pace, 2), lab, round(days_left, 2), round(per_day, 1), a.note])
    with open(os.path.join(STATE, "last-run.txt"), "w", encoding="utf-8") as f:
        f.write(now.isoformat(timespec="seconds") + f"\n{lab} 페이스 {pace:.2f}\n")
    print(f"{lab}: 주간 {a.week:g}% / 기간 경과 {elapsed*100:.1f}% = 페이스 {pace:.2f}. "
          f"남은 {days_left:.1f}일, 하루 {per_day:.1f}% 이내로 써야 초기화까지 간다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
