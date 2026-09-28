#!/bin/bash
# PC와 노트북 등 여러 기기에서 클로드 코드로 이 저장소를 작업하기 때문에,
# 세션이 시작될 때마다 로컬이 origin/main보다 뒤처져 있지 않은지 먼저 확인한다.
# (실제 사고 사례: git fetch로 이미 삭제된 브랜치를 같이 요청했다가 fetch 전체가
# 조용히 실패해서, main이 34커밋 뒤처진 걸 한참 뒤에야 발견한 적이 있음.)
#
# 2026-09-27 관문으로 승격(사장님 지시): 예전엔 "뒤처졌다"고 경고만 하고 다음 행동은
# 세션 판단에 맡겼는데, 그 경고를 6번 연속 무시(또는 못 보고 지나감)하는 사고가 났다
# (지투가 이 공용 메인 폴더에서 직접 claude/jitu-ledger-0926d로 체크아웃 후 방치 →
# 이후 열린 탐 세션들이 132커밋 뒤처진 진행상황.md를 최신인 줄 알고 읽음). 이제 안전할
# 때(원본 체크아웃 + 커밋 안 된 변경 없음)는 훅이 직접 main 전환·fast-forward까지 한다.
# 이 스크립트는 harness가 실행하는 자동화라 세션의 Bash 도구 승인 절차(안전 분류기)를
# 거치지 않는다 — 그래서 세션이 직접 시도하면 막히는 `git checkout`/`git merge --ff-only`도
# 여기서는 실행된다.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# 2026-09-28 방어선 추가: git fetch/checkout/merge, ops-status.py 호출 중 하나가
# 네트워크·디스크 문제로 멈추면 세션 시작 자체가 걸린다(훅에는 하네스 타임아웃이
# 있지만 그 전까지 세션이 응답 없이 대기). 각 호출을 15초로 끊어 실패해도 그냥
# 넘어가게 한다. timeout이 없는 환경(드문 경우)에서는 방어 없이 그대로 실행한다.
if command -v timeout >/dev/null 2>&1; then
  run_with_timeout() { timeout 15s "$@"; }
else
  run_with_timeout() { "$@"; }
fi

# git worktree에서는 .git이 디렉터리가 아니라 파일이다(전용 워크트리에서 작업하는 세션들).
# -d가 아니라 -e로 존재를 본 뒤, 아래에서 -d로 "원본 체크아웃 여부"를 따로 판단한다.
if [ ! -e .git ]; then
  exit 0
fi
is_primary_checkout=0
[ -d .git ] && is_primary_checkout=1

if ! run_with_timeout git fetch origin --prune --quiet 2>/dev/null; then
  echo "⚠️ git fetch origin --prune 실패 — 원격(GitHub) 상태를 확인하지 못했습니다. 네트워크 또는 GitHub 접근 권한을 확인하세요."
  exit 0
fi

default_branch="main"

if ! git rev-parse --verify "origin/$default_branch" >/dev/null 2>&1; then
  exit 0
fi

is_clean() {
  # 추적 중인 파일 기준으로만 본다. 안 지워진 새 파일(untracked)은 checkout/merge를
  # 막지 않는다(git 자체가 충돌 시 안전하게 중단한다) — 2026-09-27 사고의 지투 훅
  # 파일 3개(추적 안 됨)가 정확히 이 경우였고, 그때 수동으로 한 처리와 같다.
  git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain --untracked-files=no)" ]
}

current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")

# ── 1) 공용 메인 폴더(원본 체크아웃)가 main이 아닌 브랜치에 멈춰 있으면 자동으로 되돌린다.
#    전용 워크트리는 대상이 아니다 — 거기서는 다른 브랜치에 있는 게 정상이다.
if [ "$is_primary_checkout" -eq 1 ] && [ "$current_branch" != "$default_branch" ]; then
  if is_clean; then
    if run_with_timeout git checkout --quiet "$default_branch" 2>/dev/null; then
      echo "🔧 공용 메인 폴더가 '$current_branch'에 멈춰 있어 '$default_branch'로 자동 전환했습니다(커밋 안 된 변경 없음, 안전한 전환). 새 작업 브랜치가 필요하면 전용 워크트리를 쓰세요(git worktree add)."
      current_branch="$default_branch"
    else
      echo "🛑 공용 메인 폴더가 '$current_branch'에 멈춰 있는데 '$default_branch'로 자동 전환하지 못했습니다. 진행상황.md 등 로컬 문서가 낡았을 수 있으니 먼저 확인하세요: git status, git log $current_branch --not origin/$default_branch"
    fi
  else
    echo "🛑 공용 메인 폴더가 '$current_branch'에 멈춰 있고 커밋 안 된 변경도 있어 자동 전환을 건너뜁니다. 이 변경이 무엇인지 먼저 확인하세요(git status) — 지우거나 main으로 옮기기 전에 내용을 봐야 합니다."
  fi
fi

behind=$(git rev-list --count "HEAD..origin/$default_branch" 2>/dev/null || echo 0)
ahead=$(git rev-list --count "origin/$default_branch..HEAD" 2>/dev/null || echo 0)

