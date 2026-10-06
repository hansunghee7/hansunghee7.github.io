#!/usr/bin/env bash
# 지투 PO 루프 훅 래퍼(prompt|pre-bash|post-bash): python이 없으면 조용히 통과(exit 0). 로직은 jitu-loop.py.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else exit 0; fi
exec "$PY" "$DIR/jitu-loop.py" "$@"
