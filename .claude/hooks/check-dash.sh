#!/usr/bin/env bash
# PostToolUse 훅 래퍼: python이 없으면 조용히 통과(exit 0). 검사 로직은 check-dash.py.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else exit 0; fi
exec "$PY" "$DIR/check-dash.py"
