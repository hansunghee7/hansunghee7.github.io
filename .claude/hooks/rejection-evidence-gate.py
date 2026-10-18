"""PreToolUse(Write|Edit|MultiEdit|Bash|PowerShell) 훅(2026-10-18 노트, 사장님 지시 "리서치로 결론내지 말고 실측해서 결론낼 것"):
기각·하지 않기로 한 결정을 기록할 때 실측 증거를 같이 적게 한다.

사고: 10/12 Claude Code 채널을 "유휴 세션을 못 깨운다"(공식 이슈·리서치)로 '하지 않는 것'에 넣었고, 사장님이 세 번 물어도 다시 재지
않았다. 10/18 실측에서 1·5·15분 쉰 세션이 2~5초에 깨어났다(C:/work/_ops/chan-test). 결정이 기록되는 순간에 증거를 묻는다.

막는 것: 새로 쓰는 글(Write 내용, Edit의 새 줄, proc.py add/amend·mailbox.py send·gh issue create 명령 본문)에 기각 표현
(하지 않는 것·하지 않기로·기각·배제·채택하지 않·쓰지 않기로·드랍)이 있는데 같은 글에 `[실측: <로그·파일 경로나 숫자>]`도
`[실측 불가: <이유>]`도 없을 때. 실측 불가(되돌리기 어려운 위험·돈·계정 정지 등)는 이유를 적으면 통과하고 C:/work/_ops/rejection_log.jsonl에 남는다.
제외: 훅·시험 파일, 근거 이력 보존 문서, 이미 있던 줄(Edit에서 old에 있던 줄). 파싱 실패는 통과(fail-open)."""
import json
import os
import re
import sys
import time

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

LOG = os.environ.get("REJECTION_LOG", "C:/work/_ops/rejection_log.jsonl")
REJECT = re.compile(r"하지\s?않는\s?것|하지\s?않기로|기각|배제(?!적)|채택하지\s?않|채택\s?안\s?함|쓰지\s?않기로|드랍(?:한다|하기로|함)")
EVIDENCE = re.compile(r"\[실측\s*:\s*[^\]]{3,}\]")
NO_MEASURE = re.compile(r"\[실측\s*불가\s*:\s*([^\]]{4,})\]")
SKIP_PATH = re.compile(r"(\.claude[/\\]hooks[/\\]|[/\\]test_[^/\\]*$|CLAUDE_md_근거_이력|[/\\]_이력[/\\]|진행상황_아카이브|\.jsonl$)")
BASH_TARGET = re.compile(r"proc\.py\s+(?:add|amend)|mailbox\.py\s+send|gh\s+issue\s+(?:create|comment)")


def added_text(tool: str, ti: dict) -> tuple[str, str]:
    """(새로 들어가는 글, 대상 경로)."""
    path = str(ti.get("file_path", ""))
    if tool == "Write":
        return str(ti.get("content", "")), path
    if tool == "Edit":
        old = set(str(ti.get("old_string", "")).splitlines())
        return "\n".join(l for l in str(ti.get("new_string", "")).splitlines() if l not in old), path
    if tool == "MultiEdit":
        parts = []
        for e in ti.get("edits") or []:
            old = set(str(e.get("old_string", "")).splitlines())
            parts += [l for l in str(e.get("new_string", "")).splitlines() if l not in old]
        return "\n".join(parts), path
    cmd = str(ti.get("command", ""))
    return (cmd if BASH_TARGET.search(cmd) else ""), ""


def check(tool: str, ti: dict) -> tuple[str | None, str | None]:
    """(막을 이유, 실측 불가 사유). 둘 다 None이면 통과."""
    text, path = added_text(tool, ti)
    if not text or (path and SKIP_PATH.search(path)):
        return None, None
    m = REJECT.search(text)
    if not m:
        return None, None
    if EVIDENCE.search(text):
        return None, None
    nm = NO_MEASURE.search(text)
    if nm:
        return None, nm.group(1)
    line = next((l for l in text.splitlines() if REJECT.search(l)), "")[:120]
    return f"기각 표현 '{m.group(0)}'이 있는데 실측 증거가 없습니다: {line}", None


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        sys.exit(0)
    tool = str(data.get("tool_name", ""))
    ti = data.get("tool_input") or {}
    why, no_measure = check(tool, ti)
    if no_measure:
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "path": ti.get("file_path", ""),
                                    "no_measure": no_measure[:200]}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        sys.exit(0)
    if not why:
        sys.exit(0)
    sys.stderr.write(
        f"[기각 증거 관문] {why}. 사장님 지시(10/18): 리서치·문서·이슈로 결론내지 말고 실측해서 결론낸다. "
        "직접 재 본 결과를 같은 글에 `[실측: 로그·파일 경로나 숫자]`로 적으세요. 실측 자체가 되돌리기 어려운 위험(돈·계정 정지·자격증명 노출)이면 "
        "`[실측 불가: 이유]`를 적으면 통과하고 기록이 남습니다. 다시 볼 신호·날짜도 같이 적으세요(정본: 공정 카드 카빗DM #5).")
    sys.exit(2)


if __name__ == "__main__":
    main()
