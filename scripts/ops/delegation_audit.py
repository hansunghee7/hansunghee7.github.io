"""위임 비율 정기 실측과 판정일 감시 (감시 대장 항목 fn:delegation-audit).

배경: 사장님 지시(2026-10-11) '위임 관문을 경고에서 차단으로 바꿀지는 오탐이 줄어든 뒤 실측하고 정한다.
대신 이것을 놓치지 않고 실측 및 적용되어야 한다'. 세션이 바뀌어도 약속이 빠지지 않도록 감시 장치로 만들었다.

하는 일 (전사 본문은 출력·저장하지 않고 숫자만 센다):
  run     세션 전사에서 위임 비율과 Stop 훅 피드백을 세어 history.csv에 오늘 행을 넣는다(같은 날 재실행은 그 행을 갈아쓴다).
          판정일(2026-10-18) 이후 첫 실행에서는 10/12~ 7일 지표를 기준선과 비교한 한 줄을 decision_1018.md에 쓰고
          state.json에 decision_due=true를 기록한다. 차단 전환 판정은 스크립트가 하지 않는다(사장님·탐 결정).
  watch   감시 대장용. run을 하고, 직전 성공이 36시간을 넘었거나 판정 대기 중이면 종료 코드 1(붉음).
  decide  "결정 내용"을 state.json의 decided에 기록(붉음 해제).
  status  state.json 요약.

사용: python scripts/ops/delegation_audit.py run [--days 3] [--out history.csv]
"""
import argparse
import collections
import csv
import glob
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

OPS_DIR = os.environ.get("DELEG_AUDIT_DIR", "C:/work/_ops/deleg_audit")
ROOT = os.environ.get("DELEG_AUDIT_ROOT", "C:/Users/PC/.claude/projects")
PREFIX = "C--work-hansunghee7-github-io"  # 이 저장소 세션(워크트리 포함)

DECISION_DATE = date(2026, 10, 18)
DECISION_SINCE = date(2026, 10, 12)  # 훅 수정 반영 뒤
STALE_HOURS = 36
BASELINE = dict(date="2026-10-11", label="baseline", sessions=7, calls=2108, deleg=286, stop=227,
                stuck=163, commit=38, tone=13, other=13)

MARKS = ["ask_dex.sh", "ask_bt.sh", "hx.sh", "api_run.py", "credit_run.py", "gemini_route.py", "vertex_research.py", "nohup"]
DELEG_TOOLS = {"Agent", "Task", "SendMessage", "Monitor", "CronCreate", "ScheduleWakeup"}
COLS = ["date", "label", "sessions", "calls", "deleg", "ratio_pct", "stop", "stuck", "commit", "tone", "other"]


def _text_of(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _ts(o):
    s = o.get("timestamp")
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def collect(root=None, prefix=PREFIX, days=3, since_ts=None, now=None):
    """숫자만 센다. since_ts가 있으면 그 시각 이후 줄만 센다. 반환: dict(sessions, calls, deleg, stop, stuck, commit, tone, other)."""
    root = root or ROOT
    now = now or time.time()
    cut = since_ts if since_ts is not None else now - days * 86400
    r = collections.Counter()
    for d in os.listdir(root) if os.path.isdir(root) else []:
        if not d.startswith(prefix):
            continue
        for fp in glob.glob(os.path.join(root, d, "*.jsonl")):
            if os.path.getmtime(fp) < cut:
                continue
            r["sessions"] += 1
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        try:
                            o = json.loads(line)
                        except Exception:
                            continue
                        if since_ts is not None:
                            t = _ts(o)
                            if t is not None and t < since_ts:
                                continue
                        m = o.get("message") or {}
                        role = m.get("role") or o.get("type")
                        c = m.get("content")
                        if role == "assistant" and isinstance(c, list):
                            for b in c:
                                if isinstance(b, dict) and b.get("type") == "tool_use":
                                    n = b.get("name", "")
                                    inp = b.get("input") or {}
                                    r["calls"] += 1
                                    if n in DELEG_TOOLS:
                                        r["deleg"] += 1
                                    elif n == "Bash":
                                        cmd = str(inp.get("command", ""))
                                        if any(k in cmd for k in MARKS) or inp.get("run_in_background") is True:
                                            r["deleg"] += 1
                        elif role == "user":
                            t = _text_of(c)
                            if t.startswith("Stop hook feedback"):
                                r["stop"] += 1
                                if "stuck-process-gate" in t:
                                    r["stuck"] += 1
                                elif "commit-gate" in t:
                                    r["commit"] += 1
                                elif "check-tone" in t:
                                    r["tone"] += 1
                                else:
                                    r["other"] += 1
            except Exception:
                continue
    return {k: r[k] for k in ["sessions", "calls", "deleg", "stop", "stuck", "commit", "tone", "other"]}


def ratio(v):
    return round(100.0 * v["deleg"] / v["calls"], 1) if v["calls"] else 0.0


def row_of(v, day, label):
    return dict(date=day, label=label, sessions=v["sessions"], calls=v["calls"], deleg=v["deleg"],
                ratio_pct=ratio(v), stop=v["stop"], stuck=v["stuck"], commit=v["commit"], tone=v["tone"], other=v["other"])


def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})


