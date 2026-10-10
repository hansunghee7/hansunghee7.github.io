#!/usr/bin/env python3
"""Stop 훅: 막혔다고 말하는 답변은 이번 턴에 프로세스표·절차 기록을 열어 봤을 때만 통과한다(사장님 지시 2026-10-04).

사고(2026-10-04 핏): 비즈(Vids) 내려받기에서 기록된 절차를 찾아보지 않고 추측으로 메뉴를 눌러 한참 막혔고, 사장님이 정답 경로를 보여 주셨다.
규칙(2026-10-11 좁힘: 이번 턴 도구 결과에 오류가 하나도 없으면 설명·보고 문장이라 통과): 마지막 답변에 '막힘' 표현(막혔·안 됩니다·실패했·멈췄 등)이 있으면, 이번 턴 도구 호출에
  프로세스표·GENERATION_PIPELINES·레시피·업무대장 같은 절차 기록을 읽거나 검색한 흔적이 있어야 한다.
  없으면 exit 2로 "먼저 프로세스표를 찾아 읽고 다시 답하라"고 알린다.
입력: stdin JSON(Claude Code Stop 훅). stop_hook_active면 통과(무한 루프 방지). 검사기 오류는 통과.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("commit_gate", Path(__file__).parent / "commit-gate.py")
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

# 2026-10-10 좁힘(사장님 승인 "추천대로 적용"): '되지 않·못 했·멈춰·못 받·막힌'은 통계·위험 안내·설명 문장에 오탐이 잦아 뺐다(한 세션 5회 재현).
# 코드 표기(백틱)는 판정에서 제외한다. 막힘을 직접 말하는 표현만 남긴다.
STUCK = re.compile(r"(막혔|막혀|안\s*됩니다|안\s*됐|실패했|실패합니다|멈췄|동작하지\s*않|열리지\s*않|내려받아지지)")
CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.S)
NOT_STUCK = re.compile(r"(막히지\s*않|막힘\s*없|막힌\s*곳\s*없|실패\s*없|문제\s*없)")
PROC_REF = re.compile(r"(프로세스표|GENERATION_PIPELINES|구PC_작업실_영상레시피|영상레시피|업무대장|DAILY_ROUTINE|session-start|hermes-delegate|ink-desk)")


def consulted(tools):
    for name, inp in tools:
        blob = name + " " + " ".join(str(v) for v in inp.values())
        if name in ("Read", "Grep", "Glob", "Bash", "PowerShell", "Skill") and PROC_REF.search(blob):
            return True
    return False


EXIT_ERR = re.compile(r"(?:Exit code|exit code|종료 코드)[:\s]*([1-9]\d*)")


def turn_has_error(path):
    """이번 턴(마지막 진짜 사용자 발화 이후) 도구 결과에 오류(is_error true 또는 0이 아닌 종료 코드)가 있는지. commit-gate.load_turn과 같은 턴 경계를 쓴다. 파싱 실패는 예외로 올려 통과시킨다."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    start = 0
    for i, ev in enumerate(events):
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        joined = chr(10).join(parts)
        if joined and "SYSTEM NOTIFICATION" not in joined and not joined.lstrip().startswith("<system-reminder>"):
            start = i
    for ev in events[start + 1:]:
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        if not isinstance(c, list):
            continue
        for p in c:
            if not isinstance(p, dict) or p.get("type") != "tool_result":
                continue
            if p.get("is_error") is True:
                return True
            body = p.get("content")
            if isinstance(body, list):
                body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
            if isinstance(body, str) and EXIT_ERR.match(body.lstrip()):
                return True
    return False


def check(text, tools, has_error=True):
    """has_error: 이번 턴 도구 결과에 오류가 하나라도 있는가. 없으면(설명·통계·보고 문장의 오탐) 통과한다(2026-10-11 좁힘)."""
    if not has_error:
        return None
    text = CODE.sub("", text)
    if not STUCK.search(text):
        return None
    stripped = NOT_STUCK.sub("", text)
    if not STUCK.search(stripped):
        return None
    if consulted(tools):
        return None
    return "no-process-lookup"


if __name__ == "__main__":
    for _s in (sys.stdin, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
        if data.get("stop_hook_active"):
            sys.exit(0)
        if data.get("_text") is not None:
            text, tools = data["_text"], data.get("_tools", [])
            err = data.get("_error", True)
        elif data.get("transcript_path"):
            text, tools = cg.load_turn(data["transcript_path"])
            err = turn_has_error(data["transcript_path"])
        else:
            sys.exit(0)
        verdict = check(text, tools, err) if text else None
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    if not verdict:
        sys.exit(0)
    print("막혔다는 말이 있지만 이번 턴에 절차 기록(프로세스표·GENERATION_PIPELINES·영상레시피·업무대장)을 찾아 읽은 흔적이 없습니다(사장님 지시 2026-10-04). "
          "추측으로 다시 시도하지 말고, 먼저 해당 프로세스표/절차 기록을 검색·열람해 기록된 단계와 대조한 뒤 어느 단계에서 막혔는지 다시 답하세요. "
          "기록에 없으면 그 사실을 적고 프로세스표에 추가하세요.", file=sys.stderr)
    sys.exit(2)
