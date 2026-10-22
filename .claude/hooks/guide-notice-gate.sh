#!/usr/bin/env bash
# PreToolUse 훅 래퍼: python이 없으면 조용히 통과(exit 0). 로직은 guide-notice-gate.py.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else exit 0; fi
# 한국어 Windows 기본 코드페이지(cp949)로 차단문이 깨지는 것을 막는다(카빗DM 3차 항목 6·19, 지투·노트 관찰).
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
exec "$PY" "$DIR/guide-notice-gate.py"
