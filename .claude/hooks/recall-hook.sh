#!/usr/bin/env bash
# UserPromptSubmit 훅 래퍼: 사장님 메시지와 관련된 프로세스표 카드·사장님 과거 발화를 보여 준다(recall.py --hook). python이 없으면 조용히 통과.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else exit 0; fi
exec "$PY" "$DIR/../../scripts/ops/recall.py" --hook
