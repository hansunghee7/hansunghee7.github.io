#!/usr/bin/env bash
# 탐이 비티(Antigravity/Gemini)에게 질문하고 답을 파일로 받는다(2026-10-01, N71).
# 사용: scripts/ops/ask_bt.sh <질문파일.md> [출력파일.md]
# 방식: 구PC(ssh goosolar)에서 solar 계정의 agy를 -p(출력만) 모드로 ag-test 폴더에서 실행한다.
#   - 상시 감시가 아니라 "필요할 때 소환해서 한 번 답 받고 끝" (비티 본인 제안, 한도 절약).
#   - 고객 정보·비밀값·가격·전략은 질문 파일에 넣지 않는다.
#   - 비티의 답은 가설이다. 채택 전에 탐이 실측한다.
set -eu

# 호출 기록(2026-10-02 사장님 방침: "필요할 때 그냥 부르고, 부르면서 하루 한도를 파악"). 한도 오류 문구가 처음 나오면 그 원문이 한도 정의가 된다.
LIMIT_RE='rate limit|usage limit|quota|RESOURCE_EXHAUSTED|429|limit reached|한도'
# 풀이 한도로 막혔나(2026-10-07): 답이 짧을 때만 stdout도 본다(정상 긴 답의 '한도' 오탐 방지), stderr는 항상 본다.
limit_blocked() {  # limit_blocked <출력파일>
  [ "$(cat "$1" 2>/dev/null | wc -c)" -lt 1500 ] && grep -Eiq "$LIMIT_RE" "$1" 2>/dev/null && return 0
  grep -Eiq "$LIMIT_RE" "$1.err" "$1.log" 2>/dev/null
}
calllog() {  # calllog <누구> <초> <rc> <출력파일>
  local f="${AGENT_CALLS_CSV:-/c/work/_ops/agent_calls.csv}"; [ -f "$f" ] || echo "time,who,sec,rc,out_bytes,limit_hit" > "$f"
  # 답 본문이 길면 정상 답에 "한도" 같은 단어가 섞여도 한도 신호로 보지 않는다(10/3 오탐, bt_loop.py와 같은 기준 1500바이트).
  local hit=0; [ "$(cat "$4" 2>/dev/null | wc -c)" -lt 1500 ] && grep -Eiq "$LIMIT_RE" "$4" "$4.log" 2>/dev/null && hit=1
  echo "$(date '+%F %T'),$1,$2,$3,$(wc -c < "$4" 2>/dev/null || echo 0),$hit" >> "$f"
  [ "$hit" = 1 ] && echo "⚠ 한도 신호 감지: $4 원문을 docs/processes에 기록할 것" >&2; return 0
}
Q="${1:?질문 파일 경로}"; OUT="${2:-/tmp/bt_reply_$(date +%Y%m%d_%H%M).md}"
# 모델(사장님 결정 10/3): 비티가 있는 이유는 다양성(다른 회사 모델의 눈)이라 **제미나이 먼저**, 한도가 막히면 Sonnet으로 자동 전환(페일오버).
# 둘은 한도 풀이 다르다(비티 = 제미나이 계열 공유, 비티-sonnet 별도). 근거 docs/processes/N114_비티모델비교_1003.md
# BT_MODEL=claude-sonnet-4-6 처럼 지정하면 그 모델만 쓴다.
QUOTA="$(dirname "$0")/quota.py"
# 2026-10-03(N120, 사장님 "무료 먼저, 막히면 GCP 크레딧"): 안티그래비티 제미나이가 막히면 Vertex 제미나이(개인 GCP 무료 크레딧)로 넘어가고, 그것도 하루 상한이면 Sonnet.
if [ -n "${BT_MODEL:-}" ]; then ORDER="sonnet"; [ "$BT_MODEL" = "gemini" ] && ORDER="gemini"; [ "$BT_MODEL" = "vertex" ] && ORDER="vertex"; [ "$BT_MODEL" = "router" ] && ORDER="router"; else ORDER="gemini router sonnet vertex"; fi  # 사장님 10/5: 무료(안티그래비티 제미나이 → 라우터 무료 풀) → 소넷 → GCP(Vertex 크레딧) 순으로 장애 전환
rc=99; LAST=""; USED=""
for M in $ORDER; do
  rm -f "$OUT.err" "$OUT.log"  # 앞 풀의 stderr가 다음 풀 판정에 섞이지 않게
  if [ "$M" = router ]; then  # 옴니라우터 무료 콤보(사장님 10/5 "옴니라우터 실사용"): 크레딧을 쓰기 전에 무료 풀로, 호출 기록 who=비티-라우터
    t0=$(date +%s); rc=0
    python -c "import sys; sys.path.insert(0, r'$(dirname "$0")'); import omni_gateway as g; r = g.chat(open(sys.argv[1], encoding='utf-8').read(), model='hermes-flash', agent='bt-test', max_tokens=4096, timeout=90, startup_wait=60); open(sys.argv[2], 'w', encoding='utf-8').write(r.get('text', '')); sys.exit(0 if r['ok'] else 1)" "$Q" "$OUT" 2>/dev/null || rc=$?
    calllog "비티-라우터" $(( $(date +%s)-t0 )) $rc "$OUT"
    if [ "$rc" = 0 ] && ! limit_blocked "$OUT"; then USED="옴니라우터 무료 콤보(hermes-flash)"; break; fi
    LAST="라우터 실패(rc=$rc) $(head -c 200 "$OUT" 2>/dev/null | tr '