def ensure_baseline(rows):
    if not any(r.get("label") == "baseline" for r in rows):
        rows.insert(0, row_of(BASELINE, BASELINE["date"], "baseline"))
    return rows


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"decision_due": False, "decided": "", "last_run": ""}


def save_state(path, st):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def run(out=None, days=3, today=None, root=None, ops_dir=None, now=None):
    ops_dir = ops_dir or OPS_DIR
    out = out or os.path.join(ops_dir, "history.csv")
    state_path = os.path.join(ops_dir, "state.json")
    today = today or date.today()
    now = now or time.time()
    v = collect(root=root, days=days, now=now)
    rows = ensure_baseline(read_rows(out))
    rows = [r for r in rows if not (r.get("label") == "run" and r.get("date") == today.isoformat())]
    rows.append(row_of(v, today.isoformat(), "run"))
    write_rows(out, rows)
    st = load_state(state_path)
    st["last_run"] = datetime.fromtimestamp(now).isoformat(timespec="seconds")
    st.setdefault("decided", "")
    st.setdefault("decision_due", False)
    if today >= DECISION_DATE and not st["decision_due"]:
        since = datetime.combine(DECISION_SINCE, datetime.min.time()).timestamp()
        w = collect(root=root, since_ts=since, now=now)
        line = (f"판정일 {DECISION_DATE} 비교(10/12~ 7일 창, 세션 {w['sessions']}개, 도구 호출 {w['calls']}회): "
                f"위임 비율 기준선 13.6% -> {ratio(w)}%, stuck-process-gate 피드백 기준선 163건 -> {w['stuck']}건 "
                f"(commit-gate {w['commit']}, check-tone {w['tone']}, 기타 {w['other']}). "
                f"차단 전환 여부는 사장님·탐이 정한다(`delegation_audit.py decide \"...\"`로 기록).")
        with open(os.path.join(ops_dir, "decision_1018.md"), "w", encoding="utf-8") as f:
            f.write(line + "\n")
        st["decision_due"] = True
        st["decision_written"] = datetime.fromtimestamp(now).isoformat(timespec="seconds")
    save_state(state_path, st)
    return rows[-1], st


def watch(ops_dir=None, now=None, **kw):
    """(종료 코드, 한 줄). 붉음 조건: 직전 성공이 36시간 초과 또는 판정 대기."""
    ops_dir = ops_dir or OPS_DIR
    now = now or time.time()
    prev = load_state(os.path.join(ops_dir, "state.json")).get("last_run")
    gap = ""
    if prev:
        try:
            h = (now - datetime.fromisoformat(prev).timestamp()) / 3600
            if h > STALE_HOURS:
                gap = f"직전 실측이 {h:.0f}시간 전(36시간 초과)"
        except Exception:
            pass
    r, st = run(ops_dir=ops_dir, now=now, **kw)
    if st.get("decision_due") and not st.get("decided"):
        return 1, f"위임 관문 차단 전환 판정 대기 (decision_1018.md 확인 후 decide로 기록)" + (f"; {gap}" if gap else "")
    if gap:
        return 1, gap
    return 0, f"위임 {r['ratio_pct']}% ({r['deleg']}/{r['calls']}), stuck {r['stuck']}건, 실측 정상"


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # watch.py가 utf-8로 읽는다
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "watch", "decide", "status"])
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "decide":
        p = os.path.join(OPS_DIR, "state.json")
        st = load_state(p)
        if not a.text.strip():
            print("결정 내용을 적어야 한다")
            return 2
        st["decided"] = a.text.strip()
        st["decided_at"] = datetime.now().isoformat(timespec="seconds")
        save_state(p, st)
        print("기록함")
        return 0
    if a.cmd == "status":
        print(json.dumps(load_state(os.path.join(OPS_DIR, "state.json")), ensure_ascii=False))
        return 0
    if a.cmd == "watch":
        code, msg = watch(out=a.out, days=a.days)
        print(msg)
        return code
    r, st = run(out=a.out, days=a.days)
    print(f"{r['date']} 세션 {r['sessions']} 호출 {r['calls']} 위임 {r['deleg']} ({r['ratio_pct']}%) Stop {r['stop']} "
          f"(stuck {r['stuck']}, commit {r['commit']}, tone {r['tone']}, 기타 {r['other']}) 판정대기={st['decision_due'] and not st['decided']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
