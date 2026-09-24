#!/usr/bin/env python3
"""PR에서 새로 추가된 줄에 개인정보(이메일)나 키가 섞여 있는지 검사한다.

왜 이 검사가 있나
-----------------
이 저장소는 공개다. 한 번 올라간 내용은 지워도 커밋 이력에 남는다.
사장님 지시(2026-09-24): 고객 회사명 노출은 괜찮지만 **고객 이메일 같은
개인정보와 내부 키는 각별히 막는다**. GitHub의 키 자동 차단(push
protection, 2026-09-24 켬)은 알려진 키 형식만 잡고 이메일은 잡지 않아서,
이메일은 이 검사가 맡고 키는 이중으로 본다.

무엇을 잡나
-----------
1. 이메일 주소: 아래 ALLOWED_EMAILS·ALLOWED_DOMAINS(사장님 본인·공용 예시
   주소)가 아니면 막는다. 이미지 파일명(logo@2x.png)은 이메일이 아니다.
2. 키 형태: 구글 API 키, 깃허브 토큰, 텔레그램 봇 토큰, OpenAI·Anthropic·
   Groq·NVIDIA 키, 슬랙 토큰, 개인 키 블록.

PR의 변경분(base와 head 사이 새로 추가된 줄)만 본다. 기존 줄까지 잡으면
관련 없는 PR마다 헛경보가 뜬다(check_writing_style.py와 같은 이유).

진짜 예시로 꼭 넣어야 하는 줄은 같은 줄에 `leak-check: allow`를 적으면
통과한다(쓴 사람이 의도했다는 표시가 diff에 남는다).

사용법: python scripts/check_public_leaks.py [base] [head]
기본값: base=origin/main, head=HEAD
"""
import re
import subprocess
import sys

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IMAGE_EXT = re.compile(r"\.(png|jpe?g|webp|gif|svg|avif)$", re.I)

# 사장님 본인 주소와 이미 공개된 운영 주소(2026-09-24 전체 이력 검사 기준).
ALLOWED_EMAILS = {
    "hansunghee7@gmail.com",
    "simon@paywork.io",
    "github-deploy@saegim-mcp.iam.gserviceaccount.com",
}
ALLOWED_DOMAINS = (
    "simplifier.co.kr",
    "simplifier.co",
    "anthropic.com",
    "users.noreply.github.com",
    "example.com",
    "example.org",
)

KEY_PATTERNS = {
    "구글 API 키": r"AIza[0-9A-Za-z_-]{35}",
    "깃허브 토큰": r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}",
    "텔레그램 봇 토큰": r"\b[0-9]{8,10}:AA[A-Za-z0-9_-]{33}\b",
    "OpenAI·Anthropic 키": r"\bsk-(ant-|proj-)?[A-Za-z0-9_-]{32,120}\b",
    "Groq 키": r"\bgsk_[A-Za-z0-9]{40,}",
    "NVIDIA 키": r"\bnvapi-[A-Za-z0-9_-]{40,}",
    "슬랙 토큰": r"\bxox[abprs]-[A-Za-z0-9-]{20,}",
    "개인 키 블록": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
KEYS = {name: re.compile(p) for name, p in KEY_PATTERNS.items()}

SELF_PATH = "scripts/check_public_leaks.py"
ALLOW_MARK = "leak-check: allow"


def email_allowed(addr):
    addr = addr.lower()
    if addr in ALLOWED_EMAILS:
        return True
    domain = addr.rsplit("@", 1)[1]
    return any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS)


def added_lines(base, head):
    """(파일 경로, 추가된 줄) 목록. 바이너리는 git이 빼 준다."""
    out = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", f"{base}...{head}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout
    path = None
    for line in out.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and not line.startswith("+++") and path:
            yield path, line[1:]


def mask(s):
    return s[:4] + "…" + f"({len(s)}자)"


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    problems = []
    for path, text in added_lines(base, head):
        if path == SELF_PATH or ALLOW_MARK in text:
            continue
        for addr in EMAIL.findall(text):
            if IMAGE_EXT.search(addr) or email_allowed(addr):
                continue
            problems.append(f"{path}: 허용 목록 밖 이메일 {mask(addr)}")
        for name, rx in KEYS.items():
            for m in rx.finditer(text):
                problems.append(f"{path}: {name} 형태 {mask(m.group(0))}")
    if problems:
        print("공개 저장소에 올리면 안 되는 값이 있습니다(값은 가려서 표시):")
        for p in sorted(set(problems)):
            print(" -", p)
        print("고객 이메일은 '외부 고객 1호' 같은 코드명으로, 키는 이름(환경변수)으로 바꾸세요.")
        print(f"꼭 필요한 예시라면 그 줄에 '{ALLOW_MARK}'를 적으세요.")
        sys.exit(1)
    print("개인정보·키 검사 통과")


if __name__ == "__main__":
    main()
