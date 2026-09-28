#!/usr/bin/env bash
# UserPromptSubmit 훅 래퍼: python이 없으면 조용히 통과(exit 0). 판정 로직은 skill-nudge.py.
# 2026-09-28: PATH가 깨져 python 탐색·실행이 멈추면서 이 훅이 30초 타임아웃으로
# 죽어 개시어 안내가 안 뜬 사고가 있었다(PATH 버그는 별도로 고쳤음). 재발 방지로
# 내부 python 호출에도 10초 방어선을 건다 — 걸리면 안내를 못 띄우고 조용히
# 넘어가되(exit 0), 최소한 하네스 타임아웃(30초)까지 세션을 붙잡지는 않는다.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else exit 0; fi
if command -v timeout >/dev/null 2>&1; then
  timeout 10s "$PY" "$DIR/skill-nudge.py"
else
  "$PY" "$DIR/skill-nudge.py"
fi
exit 0
