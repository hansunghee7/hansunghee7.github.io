#!/usr/bin/env bash
# 미검증 초안, 첫 시험 뒤 확정. 아직 한 번도 실행하지 않았다(2026-10-02, 탐).
# 탐이 덱스(OpenAI Codex CLI)에게 작업 카드 1장을 주고 결과를 파일로 받는다. ask_bt.sh와 같은 "소환해서 한 번 받고 끝" 방식이다.
# 사용: scripts/ops/ask_dex.sh <작업카드.md> [출력파일.md]
# 원칙:
#   - 카드에는 고객 정보, 비밀값, 가격, 전략을 넣지 않는다.
#   - 실행은 비밀값이 없는 격리 폴더(DEX_WORKDIR)에서만 한다. 저장소 본 폴더에서 돌리지 않는다.
#   - 덱스의 결과는 diff와 종료 코드뿐이다. 판정은 탐이 한다.
#   - 영입 관문(학습 제외 확인 등)이 끝나기 전에는 실행하지 않는다: docs/덱스_영입_준비.md 1절.
set -eu
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
# 10/2 공식 문서 대조: 비대화형은 codex exec, 샌드박스는 read-only/workspace-write. 첫 시험 전까지는 미검증 초안.
cd "$WORKDIR"
timeout 600 codex exec --sandbox workspace-write "$(cat "$CARD")" > "$OUT"
echo "답 저장: $OUT ($(wc -c < "$OUT") bytes)"
echo "다음: git -C $WORKDIR diff 를 탐이 읽고 검사를 직접 다시 돌린다."
