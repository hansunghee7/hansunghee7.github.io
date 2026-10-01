#!/usr/bin/env bash
# 탐이 비티(Antigravity/Gemini)에게 질문하고 답을 파일로 받는다(2026-10-01, N71).
# 사용: scripts/ops/ask_bt.sh <질문파일.md> [출력파일.md]
# 방식: 구PC(ssh goosolar)에서 solar 계정의 agy를 -p(출력만) 모드로 ag-test 폴더에서 실행한다.
#   - 상시 감시가 아니라 "필요할 때 소환해서 한 번 답 받고 끝" (비티 본인 제안, 한도 절약).
#   - 고객 정보·비밀값·가격·전략은 질문 파일에 넣지 않는다.
#   - 비티의 답은 가설이다. 채택 전에 탐이 실측한다.
set -eu
Q="${1:?질문 파일 경로}"; OUT="${2:-/tmp/bt_reply_$(date +%Y%m%d_%H%M).md}"
ssh -o ConnectTimeout=15 -o BatchMode=yes goosolar 'cd ~/carvit-pass/ag-test && timeout 240 ~/.local/bin/agy -p "$(cat)"' < "$Q" > "$OUT"
echo "답 저장: $OUT ($(wc -c < "$OUT") bytes)"
