#!/bin/bash
# PC와 노트북 등 여러 기기에서 클로드 코드로 이 저장소를 작업하기 때문에,
# 세션이 시작될 때마다 로컬이 origin/main보다 뒤처져 있지 않은지 먼저 확인한다.
# (실제 사고 사례: git fetch로 이미 삭제된 브랜치를 같이 요청했다가 fetch 전체가
# 조용히 실패해서, main이 34커밋 뒤처진 걸 한참 뒤에야 발견한 적이 있음.)
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# git worktree에서는 .git이 디렉터리가 아니라 파일이다(마야는 전용 worktree에서 작업). -d가 아니라 -e로 본다.
if [ ! -e .git ]; then
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

# 세션 의식은 스킬로 옮겨졌다(2026-09-20 구조 최적화). 스킬을 안 열고 진행하는 것을 막기 위해 매 세션 시작에 한 줄 상기시킨다.
echo "📌 세션 의식: 첫 메시지가 '하이~'면 .claude/skills/session-start, '바이~'면 session-end 스킬을 먼저 연다. 인수인계 블록은 요약하지 말고 원문 그대로 출력한다."

# 감시가 찾은 문제(꺼진 서비스, 실패한 주기 작업)를 세션 시작 때 보여 준다. 상태 파일이 없으면 조용히 통과.
if command -v python3 >/dev/null 2>&1; then PY=python3; elif command -v python >/dev/null 2>&1; then PY=python; else PY=""; fi
[ -n "$PY" ] && "$PY" "$(dirname "${BASH_SOURCE[0]}")/ops-status.py" 2>/dev/null

exit 0
