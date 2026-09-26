"""PreToolUse 훅(2026-09-27 탐, 사장님 지시): Bash/PowerShell 명령에 봇 토큰·API 키처럼 보이는
문자열이 원문 그대로 들어가면 실행 전에 막는다.

왜: 대화에 자격증명 원문이 반복 노출되면 세션 후반 Bash 전체가 "Credential Leakage" 안전분류기에
막히는 사고가 2026-09-27 하루에 두 번 재발했다(cxo-db#240). "토큰을 대화에 남기지 말자"가 메모리
파일에만 있으면 다음 세션이 또 잊는다(CLAUDE.md id:4e7b) - 그 문자열이 명령줄에 나타나는 시점 자체를
도구 관문에서 막는다.
예외: 명령에 "[자격증명 확인됨: 이유]"를 적으면 통과(예: 재발급 직후 1회성 검증처럼 정말 필요한 경우).
"""
import json, re, sys

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PATTERNS = [
    (re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,45}\b"), "텔레그램 봇 토큰"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI류 시크릿 키"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "GitHub 토큰"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), "구글 API 키"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "슬랙 토큰"),
]


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if "[자격증명 확인됨:" in cmd:
        return 0
    for pattern, label in PATTERNS:
        if pattern.search(cmd):
            sys.stderr.write(
                f"[자격증명 원문 관문] 명령에 {label}처럼 보이는 문자열이 그대로 들어 있습니다. "
                "값을 셸에 직접 쓰지 말고 환경변수·.env 참조로 바꾸세요(예: $env:TOKEN, os.environ['TOKEN']). "
                "정말 필요하면 명령 끝에 \"[자격증명 확인됨: 이유]\"를 적고 다시 실행하세요. "
                "재발 사례: cxo-db#240, feedback_credential-text-triggers-bash-lockout.md."
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
