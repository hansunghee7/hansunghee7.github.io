#!/usr/bin/env python3
"""Stop 훅: 지투가 "정하실 것 없음"으로 끝내려는데 업무대장에 할 일이 남아 있으면 막는다(사장님 결정 2026-10-05).

사고(2026-10-05 지투): 백로그에 혼자 할 수 있는 일이 있는데 "정하실 것: 없음, 대기"로 끝내서, 사장님이 다시 말하기 전까지 멈췄다.
세션은 턴 사이에 스스로 움직이지 못하므로(commit-gate.py 머리말), 끝내기 직전에 대장을 보게 하는 관문을 둔다(CLAUDE#4e7b).

규칙: ① 이 세션이 지투일 때만(첫 사용자 발화에 '지투'가 있음, 예약 세션 프롬프트도 '지투 예약 세션'으로 시작) ② 마지막 답변이 끝내기 신호
(`정하실 것: 없음` 또는 `[실행 대기`)를 담고 ③ docs/지투_업무대장.md 열린 항목에 상태 `대기`·결정자에 `지투`가 든 행이 있으면
exit 2로 막고 그 행을 보여 준다. 해결: 그 행을 진행하거나, 못 하는 이유를 대장에서 상태 `보류`/`사장님`으로 바꾸고 끝낸다.
무한 반복 방지: stop_hook_active면 통과, 한 시간에 3번까지만 막는다(C:/work/_ops/queue_gate_count.json).
입력: stdin JSON(Stop 훅 규격). 검사기 오류가 나면 통과한다.
"""
import json
import os
import re
import sys
import time

PERSONAS = {"지투": "docs/지투_업무대장.md"}
IDLE = re.compile(r"정하실 것\s*[:：]\s*없음|\[실행 대기")
COUNT_FILE = os.environ.get("QUEUE_GATE_COUNT", "C:/work/_ops/queue_gate_count.json")
MAX_PER_HOUR = 3


def first_user_text(path):
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
    return ""


def last_assistant_text(path):
    last = ""
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") != "assistant":
                continue
            for p in ev.get("message", {}).get("content", []) or []:
                if isinstance(p, dict) and p.get("type") == "text" and p.get("text"):
                    last = p["text"]
    return last


def open_rows(ledger_text, name):
    rows = []
    section = ledger_text.split("## 닫힌 항목")[0]
    for ln in section.splitlines():
        if not ln.startswith("| N"):
            continue
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cols) < 8:
            continue
        if cols[3] == "대기" and name in cols[7]:
            rows.append((cols[0], cols[1][:60]))
    return rows


def persona_of(first_text):
    for name in PERSONAS:
        if name in first_text[:400]:
            return name
    return None


def allowed_now(now=None):
    """한 시간에 MAX_PER_HOUR번까지만 막는다. 기록 실패는 통과 처리."""
    now = now or time.time()
    try:
        try:
            with open(COUNT_FILE, encoding="utf-8") as f:
                stamps = json.load(f)
        except Exception:
            stamps = []
        stamps = [t for t in stamps if now - t < 3600]
        if len(stamps) >= MAX_PER_HOUR:
            return False
        stamps.append(now)
        os.makedirs(os.path.dirname(COUNT_FILE), exist_ok=True)
        with open(COUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(stamps, f)
        return True
    except Exception:
        return False


def check(persona, last_text, ledger_text):
    if persona not in PERSONAS or not IDLE.search(last_text or ""):
        return []
    return open_rows(ledger_text, persona)


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
        tp = data.get("transcript_path")
        if not tp:
            sys.exit(0)
        persona = persona_of(first_user_text(tp))
        if not persona:
            sys.exit(0)
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        with open(os.path.join(root, PERSONAS[persona]), encoding="utf-8") as f:
            rows = check(persona, last_assistant_text(tp), f.read())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    if not rows or not allowed_now():
        sys.exit(0)
    lst = "; ".join(f"{n} {t}" for n, t in rows[:3])
    sys.stderr.write(
        f"[업무대장 관문] 지금 끝내려 했지만 {PERSONAS[persona]}에 상태 `대기`·결정자 `{persona}`인 행이 {len(rows)}개 남아 있습니다(사장님 결정 2026-10-05): {lst}. "
        "그 행을 위에서부터 진행하세요. 정말 못 하는 이유가 있으면 대장에서 해당 행 상태를 `보류` 또는 `사장님`으로 바꾸고 사유를 적은 뒤 끝내세요(약속만 하고 끝내지 않기).\n")
    sys.exit(2)
