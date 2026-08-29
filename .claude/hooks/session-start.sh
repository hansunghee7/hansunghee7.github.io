#!/bin/bash
# PC와 노트북 등 여러 기기에서 클로드 코드로 이 저장소를 작업하기 때문에,
# 세션이 시작될 때마다 로컬이 origin/main보다 뒤처져 있지 않은지 먼저 확인한다.
# (실제 사고 사례: git fetch로 이미 삭제된 브랜치를 같이 요청했다가 fetch 전체가
# 조용히 실패해서, main이 34커밋 뒤처진 걸 한참 뒤에야 발견한 적이 있음.)
set -uo pipefail

cd "$CLAUDE_PROJECT_DIR" || exit 0

if [ ! -d .git ]; then
  exit 0
fi

if ! git fetch origin --prune --quiet 2>/dev/null; then
  echo "⚠️ git fetch origin --prune 실패 — 원격(GitHub) 상태를 확인하지 못했습니다. 네트워크 또는 GitHub 접근 권한을 확인하세요."
  exit 0
fi

default_branch="main"

if ! git rev-parse --verify "origin/$default_branch" >/dev/null 2>&1; then
  exit 0
fi

current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")
behind=$(git rev-list --count "HEAD..origin/$default_branch" 2>/dev/null || echo 0)
ahead=$(git rev-list --count "origin/$default_branch..HEAD" 2>/dev/null || echo 0)

if [ "${behind:-0}" -gt 0 ]; then
  echo "⚠️ 현재 브랜치($current_branch)가 origin/$default_branch보다 ${behind}커밋 뒤처져 있습니다. 다른 기기(PC/노트북)에서 먼저 작업했을 수 있으니, 새 작업을 시작하기 전에 사장님께 최신 진행 상황을 확인하고 필요하면 origin/$default_branch를 반영하세요."
else
  echo "✅ git 동기화 확인: 이 브랜치는 origin/$default_branch 기준 최신입니다."
fi

if [ "${ahead:-0}" -gt 0 ]; then
  echo "ℹ️ 이 브랜치에는 origin/$default_branch에 아직 없는 커밋이 ${ahead}개 있습니다."
fi

exit 0