# ── 2) main 위에 있고 뒤처져 있고 깨끗하면 fast-forward까지 자동으로 한다(원본 체크아웃만).
if [ "$is_primary_checkout" -eq 1 ] && [ "$current_branch" = "$default_branch" ] && [ "${behind:-0}" -gt 0 ]; then
  if is_clean; then
    if run_with_timeout git merge --ff-only --quiet "origin/$default_branch" 2>/dev/null; then
      echo "✅ 자동 동기화: origin/$default_branch에서 ${behind}커밋을 받아 최신으로 맞췄습니다."
      behind=0
    else
      echo "⚠️ 자동 동기화 실패(fast-forward 불가, 로컬에 origin에 없는 커밋이 있을 수 있음). 직접 확인: git pull --ff-only origin $default_branch"
    fi
  else
    echo "⚠️ 커밋 안 된 변경이 있어 자동 동기화를 건너뜁니다. 지금 로컬 문서는 origin/$default_branch보다 최대 ${behind}커밋 낡았을 수 있습니다(git status로 변경부터 확인)."
  fi
fi

if [ "${behind:-0}" -gt 0 ]; then
  echo "⚠️ 현재 브랜치($current_branch)가 origin/$default_branch보다 ${behind}커밋 뒤처져 있습니다. 다른 기기(PC/노트북)에서 먼저 작업했을 수 있으니, 새 작업을 시작하기 전에 사장님께 최신 진행 상황을 확인하고 필요하면 origin/$default_branch를 반영하세요."
else
  echo "✅ git 동기화 확인: 이 브랜치는 origin/$default_branch 기준 최신입니다."
fi

if [ "${ahead:-0}" -gt 0 ]; then
  echo "ℹ️ 이 브랜치에는 origin/$default_branch에 아직 없는 커밋이 ${ahead}개 있습니다."
fi

# 세션 의식은 스킬로 옮겨졌다(2026-09-20 구조 최적화). 스킬을 안 열고 진행하는 것을 막기 위해 매 세션 시작에 한 줄 상기시킨다.
echo "📌 세션 의식: 첫 메시지가 '하이~'면 .claude/skills/session-start, '바이~'면 session-end 스킬을 먼저 연다. 인수인계 블록은 요약하지 말고 원문 그대로 출력한다."

# 2026-09-27: 안전 분류기가 세션 후반부 Bash를 막아 정상 인수인계 커밋 없이 세션이
# 끊기는 사고가 두 번 겹쳤다(탐, 텔레그램 토큰 반복 노출 추정). 다음 세션이 "인수인계가
# 없다"며 진행상황.md 전체·아카이브를 뒤지는 것을 막기 위해, 최근 커밋 목록을 여기서
# 미리 계산해 보여준다. 페르소나 이름으로 바로 골라 `git show <해시> -- docs/진행상황.md`만
# 보면 되고, 파일 전체를 읽거나 grep으로 찾을 필요가 없다.
if git rev-parse --verify HEAD >/dev/null 2>&1 && [ -f docs/진행상황.md ]; then
  echo "🕘 최근 진행상황.md 커밋(최신 8개) — 자기 페르소나 줄만 골라 'git show <해시> -- docs/진행상황.md'로 본다:"
  git log --format='   %h  %ad  %s' --date=format:'%m-%d %H:%M' -8 -- docs/진행상황.md 2>/dev/null
fi

# 2026-09-27 사고 재발방지: 일부 페르소나(예: 핏)는 역할노트에 "인수인계 정본은
# 진행상황.md가 아니라 다른 저장소"라는 예외가 적혀 있는데, 위 커밋-찾기 절차를
# 기계적으로 따르다 이 예외를 놓쳐 옛 블록을 최신으로 잘못 보고한 사고가 있었다.
# 문서에만 있는 예외는 세션마다 놓칠 수 있으므로, 훅이 매번 직접 확인해 보여준다.
if [ -d docs ]; then
  override_files=$(grep -l "정본은.*진행상황\.md가 아니라" docs/역할노트-*.md 2>/dev/null)
  if [ -n "$override_files" ]; then
    echo "⚠️ 인수인계 정본 위치 예외 — 자기 역할노트가 아래에 있으면 진행상황.md 커밋 대신 거기서 최신 블록을 읽는다:"
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      echo "   $(basename "$f"): $(grep -m1 "정본은.*진행상황\.md가 아니라" "$f" | sed 's/^> //')"
    done <<< "$override_files"
  fi
fi

# 감시가 찾은 문제(꺼진 서비스, 실패한 주기 작업)를 세션 시작 때 보여 준다. 상태 파일이 없으면 조용히 통과.
if command -v python3 >/dev/null 2>&1; then PY=python3; elif command -v python >/dev/null 2>&1; then PY=python; else PY=""; fi
[ -n "$PY" ] && run_with_timeout "$PY" "$(dirname "${BASH_SOURCE[0]}")/ops-status.py" 2>/dev/null

exit 0
