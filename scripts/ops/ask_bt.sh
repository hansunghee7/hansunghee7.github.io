#!/usr/bin/env bash
# 탐이 비티(Antigravity/Gemini)에게 질문하고 답을 파일로 받는다(2026-10-01, N71).
# 사용: scripts/ops/ask_bt.sh <질문파일.md> [출력파일.md]
# 방식: 구PC(ssh goosolar)에서 solar 계정의 agy를 -p(출력만) 모드로 ag-test 폴더에서 실행한다.
#   - 상시 감시가 아니라 "필요할 때 소환해서 한 번 답 받고 끝" (비티 본인 제안, 한도 절약).
#   - 고객 정보·비밀값·가격·전략은 질문 파일에 넣지 않는다.
#   - 비티의 답은 가설이다. 채택 전에 탐이 실측한다.
set -eu

# 호출 기록(2026-10-02 사장님 방침: "필요할 때 그냥 부르고, 부르면서 하루 한도를 파악"). 한도 오류 문구가 처음 나오면 그 원문이 한도 정의가 된다.
calllog() {  # calllog <누구> <초> <rc> <출력파일>
  local f=/c/work/_ops/agent_calls.csv; [ -f "$f" ] || echo "time,who,sec,rc,out_bytes,limit_hit" > "$f"
  local hit=0; grep -Eiq 'rate limit|usage limit|quota|RESOURCE_EXHAUSTED|429|limit reached|한도' "$4" "$4.log" 2>/dev/null && hit=1
  echo "$(date '+%F %T'),$1,$2,$3,$(wc -c < "$4" 2>/dev/null || echo 0),$hit" >> "$f"
  [ "$hit" = 1 ] && echo "⚠ 한도 신호 감지: $4 원문을 docs/processes에 기록할 것" >&2; return 0
}
Q="${1:?질문 파일 경로}"; OUT="${2:-/tmp/bt_reply_$(date +%Y%m%d_%H%M).md}"
t0=$(date +%s); rc=0
ssh -o ConnectTimeout=15 -o BatchMode=yes goosolar 'cd ~/carvit-pass/ag-test && timeout 240 ~/.local/bin/agy -p "$(cat)"' < "$Q" > "$OUT" || rc=$?
calllog 비티 $(( $(date +%s)-t0 )) $rc "$OUT"
echo "답 저장: $OUT ($(wc -c < "$OUT") bytes)"
