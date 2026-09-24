#!/usr/bin/env bash
# 구PC 작업실 크롬 5개(계정별 프로필)를 켜 둔다. 이미 떠 있는 것은 건드리지 않고, 응답 없는 포트만 다시 켠다.
# 2026-09-24 탐, 사장님 지시: 재부팅·크롬 종료 뒤에도 로그인 유지된 크롬이 자동으로 다시 떠야 한다.
# 로그인 정보는 프로필 폴더에 남아 있으므로 다시 켜도 로그인 상태가 유지된다.
# 등록(사용자 crontab, 관리자 권한 불필요):
#   @reboot sleep 60 && $HOME/workshop/start_chromes.sh
#   */5 * * * * $HOME/workshop/start_chromes.sh
# 결과 기록: ~/workshop/logs/start_chromes.log (다시 켠 것만 한 줄씩), ~/workshop/logs/chromes.last (마지막 점검 시각, 감시용)
set -u
W="$HOME/workshop"
# 포트:프로필 폴더 (계정 대장은 profiles/ACCOUNTS.md, 저장소에는 올리지 않음)
PROFILES="9222:flow-free1 9223:acct3 9224:acct4 9225:acct5 9226:acct2"
mkdir -p "$W/logs"
# 재부팅 직후 @reboot 실행과 5분 주기 실행이 같은 순간에 겹쳐 같은 크롬을 두 번 켰다(2026-09-24 재부팅 시험).
# 한 번에 하나만 돌게 잠근다. 이미 돌고 있으면 조용히 끝낸다.
exec 9>"$W/logs/start_chromes.lock"
flock -n 9 || exit 0
up=0
for pp in $PROFILES; do
  port=${pp%%:*}; prof=${pp#*:}
  if curl -s -m 3 "http://127.0.0.1:$port/json/version" >/dev/null; then
    up=$((up+1)); continue
  fi
  # 포트는 죽었는데 같은 프로필 크롬이 남아 있으면(멈춤) 정리하고 다시 켠다
  pkill -f "user-data-dir=$W/profiles/$prof " 2>/dev/null
  pkill -f "user-data-dir=$W/profiles/$prof$" 2>/dev/null
  rm -f "$W/profiles/$prof/SingletonLock" "$W/profiles/$prof/SingletonSocket" "$W/profiles/$prof/SingletonCookie"
  setsid nohup xvfb-run -a -s "-screen 0 1366x900x24" google-chrome \
    --user-data-dir="$W/profiles/$prof" --remote-debugging-port="$port" --remote-debugging-address=127.0.0.1 \
    --no-first-run --no-default-browser-check --lang=ko https://labs.google/fx/tools/flow \
    > "$W/logs/chrome-$prof.log" 2>&1 < /dev/null &
  echo "$(date '+%F %T') restarted $port ($prof)" >> "$W/logs/start_chromes.log"
  sleep 4
done
echo "$(date '+%F %T') up_before=$up/5" > "$W/logs/chromes.last"
