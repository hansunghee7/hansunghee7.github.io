#!/usr/bin/env python3
"""goosolar에 SSH로 접속해 구글 워크스페이스 계정으로 로그인된 공식 Gemini CLI(@google/gemini-cli)에
비대화형으로 질문을 던지고 답을 받는다(2026-09-28 실측 확인).

기존 제미나이 API(7hansunghee 등 무료 프로젝트 키, GOOGLE_API_KEY)와는 완전히 다른 계정·다른 경로다:
  - 이 스크립트: 사장님의 구글 워크스페이스 계정으로 Sign in with Google 로그인(무료 API 키 아님).
    Antigravity(agy)와도 다른 제품이라 그쪽 "Individual quota"(daily-cloudcode-pa.googleapis.com)와 무관하다.
  - 로그인은 최초 1회 사람이 직접 해야 한다(hermes-delegate 위임 금지 원칙과 같은 이유).
    이미 goosolar에 로그인돼 있으면(~/.gemini/oauth_creds.json 등) 이 스크립트는 그대로 재사용만 한다.
  - 워크스페이스 계정 쿼터가 무료 개인용보다 넉넉한지는 아직 하루치 실측뿐이라 확정 아님 — 계속 지켜볼 것.

사용법:
  python gemini_cli_ask.py "질문 내용"
  python gemini_cli_ask.py --file question.txt [--out answer.md]
  echo "질문" | python gemini_cli_ask.py -

종료 코드: 0=성공, 1=인자 오류, 2=SSH/CLI 실패(stderr에 원문 남김), 3=응답이 빈 문자열(성공했다고 속이지 않음).
"""
import subprocess
import sys

SSH_HOST = "goosolar"
WORKDIR = "~/gemini-web-test"  # 최초 로그인 때 "trust this folder" 승인해둔 폴더 — 다른 폴더면 신뢰 승인부터 다시 해야 함
NODE_BIN = "$HOME/.nvm/versions/node/v24.21.0/bin"
TIMEOUT_S = 120


def ask(prompt: str) -> str:
    if not prompt.strip():
        raise ValueError("빈 질문은 보내지 않는다")
    # 원격 셸(bash)에 작은따옴표로 감싸 넘긴다(POSIX sh 표준 이스케이프: 내부 작은따옴표만 처리).
    escaped = prompt.replace("'", "'\\''")
    remote_cmd = f'export PATH="{NODE_BIN}:$PATH"; cd {WORKDIR} && gemini -p \'{escaped}\''
    r = subprocess.run(
        ["ssh", SSH_HOST, remote_cmd],
        capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT_S,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ssh/gemini 실패(exit {r.returncode}): {r.stderr.strip()[:500]}")
    answer = r.stdout.strip()
    if not answer:
        raise RuntimeError(f"응답이 비어 있음(성공으로 위장 안 함). stderr: {r.stderr.strip()[:300]}")
    return answer


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = args[i + 1]
        del args[i:i + 2]
    if args[0] == "--file":
        prompt = open(args[1], encoding="utf-8").read()
    elif args[0] == "-":
        prompt = sys.stdin.read()
    else:
        prompt = args[0]

    try:
        answer = ask(prompt)
    except subprocess.TimeoutExpired:
        print(f"실패: {TIMEOUT_S}초 안에 응답 없음", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 1

    if out_path:
        open(out_path, "w", encoding="utf-8").write(answer)
        print(f"OK -> {out_path} ({len(answer)}자)")
    else:
        print(answer)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