' ' ')"; echo "라우터 건너뜀(rc=$rc)" >&2; rc=99; continue
  fi
  if [ "$M" = vertex ]; then  # 호출 기록·하루 상한은 ask_vertex.py가 관리(C:/work/_ops/vertex_usage.csv), 종료 코드 3 = 하루 상한
    t0=$(date +%s); rc=0; python "$(dirname "$0")/ask_vertex.py" "$Q" "$OUT" --who 비티 || rc=$?
    calllog "비티-vertex" $(( $(date +%s)-t0 )) $rc "$OUT"  # 10/5 사장님 지적: 비티 Vertex 호출이 who=탐으로만 찍혀 비티 사용량이 2회로 보였음 → 비티 몫으로 기록
    if [ "$rc" = 0 ] && ! limit_blocked "$OUT"; then USED="Vertex 제미나이(GCP 크레딧)"; break; fi
    LAST="Vertex 실패(rc=$rc) $(head -c 200 "$OUT" 2>/dev/null | tr '
' ' ')"; echo "Vertex 건너뜀(rc=$rc)" >&2; rc=99; continue
  fi
  if [ "$M" = gemini ]; then POOL=비티; MARG=""; else POOL=비티-sonnet; MARG="--model claude-sonnet-4-6"; fi
  # 한도 관문(10/3, 사장님 지시 "한도는 탐이 관리"): 막혔거나 주간 예산을 다 썼으면 이 모델은 건너뛴다.
  python "$QUOTA" check "$POOL" --who 탐 || continue
  t0=$(date +%s); rc=0
  ssh -o ConnectTimeout=15 -o BatchMode=yes goosolar "cd ~/carvit-pass/ag-test && timeout 240 ~/.local/bin/agy $MARG -p \"\$(printf '%s\\n\\n' '도구나 명령을 실행하지 말고 아래 텍스트만 읽고 글로만 답하라.'; cat)\"" < "$Q" > "$OUT" 2> "$OUT.err" || rc=$?
  calllog "$POOL" $(( $(date +%s)-t0 )) $rc "$OUT"
  # 한도 문구는 stderr("Individual quota reached ... Resets in 130h")에도 stdout 짧은 답에도 나온다. 대장에 막힘을 적고 다음 풀로 같은 호출 안에서 낙하한다(10/7).
  # 2026-10-11 실측: 큰 코드 카드(1.6만~3만 자)에서 비티(agy 헤드리스)가 '도구 권한을 물어볼 수 없어 자동 거절'로 답 없이 끝나는데 종료 코드는 0이었다(답 28바이트).
  # 빈 답(100바이트 미만) 또는 stderr의 'no output produced'는 실패로 보고 다음 풀로 낙하한다.
  EMPTY=0; [ "$(wc -c < "$OUT" 2>/dev/null || echo 0)" -lt 100 ] && EMPTY=1
  grep -q "no output produced" "$OUT.err" 2>/dev/null && EMPTY=1
  if limit_blocked "$OUT" || [ "$rc" != 0 ] || [ "$EMPTY" = 1 ]; then
    [ "$EMPTY" = 1 ] && [ "$rc" = 0 ] && rc=98
    MSG="$(grep -m1 -Ehio 'Individual quota reached.*|.*(rate limit|quota|RESOURCE_EXHAUSTED|429|한도).*' "$OUT.err" "$OUT" 2>/dev/null | head -1)"
    [ "$EMPTY" = 1 ] && MSG="${MSG:-빈 답(도구 권한 자동 거절 의심)}"
    LAST="$POOL 실패(rc=$rc) ${MSG:-원인 불명}"; LAST="${LAST:0:200}"
    limit_blocked "$OUT" && python "$QUOTA" hit "$POOL" "${MSG:-limit}"
    echo "$POOL 건너뜀: 다음 풀로 낙하" >&2; rc=99; continue
  fi
  USED="$POOL"; break
done
[ "$rc" = 99 ] && { echo "모든 풀 실패(종료 3). 마지막 오류: ${LAST:-한도 관문에서 전부 멈춤, python $QUOTA status 확인}" >&2; exit 3; }
echo "쓴 모델: $USED" >&2
# 어느 풀이 답했는지 결과 파일 맨 위에 한 줄 남긴다
{ echo "<!-- 답한 풀: $USED -->"; cat "$OUT"; } > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
echo "답 저장: $OUT ($(wc -c < "$OUT") bytes)"
