#!/usr/bin/env bash
# 2026-10-02 탐: 첫 시험(yt_oauth_once.py F401) 통과 뒤 확정. 같은 호출 방식으로 30초, 토큰 7,008, 탐 재검사 통과.
# 탐이 덱스(OpenAI Codex CLI)에게 작업 카드 1장을 주고 결과를 파일로 받는다. ask_bt.sh와 같은 "소환해서 한 번 받고 끝" 방식이다.
# 사용: scripts/ops/ask_dex.sh <작업카드.md> [출력파일.md]
# 원칙:
#   - 카드에는 고객 정보, 비밀값, 가격, 전략을 넣지 않는다.
#   - 실행은 비밀값이 없는 격리 폴더(DEX_WORKDIR)에서만 한다. 저장소 본 폴더에서 돌리지 않는다.
#   - 덱스의 결과는 diff와 종료 코드뿐이다. 판정은 탐이 한다.
#   - 영입 관문(학습 제외 확인 등)이 끝나기 전에는 실행하지 않는다: docs/덱스_영입_준비.md 1절.
set -eu

# 호출 기록(2026-10-02 사장님 방침: "필요할 때 그냥 부르고, 부르면서 하루 한도를 파악"). 한도 오류 문구가 처음 나오면 그 원문이 한도 정의가 된다.
calllog() {  # calllog <누구> <초> <rc> <출력파일>
  local f=/c/work/_ops/agent_calls.csv; [ -f "$f" ] || echo "time,who,sec,rc,out_bytes,limit_hit" > "$f"
  local hit=0; grep -Eiq 'rate limit|usage limit|quota|RESOURCE_EXHAUSTED|429|limit reached|한도' "$4" "$4.log" 2>/dev/null && hit=1
  echo "$(date '+%F %T'),$1,$2,$3,$(wc -c < "$4" 2>/dev/null || echo 0),$hit" >> "$f"
  [ "$hit" = 1 ] && echo "⚠ 한도 신호 감지: $4 원문을 docs/processes에 기록할 것" >&2; return 0
}
CARD="${1:?작업 카드 파일 경로}"
OUT="${2:-/tmp/dex_reply_$(date +%Y%m%d_%H%M).md}"
WORKDIR="${DEX_WORKDIR:?격리 작업 폴더 경로를 DEX_WORKDIR에 지정}"
# 관문: 작업 폴더가 저장소 본 폴더이거나 비밀 폴더 아래면 멈춘다.
case "$WORKDIR" in
  */hansunghee7.github.io|*/hansunghee7.github.io/*|*secrets*) echo "격리 폴더가 아님: $WORKDIR" >&2; exit 2;;
esac
[ -d "$WORKDIR" ] || { echo "작업 폴더 없음: $WORKDIR" >&2; exit 2; }
# 비밀값 흔적이 있는 카드는 거부한다(완전한 검사는 아니다, 1차 관문).
if grep -Eiq '(api[_-]?key|token|password|secret|sk-[A-Za-z0-9])' "$CARD"; then
  echo "카드에 비밀값 의심 문자열이 있음: 보내지 않음" >&2; exit 3
fi
# 비대화형은 codex exec. 윈도우는 ~/.codex/config.toml의 [windows] sandbox = "unelevated"가 있어야
# workspace-write가 적용된다(없으면 read-only로 떨어져 명령이 전부 거절됨, 10/2 실측).
# 표준입력을 닫지 않으면 "Reading additional input from stdin"에서 끝없이 기다린다(10/2 실측) → < /dev/null.
cd "$WORKDIR"
t0=$(date +%s); rc=0
timeout 600 codex exec -C "$WORKDIR" --sandbox workspace-write -o "$OUT" "$(cat "$CARD")" < /dev/null > "$OUT.log" 2>&1 || rc=$?
calllog 덱스 $(( $(date +%s)-t0 )) $rc "$OUT"
echo "답 저장: $OUT ($(wc -c < "$OUT") bytes)"
echo "다음: git -C $WORKDIR diff 를 탐이 읽고 검사를 직접 다시 돌린다. 커밋은 바뀐 파일 이름을 하나씩 지정한다(테스트 산출물 섞임 방지, 10/2)."
