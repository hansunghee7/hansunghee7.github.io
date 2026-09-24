#!/usr/bin/env bash
# 구PC 작업실 결과물을 신PC로 가져오고 규격을 확인한다(2026-09-24 탐). 신PC Git Bash에서 실행.
# 사용: bash scripts/ops/goosolar/workshop/pull.sh <구PC 결과 폴더 이름> <신PC 받을 폴더>
#   예: bash scripts/ops/goosolar/workshop/pull.sh ep13 "D:/Downloads/AI숏폼 제작/ep13. 창문냄새/clips"
# 이미 같은 크기로 받은 파일은 건너뛴다. 끝에 파일별 해상도·길이와 크기 중복 검사(핏 verify_clips 원칙)를 출력한다.
set -euo pipefail
src="${1:?구PC out/ 아래 폴더 이름}"; dest="${2:?받을 폴더}"
mkdir -p "$dest"
ssh -o BatchMode=yes goosolar "cd ~/workshop/out/$src && stat -c '%s %n' *.mp4" | while read -r size name; do
  if [ -f "$dest/$name" ] && [ "$(stat -c %s "$dest/$name")" = "$size" ]; then
    echo "skip $name"; continue
  fi
  scp -q "goosolar:~/workshop/out/$src/$name" "$dest/$name" && echo "got  $name ($size bytes)"
done
echo "--- 규격"
for f in "$dest"/*.mp4; do
  printf '%s  ' "$(basename "$f")"
  ffprobe -v error -select_streams v:0 -show_entries stream=width,height:format=duration -of csv=p=0 "$f" | tr '\n' ' '; echo
done
dups=$(stat -c %s "$dest"/*.mp4 | sort | uniq -d)
if [ -n "$dups" ]; then echo "VERIFY FAIL: 같은 크기 파일 있음 ($dups) -> 섞였는지 확인"; exit 1; fi
echo "VERIFY OK: $(ls "$dest"/*.mp4 | wc -l)개, 크기 중복 없음"
