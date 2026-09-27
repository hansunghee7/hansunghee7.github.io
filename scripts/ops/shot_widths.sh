#!/usr/bin/env bash
# HTML 시안을 여러 화면 너비로 Edge 헤드리스 스크린샷 찍는 공용 헬퍼.
# 매번 python -m http.server를 손으로 새로 띄우고 끄는 걸 반복하다가, 정리(kill)
# 명령이 없거나(끝에 안 넣음) 있어도 겹겹이 이스케이프한 한 줄이 조용히 실패해서
# 좀비 서버 20개가 쌓인 사고 재발방지(2026-09-27, cxo-db 기록).
#
# trap으로 EXIT 시 무조건 서버를 끈다 — 스크린샷 단계에서 에러가 나도, 스크립트가
# 중간에 죽어도 서버는 반드시 정리된다(끝에 수동으로 taskkill 이어붙이는 것보다 안전).
#
# 사용: bash scripts/ops/shot_widths.sh <디렉터리> <html파일> <출력.png> [너비1 너비2 ...]
#   예: bash scripts/ops/shot_widths.sh /c/work/.../scratchpad carvit_shadcn.html out.png 320 360 480
set -euo pipefail

DIR="${1:?디렉터리 필요}"; HTML="${2:?html 파일 필요}"; OUT="${3:?출력 png 필요}"
shift 3
WIDTHS=("${@:-320 360 480}")
HEIGHT="${HEIGHT:-820}"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1]); s.close()')
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cd "$DIR"
python -m http.server "$PORT" >/dev/null 2>&1 &
SERVER_PID=$!

for i in $(seq 1 20); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && break
  sleep 0.2
done

TMPHTML="_shot_widths_$$.html"
{
  echo '<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#ddd;font:14px sans-serif;display:flex;gap:24px;padding:16px;align-items:flex-start}figure{margin:0}figcaption{font-weight:700;margin-bottom:6px}iframe{border:1px solid #999;background:#fff}</style>'
  for w in "${WIDTHS[@]}"; do
    echo "<figure><figcaption>${w}px</figcaption><iframe src=\"$HTML\" width=\"$w\" height=\"$HEIGHT\"></iframe></figure>"
  done
} > "$TMPHTML"

TOTAL_W=0
for w in "${WIDTHS[@]}"; do TOTAL_W=$((TOTAL_W + w + 24)); done

"$EDGE" --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1.5 --window-size="${TOTAL_W},$((HEIGHT+80))" \
  --virtual-time-budget=4000 --screenshot="$OUT" \
  "http://127.0.0.1:$PORT/$TMPHTML" 2>/dev/null

rm -f "$TMPHTML"
echo "완료: $OUT"
