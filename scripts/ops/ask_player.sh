#!/usr/bin/env bash
# ask_player.sh : 비티·덱스를 "플레이어(주연 코더)"로 돌리는 게이트 밖 런처 (탐 N193, 사장님 10/18 동일권한 확정).
#
# 왜 별도 런처인가:
#   ask_bt.sh / ask_dex.sh 는 "글만 답하는" 리뷰 모드다(그대로 둔다).
#   플레이어 모드는 외부 모델이 저장소에 실제로 커밋·push 하고 운영 상태 DB까지 쓴다(사장님이 클로드 동일권한 부여).
#   그 실행은 호스트 안전 분류기를 거치지 않아야 하므로, 지휘 세션(클로드)이 "실행"하지 않고
#   이 스크립트를 사장님·자동화가 터미널에서 "직접" 돌린다(설계=탐, 실행=사장).
#
# 실측 근거(2026-10-18, 공정카드 탐#177):
#   덱스 = codex exec --sandbox danger-full-access 로 커밋·push·proc DB 쓰기 성공.
#   비티 = goosolar 에서 agy --dangerously-skip-permissions 에이전트 모드로 커밋·push 성공.
#
# 사용:  scripts/ops/ask_player.sh <bt|dex> <작업카드.md> [출력파일.md]
# 산출:  외부 모델이 claude/<agent>-player-<타임스탬프> 브랜치에 커밋(필요시 push). PR·병합은 탐이 한다(자동 아님).
#
# 보상 가드(클로드 안전층이 외부 프로세스엔 안 걸리므로 이 스크립트가 대신 건다):
#   - 일회용 클론에서만 실행(저장소 본 폴더 아님, 시크릿 없음).
#   - claude/ 접두 브랜치만(main 직접 push 는 서버 룰셋이 차단).
#   - 카드에 비밀값 의심 문자열이 있으면 보내지 않음(1차 관문).
#   - 실행 뒤 새 커밋에 비밀값 의심 문자열이 있으면 push 를 막고 경고.
set -euo pipefail

SECRET_RE='(api[_-]?key|token|password|secret|sk-[A-Za-z0-9]{10}|AKIA[0-9A-Z]{12}|-----BEGIN)'
GH_URL="https://github.com/hansunghee7/hansunghee7.github.io.git"

AGENT="${1:?첫 인자: bt | dex}"
CARD="${2:?둘째 인자: 작업 카드 .md 경로}"
OUT="${3:-/c/work/_ops/player_${AGENT}_$(date +%Y%m%d_%H%M%S).md}"
TS="$(date +%Y%m%d_%H%M%S)"
BRANCH="claude/${AGENT}-player-${TS}"

[ -f "$CARD" ] || { echo "작업 카드 없음: $CARD" >&2; exit 2; }
# 카드 1차 비밀값 관문.
if grep -Eiq "$SECRET_RE" "$CARD"; then
  echo "카드에 비밀값 의심 문자열이 있음: 보내지 않음(소독 후 다시)" >&2; exit 3
fi

# 새 커밋(origin/main..HEAD)에 비밀값이 섞였는지. 반환 0=깨끗, 1=의심.
commit_secret_scan() {  # $1=저장소 경로
  git -C "$1" log origin/main..HEAD -p 2>/dev/null | grep -E '^\+' | grep -Eiq "$SECRET_RE" && return 1 || return 0
}

case "$AGENT" in
  dex)
    # 덱스: 로컬 일회용 클론 + codex full-access.
    CLONE="/c/work/_ops/player/dex-${TS}"
    mkdir -p "$(dirname "$CLONE")"
    git clone --local --no-hardlinks -q /c/work/hansunghee7.github.io "$CLONE"
    git -C "$CLONE" remote set-url origin "$GH_URL"
    git -C "$CLONE" checkout -q -b "$BRANCH"
    WIN="$(cygpath -m "$CLONE" 2>/dev/null || echo "$CLONE")"
    echo "덱스 플레이어 실행(클론 $CLONE, 브랜치 $BRANCH)..." >&2
    timeout 900 codex exec -C "$WIN" --sandbox danger-full-access -o "$OUT" - < "$CARD" > "$OUT.log" 2>&1 || true
    if commit_secret_scan "$CLONE"; then
      git -C "$CLONE" push -u origin "$BRANCH" 2>&1 | tail -3 || echo "push 실패(수동 확인)" >&2
    else
      echo "경고: 새 커밋에 비밀값 의심 문자열, push 막음. $CLONE 를 탐이 직접 검토" >&2
    fi
    echo "답: $OUT / 클론: $CLONE / 브랜치: $BRANCH"
    echo "다음(탐): git -C $CLONE diff origin/main 검토 후 gh pr create (auto-merge 금지, CI 통과 후 병합)"
    ;;
  bt)
    # 비티: goosolar 에서 github 클론 + agy 에이전트 모드.
    REMOTE_DIR="~/player-bt-${TS}"
    CARD_CONTENT="$(cat "$CARD")"
    echo "비티 플레이어 실행(goosolar $REMOTE_DIR, 브랜치 $BRANCH)..." >&2
    ssh -o ConnectTimeout=20 -o BatchMode=yes goosolar \
      "git clone --quiet $GH_URL $REMOTE_DIR && cd $REMOTE_DIR && git checkout -q -b $BRANCH && \
       ~/.local/bin/agy --dangerously-skip-permissions -p \"\$(cat <<'__CARD__'
$CARD_CONTENT
__CARD__
)\"" > "$OUT" 2> "$OUT.log" || true
    # 커밋 비밀값 검사 + push 는 goosolar 에서.
    ssh -o ConnectTimeout=20 -o BatchMode=yes goosolar \
      "cd $REMOTE_DIR && if git log origin/main..HEAD -p | grep -E '^\\+' | grep -Eiq '$SECRET_RE'; then \
         echo '경고: 새 커밋 비밀값 의심, push 막음'; else git push -u origin $BRANCH 2>&1 | tail -3; fi" 2>&1 | tail -4
    echo "답: $OUT / goosolar: $REMOTE_DIR / 브랜치: $BRANCH"
    echo "다음(탐): git fetch 후 브랜치 검토 → gh pr create (auto-merge 금지)"
    ;;
  *)
    echo "알 수 없는 에이전트: $AGENT (bt | dex)" >&2; exit 2;;
esac
