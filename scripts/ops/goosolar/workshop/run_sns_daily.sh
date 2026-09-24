#!/usr/bin/env bash
# 매일 SNS 숫자 읽기 + 크롬 확장 비교(2026-09-24 탐, 사장님 결정: 3일 나란히 비교 후 연결).
# 구PC crontab: 0 1 * * * $HOME/workshop/run_sns_daily.sh   (구PC는 UTC, 01:00 UTC = 10:00 KST)
# 결과: ~/workshop/out/sns/<날짜>.jsonl, compare_<날짜>.md, 감시용 last_run(성공 때만 갱신)
set -u
W="$HOME/workshop"; D=$(TZ=Asia/Seoul date +%F); O="$W/out/sns"
mkdir -p "$O"
exec 8>"$O/run.lock"; flock -n 8 || exit 0
"$W/venv/bin/python" "$W/sns_read.py" > "$O/$D.jsonl" 2> "$O/err_$D.txt" || exit 1
n=$(grep -c '"followers": [0-9]' "$O/$D.jsonl")
"$W/venv/bin/python" "$W/sns_compare.py" "$O/$D.jsonl" > "$O/compare_$D.md" 2>> "$O/err_$D.txt"
[ "$n" -ge 8 ] && echo "$(date '+%F %T') ok channels_with_followers=$n" > "$O/last_run"
