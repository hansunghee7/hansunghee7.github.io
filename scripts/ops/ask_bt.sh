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
  # 답 본문이 길면 정상 답에 "한도" 같은 단어가 섞여도 한도 신호로 보지 않는다(10/3 오탐, bt_loop.py와 같은 기준 1500바이트).
  local hit=0; [ "$(cat "$4" 2>/dev/null | wc -c)" -lt 1500 ] && grep -Eiq 'rate limit|usage limit|quota|RESOURCE_EXHAUSTED|429|limit reached|한도' "$4" "$4.log" 2>/dev/null && hit=1
  echo "$(date '+%F %T'),$1,$2,$3,$(wc -c < "$4" 2>/dev/null || echo 0),$hit" >> "$f"
  [ "$hit" = 1 ] && echo "⚠ 한도 신호 감지: $4 원문을 docs/processes에 기록할 것" >&2; return 0
}
Q="${1:?질문 파일 경로}"; OUT="${2:-/tmp/bt_reply_$(date +%Y%m%d_%H%M).md}"
# 모델(사장님 결정 10/3): 비티가 있는 이유는 다양성(다른 회사 모델의 눈)이라 **제미나이 먼저**, 한도가 막히면 Sonnet으로 자동 전환(페일오버).
# 둘은 한도 풀이 다르다(비티 = 제미나이 계열 공유, 비티-sonnet 별도). 근거 docs/processes/N114_비티모델비교_1003.md
# BT_MODEL=claude-sonnet-4-6 처럼 지정하면 그 모델만 쓴다.
QUOTA="$(dirname "$0")/quota.py"
# 2026-10-03(N120, 사장님 "무료 먼저, 막히면 GCP 크레딧"): 안티그래비티 제미나이가 막히면 Vertex 제미나이(개인 GCP 무료 크레딧)로 넘어가고, 그것도 하루 상한이면 Sonnet.
if [ -n "${BT_MODEL:-}" ]; then ORDER="sonnet"; [ "$BT_MODEL" = "gemini" ] && ORDER="gemini"; [ "$BT_MODEL" = "vertex" ] && ORDER="vertex"; [ "$BT_MODEL" = "router" ] && ORDER="router"; else ORDER="gemini router vertex sonnet"; fi
rc=99
for M in $ORDER; do
  if [ "$M" = router ]; then  # 옴니라우터 무료 콤보(사장님 10/5 "옴니라우터 실사용"): 크레딧을 쓰기 전에 무료 풀로, 호출 기록 who=비티-라우터
    t0=$(date +%s); rc=0
    python -c "import sys; sys.path.insert(0, r'$(dirname "$0")'); import omni_gateway as g; r = g.chat(open(sys.argv[1], encoding='utf-8').read(), model='hermes-flash', agent='bt-test', max_tokens=4096, timeout=90, startup_wait=60); open(sys.argv[2], 'w', encoding='utf-8').write(r.get('text', '')); sys.exit(0 if r['ok'] else 1)" "$Q" "$OUT" 2>/dev/null || rc=$?
    calllog "비티-라우터" $(( $(date +%s)-t0 )) $rc "$OUT"
    if [ "$rc" = 0 ]; then echo "쓴 모델: 옴니라우터 무료 콤보(hermes-flash)" >&2; break; fi
    echo "라우터 건너뜀(rc=$rc)" >&2; rc=99; continue
  fi
  if [ "$M" = vertex ]; then  # 호출 기록·하루 상한은 ask_vertex.py가 관리(C:/work/_ops/vertex_usage.csv), 종료 코드 3 = 하루 상한
    t0=$(date +%s); rc=0; python "$(dirname "$0")/ask_vertex.py" "$Q" "$OUT" --who 비티 || rc=$?
    calllog "비티-vertex" $(( $(date +%s)-t0 )) $rc "$OUT"  # 10/5 사장님 지적: 비티 Vertex 호출이 who=탐으로만 찍혀 비티 사용량이 2회로 보였음 → 비티 몫으로 기록
    if [ "$rc" = 0 ]; then echo "쓴 모델: Vertex 제미나이(GCP 크레딧)" >&2; break; fi
    echo "Vertex 건너뜀(rc=$rc)" >&2; rc=99; continue
  fi
  if [ "$M" = gemini ]; then POOL=비티; MARG=""; else POOL=비티-sonnet; MARG="--model claude-sonnet-4-6"; fi
  # 한도 관문(10/3, 사장님 지시 "한도는 탐이 관리"): 막혔거나 주간 예산을 다 썼으면 이 모델은 건너뛴다.
  python "$QUOTA" check "$POOL" --who 탐 || continue
  t0=$(date +%s); rc=0
  ssh -o ConnectTimeout=15 -o BatchMode=yes goosolar "cd ~/carvit-pass/ag-test && timeout 240 ~/.local/bin/agy $MARG -p \"\$(cat)\"" < "$Q" > "$OUT" 2> "$OUT.err" || rc=$?
  calllog "$POOL" $(( $(date +%s)-t0 )) $rc "$OUT"
  # 한도 오류는 stderr에만 나온다("Individual quota reached ... Resets in 130h"). 대장에 막힘을 적고 다음 모델로 넘어간다.
  if grep -q "quota reached\|RESOURCE_EXHAUSTED" "$OUT.err" 2>/dev/null; then
    python "$QUOTA" hit "$POOL" "$(grep -m1 -o 'Individual quota reached.*' "$OUT.err")"; continue
  fi
  echo "쓴 모델: $POOL" >&2; break
done
[ "$rc" = 99 ] && { echo "모든 모델이 한도 관문에서 멈춤: python $QUOTA status 로 확인" >&2; exit 4; }
echo "답 저장: $OUT ($(wc -c < "$OUT") bytes)"
