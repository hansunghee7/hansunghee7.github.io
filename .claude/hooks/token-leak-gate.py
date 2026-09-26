"""PreToolUse 훅(2026-09-27 탐, 사장님 지시): Bash/PowerShell·Write/Edit/MultiEdit 호출에
봇 토큰·API 키처럼 보이는 문자열이 원문 그대로 들어가면 실행 전에 막는다.

왜: 대화에 자격증명 원문이 반복 노출되면 세션 후반 Bash 전체가 "Credential Leakage" 안전분류기에
막히는 사고가 2026-09-27 하루에 두 번 재발했다(cxo-db#240). "토큰을 대화에 남기지 말자"가 메모리
파일에만 있으면 다음 세션이 또 잊는다(CLAUDE.md id:4e7b). 그 문자열이 명령·파일에 나타나는 시점
자체를 도구 관문에서 막는다.

한계(클라우드탐 검토 2026-09-26, 그대로 남김): 정규식 몇 종류만 겨냥 - Supabase/GCP 서비스 계정
키처럼 형태가 다른 비밀값은 못 잡는다. 채팅 답변 문장 자체(도구를 안 거치는 텍스트)는 이 훅으로
못 막는다. 탈출구가 자기신고식이라(로그만 남기고 검증은 안 함) 습관적으로 붙이면 무력화된다.
실전(실제 텔레그램 작업 중 안전분류기가 재발 안 하는지)은 아직 실측 안 됨 - 유닛테스트로만 확인.
예외: 내용에 "[자격증명 확인됨: 이유]"를 적으면 통과하되 사용 기록을 로그에 남긴다.
"""
import json, os, re, sys, time

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PATTERNS = [
    (re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,45}\b"), "텔레그램 봇 토큰"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI류 시크릿 키"),
    (re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{16,}\b"), "Stripe/WorkOS류 시크릿 키"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "GitHub 토큰"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), "구글 API 키"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "슬랙 토큰"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "JWT류 토큰(Supabase 등)"),
]

ESCAPE = "[자격증명 확인됨:"
LOG = os.environ.get("TOKEN_LEAK_GATE_LOG", os.path.join(os.path.dirname(__file__), "token-leak-gate.log"))


def scan_texts(texts):
    for text in texts:
        for pattern, label in PATTERNS:
            if pattern.search(text):
                return label
    return None


def collect_texts(tool, ti):
    if tool in ("Bash", "PowerShell"):
        return [str(ti.get("command", ""))]
    if tool == "Write":
        return [str(ti.get("content", ""))]
    if tool == "Edit":
        return [str(ti.get("old_string", "")), str(ti.get("new_string", ""))]
    if tool == "MultiEdit":
        out = []
        for e in ti.get("edits") or []:
            out.append(str(e.get("old_string", "")))
            out.append(str(e.get("new_string", "")))
        return out
    return []


def log_escape(tool, label):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "tool": tool, "label": label}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    tool = data.get("tool_name")
    if tool not in ("Bash", "PowerShell", "Write", "Edit", "MultiEdit"):
        return 0
    ti = data.get("tool_input") or {}
    texts = collect_texts(tool, ti)
    if not texts:
        return 0
    label = scan_texts(texts)
    if not label:
        return 0
    if any(ESCAPE in t for t in texts):
        log_escape(tool, label)
        return 0
    sys.stderr.write(
        f"[자격증명 원문 관문] {tool} 호출에 {label}처럼 보이는 문자열이 그대로 들어 있습니다. "
        "값을 직접 쓰지 말고 환경변수·.env 참조로 바꾸세요(예: $env:TOKEN, os.environ['TOKEN']). "
        "정말 필요하면 내용 어딘가에 \"[자격증명 확인됨: 이유]\"를 적고 다시 시도하세요(사용 기록이 남습니다). "
        "재발 사례: cxo-db#240, feedback_credential-text-triggers-bash-lockout.md."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
