#!/usr/bin/env python3
"""Stop 훅 `위임 관문`: 직접 손일(도구 호출)만 길게 이어지고 위임이 없는 구간을 잡는다.

근거(핏 세션 2026-10-11 실측): Bash 887회, Agent 0회, 덱스·비티 0회, 도구 출력의 약 80%가 Bash.
규칙: 직전 위임 기록 이후 구간에서 도구 호출 수 또는 도구 출력 글자 수가 임계를 넘고, 그 구간에 위임 기록이 없으면 동작한다.
위임 기록: Agent 호출, Bash/PowerShell 명령의 ask_dex.sh·ask_bt.sh·hx.sh·nohup·setsid 또는 run_in_background=true,
Monitor·CronCreate·ScheduleWakeup·SendMessage 호출.
환경변수: DELEGATION_CALLS(기본 100), DELEGATION_CHARS(기본 150000),
DELEGATION_GATE_MODE(warn 기본 | block), DELEGATION_GATE_PERSONAS(쉼표 목록, 비면 모든 세션),
DELEGATION_STATE_PATH(상태 파일, 기본 C:/work/_ops/delegation_gate_state.json).
같은 구간에서는 한 번만 동작한다(상태 파일에 session_id별 마지막 경고 호출 번호). 파싱 실패·전사 없음은 통과(fail-open).
"""
import json
import os
import re
import sys

DELEGATION_TOOLS = {"Agent", "Task", "Monitor", "CronCreate", "ScheduleWakeup", "SendMessage",
                    "mcp__scheduled-tasks__create_scheduled_task", "mcp__ccd_session_mgmt__send_message"}
DELEGATION_CMD = re.compile(r"ask_dex\.sh|ask_bt\.sh|hx\.sh|\bnohup\b|\bsetsid\b")
DEFAULT_STATE = "C:/work/_ops/delegation_gate_state.json"


def is_delegation(name, inp):
    if name in DELEGATION_TOOLS:
        return True
    if name in ("Bash", "PowerShell"):
        if inp.get("run_in_background") is True:
            return True
        return bool(DELEGATION_CMD.search(str(inp.get("command", ""))))
    return False


def _result_len(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(p.get("text", "")) for p in content if isinstance(p, dict))
    return 0


def analyze(path):
    """(전체 호출 수, 구간 시작 호출 번호, 구간 호출 수, 구간 출력 글자 수)."""
    total = 0
    seg_start = 0
    seg_calls = 0
    seg_chars = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            content = (ev.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for p in content:
                if not isinstance(p, dict):
                    continue
                if ev.get("type") == "assistant" and p.get("type") == "tool_use":
                    total += 1
                    if is_delegation(p.get("name", ""), p.get("input") or {}):
                        seg_start, seg_calls, seg_chars = total, 0, 0
                    else:
                        seg_calls += 1
                elif ev.get("type") == "user" and p.get("type") == "tool_result":
                    seg_chars += _result_len(p.get("content"))
    return total, seg_start, seg_calls, seg_chars


def persona_applies(data):
    names = [n.strip().lower() for n in os.environ.get("DELEGATION_GATE_PERSONAS", "").split(",") if n.strip()]
    if not names:
        return True
    envs = [f"{k}={v}" for k, v in os.environ.items() if k.upper().startswith(("PERSONA", "CLAUDE_PERSONA", "HERMES_PERSONA"))]
    hay = " ".join([str(data.get("cwd", "")), os.getcwd()] + envs).lower()
    return any(n in hay for n in names)


def _load_state(sp):
    try:
        with open(sp, encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def evaluate(data):
    """위반이면 (호출 수, 글자 수, 전체 호출 번호) 반환, 통과면 None. 상태 파일 갱신도 여기서 한다."""
    path = data.get("transcript_path")
    if not path or not os.path.exists(path) or not persona_applies(data):
        return None
    total, seg_start, calls, chars = analyze(path)
    max_calls = int(os.environ.get("DELEGATION_CALLS", "100"))
    max_chars = int(os.environ.get("DELEGATION_CHARS", "150000"))
    if calls < max_calls and chars < max_chars:
        return None
    sid = str(data.get("session_id") or os.path.basename(path))
    sp = os.environ.get("DELEGATION_STATE_PATH", DEFAULT_STATE)
    state = _load_state(sp)
    if int(state.get(sid, 0)) > seg_start:  # 이 구간에서 이미 경고함
        return None
    state[sid] = total
    try:
        os.makedirs(os.path.dirname(sp) or ".", exist_ok=True)
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass
    return calls, chars, total


def message(calls, chars):
    return (f"직접 손일이 {calls}회/약 {chars}자 이어졌습니다. 이 구간에 위임 기록(서브에이전트·덱스·비티·백그라운드 스크립트)이 없습니다. "
            "반복·수집·측정은 위임하고 판정만 하세요.\n"
            "예) Agent로 반복·수집 작업을 맡기고 요약만 받기 / bash ask_dex.sh·ask_bt.sh로 검증 맡기기\n"
            "예) 반복 명령은 스크립트로 묶어 run_in_background(또는 nohup)로 걸고 Monitor로 결과만 받기")


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
        res = evaluate(data)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)  # fail-open
    if not res:
        sys.exit(0)
    print(message(res[0], res[1]), file=sys.stderr)
    sys.exit(2 if os.environ.get("DELEGATION_GATE_MODE", "warn").lower() == "block" else 0)
