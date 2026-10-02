"""PreToolUse(Bash) 훅(2026-10-02 탐, F1 판정 E1): `mailbox.py send 헤르메스 ...`를 막는다.
이유: 우편은 헤르메스에게 닿지 않고 조용히 사라진다(cxo-db#242). 위임 채널의 정본은 hermes-delegate 스킬 "채널 고르기" 절.
받는이는 send 바로 뒤 첫 위치 인자(mailbox.py의 `to`)다. 다른 받는이와 `--from 헤르메스`는 통과.
파싱 실패는 통과(fail-open)."""
import json, re, sys
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
cmd = str((data.get("tool_input") or {}).get("command", ""))
m = re.search(r"mailbox\.py[\"']?\s+send\s+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
if m and m.group(1).strip("\"'") == "헤르메스":
    sys.stderr.write(
        "[헤르메스 우편 관문] 우편(mailbox.py send 헤르메스)은 헤르메스에 닿지 않고 조용히 사라집니다. "
        "즉시 실행·짧은 확인은 `scripts/hx.sh`로, 비동기·장시간은 solar-bible `tasks/pending/`에 지시서를 push하세요"
        "(hermes-delegate 스킬 \"채널 고르기\" 절).")
    sys.exit(2)
sys.exit(0)
