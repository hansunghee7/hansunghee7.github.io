#!/usr/bin/env python3
"""지투 PO 성장 루프 훅(2026-10-06 사장님 지시: 보강 4·2·3·1을 1회성이 아니라 루프로, 문서와 훅에 적용).
방법은 docs/지투_PO_성장루프.md, 기록 도구는 scripts/ops/jitu_po.py. 이 훅은 "다음 바퀴가 돌게" 하는 세 가지 결정적 지점만 맡는다(키워드 해석은 하지 않는다, CLAUDE#4e7b).

모드(인자):
  prompt     UserPromptSubmit: 사장님이 "하이 지투"처럼 지투를 부르며 시작하면, 기한이 지난 루프 항목(열린 검사 공백, 7일 넘게 안 잰 지표,
             분류 안 한 고객 신호, 점검일 지난 예측)을 한 번에 보여 준다. 기한 지난 것이 없으면 아무것도 출력하지 않는다.
  pre-bash   PreToolUse(Bash): `gh pr checks ... | ...` 로 파이프를 붙인 채 같은 명령에서 `gh pr merge`를 하면 막는다(exit 2).
             이유: 파이프가 종료 코드를 가려 CI가 실패여도 병합이 실행된다(2026-10-06 지투, simplifier-saegim#558 사고, 보강 4의 첫 사례).
  post-bash  PostToolUse(Bash): 지투 세션에서 `gh pr merge`가 병합되면 "예측 한 줄과 점검일을 남겨라"(보강 1),
             `git revert`·`git reset --hard`·`gh pr revert`를 하면 "검사 공백을 남겨라"(보강 4)를 상기시킨다(막지 않는다).
지투 세션 판정: 트랜스크립트의 첫 사용자 발화에 '지투'가 있을 때(queue-gate.py와 같은 방식).
입력: stdin JSON(Claude Code 훅 규격). 검사기 오류는 통과한다.
"""
import json
import os
import re
import subprocess
import sys

try:
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "..", "scripts", "ops", "jitu_po.py")
GREETING = re.compile(r"^\s*(하이|안녕)\s*[~～〜]?\s*(지투)\b")


def bare_cmd(cmd):
    """heredoc 본문과 따옴표 안 글자를 지운 사본(popup-gate.py와 같은 방식: jq 식 안의 | 를 파이프로 오인하지 않으려고)."""
    b = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", " ", cmd, flags=re.S)
    b = re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", "''", b)
    return re.sub(r"\d*>&\d+|&>>?", " ", b)  # `2>&1`의 &를 명령 연결로 오인하지 않게 지운다(실제 사고 명령이 `--watch 2>&1 | tail`이었다)


def unsafe_merge(cmd):
    """같은 명령에 gh pr merge가 있고, 그 앞의 gh pr checks 줄에 파이프(`|`, `||` 제외)가 붙어 있으면 True."""
    b = bare_cmd(cmd)
    if not re.search(r"\bgh\s+pr\s+merge\b", b):
        return False
    for m in re.finditer(r"\bgh\s+pr\s+checks\b([^\n;&]*)", b):
        if re.search(r"(?<!\|)\|(?!\|)", m.group(1)):
            return True
    return False


def first_user_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") != "user":
                    continue
                c = ev.get("message", {}).get("content", [])
                parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                joined = "\n".join(parts)
                if joined and "SYSTEM NOTIFICATION" not in joined and not joined.lstrip().startswith("<system-reminder>"):
                    return joined
    except Exception:
        return ""
    return ""


def is_jitu(data):
    if os.environ.get("JITU_LOOP_FORCE_JITU") == "1":
        return True
    return "지투" in first_user_text(data.get("transcript_path", "") or "")


def run_due():
    try:
        r = subprocess.run([sys.executable, TOOL, "due", "--quiet"], capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0

    if mode == "prompt":
        if GREETING.match(str(data.get("prompt", ""))):
            out = run_due()
            if out:
                print(out)
        return 0

    cmd = str((data.get("tool_input") or {}).get("command", ""))

    if mode == "pre-bash":
        if unsafe_merge(cmd):
            sys.stderr.write(
                "[병합 안전 관문] `gh pr checks ... | ...` 처럼 파이프를 붙이면 종료 코드가 가려져 CI가 실패여도 `gh pr merge`가 실행됩니다"
                "(2026-10-06 simplifier-saegim#558 사고). 파이프 없이 `gh pr checks <번호> --watch && gh pr merge <번호> --squash` 로 쓰거나, "
                "`gh pr checks <번호> --json name,state` 결과를 따로 읽고 실패가 0일 때만 병합하세요. 출력을 줄이고 싶으면 `>/dev/null`로 돌리고 "
                "상태는 --json으로 읽습니다.")
            return 2
        return 0

    if mode == "post-bash":
        b = bare_cmd(cmd)
        msg = ""
        if re.search(r"\bgh\s+pr\s+merge\b", b):
            resp = str(data.get("tool_response", "")).lower()
            if "merged" in resp or "tool_response" not in data:
                msg = ("[루프 상기, 보강 1] 병합했습니다. 이 변경으로 무엇이 얼마나 바뀔지 한 줄과 점검일을 남기세요: "
                       "python scripts/ops/jitu_po.py predict add --change \"...\" --expect \"...\" --metric \"...\" --check-on YYYY-MM-DD "
                       "(사소한 문구·정리는 생략해도 됩니다. 점검일이 오면 predict check로 실제 값을 적습니다.)")
        elif re.search(r"\bgit\s+revert\b|\bgit\s+reset\s+--hard\b|\bgh\s+pr\s+revert\b", b):
            msg = ("[루프 상기, 보강 4] 되돌리기를 했습니다. 무엇이 깨졌고 어떤 검사가 없었는지, 추가한 검사(훅·테스트·프로세스표 단계)를 짝으로 남기세요: "
                   "python scripts/ops/jitu_po.py gap add --what \"...\" --missing \"없던 검사\" --added \"추가한 검사\"")
        if msg and is_jitu(data):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
