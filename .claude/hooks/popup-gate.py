"""PreToolUse(Bash|PowerShell) 훅(2026-10-02 탐, F1 판정 E4): 사장님 화면에 창을 띄우는 명령을 막는다(CLAUDE.md Windows 팝업 금지).
대상: 명령 자리의 notepad, cmd의 start, Start-Process notepad, os.startfile, explorer.exe <파일>, Invoke-Item/ii.
명령 자리 = 줄 처음 또는 `;` `&&` `||` `|` `&` `(` 뒤. start_chromes.sh, --start, session-start, restart, Start-Sleep 등은 통과.
한계: 따옴표 안 문자열은 구분하지 못해 `echo "; notepad"` 같은 드문 경우 오탐할 수 있다. 파싱 실패는 통과(fail-open)."""
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
POS = r"(?:^|[;&|(\n])\s*"
PATTERNS = [
    (POS + r"(?:\S*[\/])?notepad(?:\.exe)?(?=\s|$|[;&|)])", "notepad"),
    (POS + r"start(?:\.exe)?\s+\S", "start"),
    (r"\bcmd(?:\.exe)?\s+/[ck]\s+start\b", "cmd /c start"),
    (r"Start-Process\b[^;&|\n]*\bnotepad", "Start-Process notepad"),
    (r"\bos\.startfile\s*\(", "os.startfile"),
    (POS + r"(?:\S*[\/])?explorer(?:\.exe)?\s+\S", "explorer.exe"),
    (POS + r"(?:Invoke-Item|ii)\s+\S", "Invoke-Item"),
]
for pat, name in PATTERNS:
    if re.search(pat, cmd, re.IGNORECASE):
        sys.stderr.write(
            f"[Windows 팝업 관문] `{name}`은(는) 사장님 화면에 창을 띄웁니다(CLAUDE.md Windows 팝업 금지). "
            "파일 확인은 Read나 `head` 같은 파일 입출력으로 하세요. 창이 꼭 필요한 작업이면 먼저 사장님께 보고하세요.")
        sys.exit(2)
sys.exit(0)
