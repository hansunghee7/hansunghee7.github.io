#!/usr/bin/env python3
"""Stop 훅 `컨텍스트 가드`: 컨텍스트 사용 비율이 60% 이상이면 압축 준비를 안내한다(공정 카드 공용-오케스트레이션 #4).

컨텍스트 사용량 = 전사의 마지막 assistant 메시지 usage (input + cache_read + cache_creation 토큰).
비율 = 사용량 / CONTEXT_WINDOW_TOKENS(기본 1000000). 60% 이상에서 5% 단계마다 세션당 한 번만 안내한다.
같은 시점에 최근 30회 도구 호출 중 25회 이상이 직접 손일(Bash·PowerShell·Edit·Write·MultiEdit)이고 위임 기록이 없으면 한 줄을 더 낸다.
환경변수: CONTEXT_WINDOW_TOKENS, CONTEXT_GUARD_STATE_PATH(기본 C:/work/_ops/context_guard_state.json),
CONTEXT_GUARD_MODE(warn 기본 | block: 종료 코드 2로 에이전트 눈에 보이게 함).
파싱 실패·usage 없음은 조용히 통과(fail-open). 세션을 막지 않는다.
"""
import json
import os
import re
import sys

DEFAULT_STATE = "C:/work/_ops/context_guard_state.json"
HAND_TOOLS = {"Bash", "PowerShell", "Edit", "Write", "MultiEdit"}
DELEGATION_TOOLS = {"Agent", "Task", "Monitor", "CronCreate", "ScheduleWakeup", "SendMessage",
                    "mcp__scheduled-tasks__create_scheduled_task", "mcp__ccd_session_mgmt__send_message"}
DELEGATION_CMD = re.compile(r"ask_dex\.sh|ask_bt\.sh|hx\.sh|\bnohup\b|\bsetsid\b|ask_vertex\.py|vertex_research\.py|gemini_route\.py|api_run\.py|credit_run\.py|orch_wait\.py|\bclaude\s+-p\b|--cloud\b")
START_RATIO = 0.60
STEP = 5
WINDOW = 30
HAND_MIN = 25


def is_delegation(name, inp):
    if name in DELEGATION_TOOLS:
        return True
    if name in ("Bash", "PowerShell"):
        return inp.get("run_in_background") is True or bool(DELEGATION_CMD.search(str(inp.get("command", ""))))
    return False


def scan(path):
    """(마지막 usage 합계 또는 None, 최근 30회 도구 호출 [(name, is_delegation)])."""
    usage = None
    calls = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if not isinstance(ev, dict) or ev.get("type") != "assistant":
                continue
            m = ev.get("message") or {}
            u = m.get("usage")
            if isinstance(u, dict):
                try:
                    tot = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                except Exception:
                    tot = 0
                if tot > 0:
                    usage = tot
            c = m.get("content")
            if isinstance(c, list):
                for p in c:
                    if isinstance(p, dict) and p.get("type") == "tool_use":
                        name = p.get("name", "")
                        calls.append((name, is_delegation(name, p.get("input") or {})))
                calls = calls[-WINDOW:]
    return usage, calls


def window_size():
    try:
        v = int(os.environ.get("CONTEXT_WINDOW_TOKENS", "1000000"))
        return v if v > 0 else 1000000
    except Exception:
        return 1000000


def level_of(ratio):
    """60% 이상이면 5% 단계 값(60, 65, ...), 아니면 0."""
    if ratio < START_RATIO:
        return 0
    return int(round(ratio * 100, 6) // STEP * STEP)


def hand_heavy(calls):
    if len(calls) < WINDOW:
        return False
    if any(d for _, d in calls):
        return False
    return sum(1 for n, _ in calls if n in HAND_TOOLS) >= HAND_MIN


def load_state(sp):
    try:
        with open(sp, encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def save_state(sp, state):
    try:
        os.makedirs(os.path.dirname(sp) or ".", exist_ok=True)
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def evaluate(data):
    """안내할 문구 목록(없으면 빈 목록). 상태 파일 갱신도 여기서 한다."""
    path = data.get("transcript_path")
    if not path or not os.path.exists(path):
        return []
    usage, calls = scan(path)
    if not usage:
        return []
    ratio = usage / window_size()
    lvl = level_of(ratio)
    if not lvl:
        return []
    sid = str(data.get("session_id") or os.path.basename(path))
    sp = os.environ.get("CONTEXT_GUARD_STATE_PATH", DEFAULT_STATE)
    state = load_state(sp)
    try:
        last = int(state.get(sid, 0))
    except Exception:
        last = 0
    if lvl <= last:
        return []
    state[sid] = lvl
    save_state(sp, state)
    out = [f"컨텍스트 {round(ratio * 100)}% 사용. 압축 준비 시점입니다(공정 카드 공용-오케스트레이션 #4).\n"
           "① 진행 중 서브에이전트·감시·막힌 것·하지 말 것을 한 블록으로 정리\n"
           "② 사장님께 압축 후 한 번에 입력할 한 문장을 제시\n"
           "③ 새 일은 시작하지 않음"]
    if hand_heavy(calls):
        out.append("오케스트레이션 2.0: 위임으로 돌려라(최근 30회 중 25회 이상이 위임 없는 직접 손일).")
    return out


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
        msgs = evaluate(data)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    if not msgs:
        sys.exit(0)
    print("\n".join(msgs), file=sys.stderr)
    sys.exit(2 if os.environ.get("CONTEXT_GUARD_MODE", "warn").lower() == "block" else 0)
