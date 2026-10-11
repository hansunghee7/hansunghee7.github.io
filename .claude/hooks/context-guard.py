#!/usr/bin/env python3
"""Stop 훅 `컨텍스트 가드`: 컨텍스트 사용 비율이 50% 이상이면 압축 준비를 안내한다(공정 카드 공용-오케스트레이션 #4).

컨텍스트 사용량 = 전사의 마지막 assistant 메시지 usage (input + cache_read + cache_creation 토큰).
비율 = 사용량 / CONTEXT_WINDOW_TOKENS(기본 1000000). 50% 이상에서 5% 단계마다 세션당 한 번만 안내한다.
같은 시점에 최근 30회 도구 호출 중 25회 이상이 직접 손일(Bash·PowerShell·Edit·Write·MultiEdit)이고 위임 기록이 없으면 한 줄을 더 낸다.
환경변수: CONTEXT_WINDOW_TOKENS, CONTEXT_GUARD_STATE_DIR(기본 C:/work/_ops/context_guard, 세션별 파일), CONTEXT_GUARD_TAIL_BYTES(기본 3145728, 전사 끝에서 이만큼만 읽음),
CONTEXT_GUARD_MODE(warn 기본 | block: 종료 코드 2로 에이전트 눈에 보이게 함).
파싱 실패·usage 없음은 조용히 통과(fail-open). 세션을 막지 않는다.
"""
import json
import os
import re
import sys

DEFAULT_STATE_DIR = "C:/work/_ops/context_guard"
HAND_TOOLS = {"Bash", "PowerShell", "Edit", "Write", "MultiEdit"}
DEFAULT_TAIL_BYTES = 3145728
START_RATIO = 0.50
STEP = 5
WINDOW = 30
HAND_MIN = 25


def is_delegation(name, inp):
    """위임 = Agent(Task)·SendMessage 호출, 또는 Bash/PowerShell 입력의 run_in_background=true. 명령 문자열 단어는 보지 않는다."""
    if name in ("Agent", "Task", "SendMessage"):
        return True
    return name in ("Bash", "PowerShell") and inp.get("run_in_background") is True


def tail_lines(path):
    """파일 끝에서 최대 CONTEXT_GUARD_TAIL_BYTES만 읽어 줄 목록을 돌려준다. 중간에서 시작했으면 잘린 첫 줄은 버린다."""
    try:
        n = int(os.environ.get("CONTEXT_GUARD_TAIL_BYTES", DEFAULT_TAIL_BYTES))
        if n <= 0:
            n = DEFAULT_TAIL_BYTES
    except Exception:
        n = DEFAULT_TAIL_BYTES
    with open(path, "rb") as f:
        size = f.seek(0, os.SEEK_END)
        start = max(0, size - n)
        f.seek(start)
        data = f.read()
    lines = data.split(b"\n")
    if start > 0:
        lines = lines[1:]
    return lines


def scan(path):
    """(마지막 usage 합계 또는 None, 최근 30회 도구 호출 [(name, is_delegation)] 시간순). 끝에서 거꾸로 읽는다."""
    usage = None
    rev = []
    for raw in reversed(tail_lines(path)):
        if usage is not None and len(rev) >= WINDOW:
            break
        try:
            ev = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(ev, dict) or ev.get("type") != "assistant":
            continue
        m = ev.get("message") or {}
        u = m.get("usage")
        if usage is None and isinstance(u, dict):
            try:
                tot = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            except Exception:
                tot = 0
            if tot > 0:
                usage = tot
        c = m.get("content")
        if isinstance(c, list):
            for p in reversed(c):
                if isinstance(p, dict) and p.get("type") == "tool_use" and len(rev) < WINDOW:
                    name = p.get("name", "")
                    rev.append((name, is_delegation(name, p.get("input") or {})))
    return usage, rev[::-1]


def window_size():
    try:
        v = int(os.environ.get("CONTEXT_WINDOW_TOKENS", "1000000"))
        return v if v > 0 else 1000000
    except Exception:
        return 1000000


def level_of(ratio):
    """50% 이상이면 5% 단계 값(50, 55, 60, ...), 아니면 0."""
    if ratio < START_RATIO:
        return 0
    return int(round(ratio * 100, 6) // STEP * STEP)


def hand_heavy(calls):
    if len(calls) < WINDOW:
        return False
    if any(d for _, d in calls):
        return False
    return sum(1 for n, _ in calls if n in HAND_TOOLS) >= HAND_MIN


def state_file(sid):
    d = os.environ.get("CONTEXT_GUARD_STATE_DIR", DEFAULT_STATE_DIR)
    return os.path.join(d, re.sub(r"[^A-Za-z0-9_.-]", "_", sid)[:100] + ".json")


def load_level(fp):
    try:
        with open(fp, encoding="utf-8") as f:
            return int(json.load(f)["level"])
    except Exception:
        return 0


def save_level(fp, level):
    """임시 파일에 쓴 뒤 os.replace로 바꿔 끼운다(원자적)."""
    try:
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        tmp = fp + ".tmp%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"level": level}, f)
        os.replace(tmp, fp)
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
    fp = state_file(sid)
    if lvl <= load_level(fp):
        return []
    save_level(fp, lvl)
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
