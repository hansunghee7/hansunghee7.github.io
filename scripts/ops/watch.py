#!/usr/bin/env python3
"""주기 작업, 서비스, PC 상태 감시 (AI 없음, 토큰 0, 읽기 전용).

왜 만들었나(2026-09-20): 주기 작업이 "안 돈다"는 문제가 반복됐다. 원인은 돌았는지, 성공했는지를 아는 장치가 없었기 때문이다.
- 헤르메스 크론의 "ok"는 AI 실행이 끝났다는 뜻일 뿐 작업 성공이 아니다(폴러가 마무리를 빼먹은 날도 ok).
- 보호 규칙 도입 뒤 예약 자동화 7개가 push 거절로 조용히 실패했고 발견은 사람이 했다.
- 한 번도 실행되지 않은 크론, 꺼진 서비스(제미나이 풀)를 에이전트가 일하다가 처음 발견했다.
동작: jobs.toml(대장)의 항목을 점검해 state.json과 STATUS.md를 쓰고, **상태가 바뀔 때만** 우편함으로 알린다.
  첫 실행은 항목별 알림 대신 요약 1통만 보낸다. 세션 시작 훅이 STATUS의 문제 줄을 에이전트에게 보여 준다.
사용: python watch.py [--dry-run]   (--dry-run은 상태 파일과 알림 없이 표만 출력)
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.environ.get("OPS_STATE_DIR", r"C:\work\_ops")
MAILBOX = os.environ.get("OPS_MAILBOX", r"C:\work\solar-bible\mailbox\mailbox.py")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
ICON = {"ok": "🟢", "pending": "⚪", "warn": "🟡", "fail": "🔴"}
# 점검 주기는 "탐지 지연을 얼마까지 허용하는가"로 정한다(주기 = 탐지 지연의 하한). 항목별로 every_min으로 바꿀 수 있다.
#  - 에이전트가 일하다가 부딪히는 것(서비스, 헤르메스 크론, 기능 점검): 30분. 연속 2회 실패 때 알리므로 약 1시간 안에 안다.
#  - GitHub 예약 작업, 명령 점검: 6시간(작업 주기가 하루~2시간이고 실패는 한 번에 확정되므로 1회 실패에 알림).
#  - PC 보안 상태: 하루 1회(1회 실패에 알림).
DEFAULT_EVERY = {"gh_workflow": 360, "pc": 1440, "cmd": 360}
DEFAULT_FAIL_AFTER = {"gh_workflow": 1, "pc": 1, "cmd": 1}
DEFAULT_TICK = 30


def now():
    return datetime.now(KST)


def run(cmd, timeout=90, stdin=None):
    try:
        # 작업 스케줄러에서 15분마다 돌 때 콘솔 창이 깜빡이지 않게 한다(Windows)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace", input=stdin, creationflags=flags)
        return p.returncode, p.stdout
    except Exception as exc:  # 실행 파일이 없거나 시간 초과
        return 1, f"{type(exc).__name__}: {exc}"


def find_exe(name, extras):
    return shutil.which(name) or next((p for p in extras if os.path.exists(p)), name)


# ---------- 순수 함수(시험 대상) ----------
def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def parse_hermes_cron(text):
    """`hermes cron list` 출력 -> {이름: {last, last_status, next}}"""
    jobs, cur = {}, None
    for line in ANSI.sub("", text).splitlines():
        m = re.match(r"\s*Name:\s+(.*\S)", line)
        if m:
            cur = jobs.setdefault(m.group(1), {})
            continue
        if cur is None:
            continue
        m = re.match(r"\s*Last run:\s+(\S+)\s*(\S*)", line)
        if m:
            cur["last"], cur["last_status"] = parse_iso(m.group(1)), m.group(2)
        m = re.match(r"\s*Next run:\s+(\S+)", line)
        if m:
            cur["next"] = parse_iso(m.group(1))
    return jobs


def infer_period_min(run_times, default=1440):
    """실행 시각들의 간격 중앙값(분). 3개 미만이면 기본값."""
    ts = sorted(run_times)
    if len(ts) < 3:
        return default
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(ts, ts[1:]) if b > a]
    return max(1, statistics.median(gaps)) if gaps else default


def is_stale(last, period_min, at, grace_min=60):
    """마지막 성공이 주기의 1.5배 + 여유보다 오래됐는가."""
    return (at - last).total_seconds() / 60 > 1.5 * period_min + grace_min


def is_due(prev_entry, every_min, at):
    """이전 점검 시각에서 every_min이 (2분 오차 포함) 지났는가."""
    if not prev_entry or not prev_entry.get("checked"):
        return True
    last = parse_iso(prev_entry["checked"])
    return last is None or (at - last).total_seconds() / 60 >= every_min - 2


def find_by_name(table, name):
    if name in table:
        return table[name]
    return next((v for k, v in table.items() if k.startswith(name)), None)


# ---------- 점검 ----------
def check_hermes(job, crons, at):
    rec = find_by_name(crons, job["name"])
    if rec is None:
        return "fail", "헤르메스 크론 목록에 없음"
    last, period = rec.get("last"), job.get("period_min", 1440)
    if last is None:
        nxt = rec.get("next")
        return ("pending", f"첫 실행 전, 다음 {nxt:%m-%d %H:%M}") if nxt and nxt > at else ("fail", "실행 기록이 없음")
    if rec.get("last_status") not in ("ok", ""):
        return "fail", f"마지막 실행 상태 {rec.get('last_status')}"
    if (at - last).total_seconds() / 60 > 1.5 * period + 5:
        return "fail", f"마지막 실행 {last:%m-%d %H:%M}, 주기 {period:g}분보다 오래 안 돎"
    detail = f"마지막 실행 {last:%m-%d %H:%M} (ok는 AI 종료 의미일 뿐)"
    stuck = job.get("stuck_glob")
    if stuck:
        old = [f for f in glob.glob(stuck) if (at.timestamp() - os.path.getmtime(f)) / 60 > job.get("stuck_min", 12)]
        if old:
            return "fail", f"{len(old)}건이 {job.get('stuck_min', 12)}분 넘게 처리 대기(마무리 누락 의심)"
    return "ok", detail


def load_gh(pairs):
    """(저장소, 워크플로 이름)별 최근 실행 20건. 저장소 전체 100건만 보면 오래된 예약 작업이 빠진다."""
    out, gh = {}, find_exe("gh", [r"C:\Program Files\GitHub CLI\gh.exe"])
    for repo, wf in pairs:
        code, txt = run([gh, "run", "list", "-R", repo, "--workflow", wf, "--limit", "20", "--json", "name,conclusion,createdAt,event,status"])
        try:
            out[(repo, wf)] = json.loads(txt) if code == 0 else None
        except ValueError:
            out[(repo, wf)] = None
    return out


def check_gh(job, gh_runs, at):
    runs = gh_runs.get((job["repo"], job["workflow"]))
    if runs is None:
        return "warn", "GitHub 조회 실패(gh 인증 확인)"
    mine = sorted((r for r in runs if r["status"] == "completed"), key=lambda r: r["createdAt"], reverse=True)
    if not mine:
        return "warn", "실행 기록이 없음"
    last = mine[0]
    when = parse_iso(last["createdAt"].replace("Z", "+00:00")).astimezone(KST)
    if last["conclusion"] != "success":
        return "fail", f"마지막 실행 {when:%m-%d %H:%M} {last['conclusion']}"
    sched = [parse_iso(r["createdAt"].replace("Z", "+00:00")) for r in mine if r["event"] == "schedule"]
    period = job.get("period_min") or infer_period_min(sched)
    if is_stale(when, period, at):
        return "fail", f"마지막 성공 {when:%m-%d %H:%M}, 주기 약 {period:g}분보다 오래 안 돎"
    return "ok", f"마지막 성공 {when:%m-%d %H:%M}"


def check_tcp(job, at):
    try:
        with socket.create_connection((job.get("host", "127.0.0.1"), job["port"]), timeout=3):
            return "ok", "포트 응답"
    except OSError as exc:
        return "fail", f"연결 실패({type(exc).__name__})"


def check_http(job, at):
    body = job.get("body")
    headers = {"User-Agent": "simplifier-ops-watch/1.0 (internal)"}
    if body:
        headers.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    req = urllib.request.Request(job["url"], data=body.encode() if body else None, method=job.get("method", "GET"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as exc:  # 405, 401처럼 "정상 거절"도 응답이다
        code = exc.code
    except Exception as exc:
        return "fail", f"{type(exc).__name__}: {str(exc)[:80]}"
    return ("ok", f"HTTP {code}") if code == job.get("expect", 200) else ("fail", f"HTTP {code} (기대 {job.get('expect', 200)})")


def check_file_age(job, at):
    """파일이 max_age_min 안에 갱신됐는가(하트비트 파일용)."""
    try:
        age = (at.timestamp() - os.path.getmtime(job["path"])) / 60
    except OSError:
        return "fail", "파일이 없음"
    return ("ok" if age <= job["max_age_min"] else "fail"), f"마지막 갱신 {age:.0f}분 전"


def check_cmd(job, at):
    cmd = list(job["cmd"])
    if cmd[0] == "python":
        cmd[0] = shutil.which("python") or sys.executable
    code, out = run(cmd, timeout=job.get("timeout", 90))
    first = (out.strip().splitlines() or [""])[0][:120]
    return ("ok" if code == 0 else "fail"), first or f"종료 코드 {code}"


def ps(cmd):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], timeout=60)[1].strip()


def check_pc(job, at):
    what = job["check"]
    if what == "disk_free":
        u = shutil.disk_usage("C:\\")
        pct = u.free / u.total * 100
        return ("ok" if pct >= job.get("min_pct", 15) else "fail"), f"C 여유 {pct:.0f}% ({u.free / 1e9:.0f}GB)"
    if what == "defender":
        out = ps("$m=Get-MpComputerStatus; \"$($m.RealTimeProtectionEnabled) $($m.AntivirusSignatureLastUpdated.ToString('yyyy-MM-dd'))\"").split()
        if len(out) != 2:
            return "warn", "디펜더 상태를 읽지 못함"
        age = (at.date() - datetime.strptime(out[1], "%Y-%m-%d").date()).days
        return ("ok" if out[0] == "True" and age <= 3 else "fail"), f"실시간 보호 {out[0]}, 정의 갱신 {age}일 전"
    if what == "firewall":
        out = ps("(Get-NetFirewallProfile | ForEach-Object { $_.Enabled }) -join ','")
        return ("ok" if out and "False" not in out else "fail"), f"방화벽 프로필 {out}"
    if what == "ports":
        out = ps("(Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -in '0.0.0.0','::' } | Select-Object -ExpandProperty LocalPort | Sort-Object -Unique) -join ','")
        ports = {int(p) for p in out.split(",") if p.strip().isdigit()}
        base_file = os.path.join(STATE_DIR, "ports_baseline.json")
        if not os.path.exists(base_file):
            os.makedirs(STATE_DIR, exist_ok=True)
            json.dump(sorted(ports), open(base_file, "w"))
            return "ok", f"기준선 생성({len(ports)}개 포트)"
        new = sorted(ports - set(json.load(open(base_file))))
        return ("ok", f"기준선과 같음({len(ports)}개)") if not new else ("warn", f"기준선에 없던 열린 포트 {new}")
    return "warn", f"알 수 없는 점검 {what}"


def evaluate(jobs, at, prev=None):
    prev = prev or {}
    due = {j["id"] for j in jobs if is_due(prev.get(j["id"]), j.get("every_min", DEFAULT_EVERY.get(j["kind"], DEFAULT_TICK)), at)}
    hermes = find_exe("hermes", [r"C:\Users\PC\AppData\Local\hermes\bin\hermes.exe"])
    crons = parse_hermes_cron(run([hermes, "cron", "list"])[1]) if any(j["kind"] == "hermes_cron" and j["id"] in due for j in jobs) else {}
    gh_runs = load_gh(sorted({(j["repo"], j["workflow"]) for j in jobs if j["kind"] == "gh_workflow" and j["id"] in due}))
    results = []
    for j in jobs:
        if j["id"] not in due:
            results.append({**prev[j["id"]], "reused": True})
            continue
        try:
            k = j["kind"]
            st, detail = (check_hermes(j, crons, at) if k == "hermes_cron" else check_gh(j, gh_runs, at) if k == "gh_workflow"
                          else check_tcp(j, at) if k == "tcp" else check_http(j, at) if k == "http" else check_cmd(j, at) if k == "cmd" else check_file_age(j, at) if k == "file_age" else check_pc(j, at))
        except Exception as exc:
            st, detail = "warn", f"점검 자체가 실패: {type(exc).__name__}: {str(exc)[:80]}"
        if st == "fail" and j.get("severity") == "warn":
            st = "warn"
        results.append({"id": j["id"], "name": j["name"], "status": st, "detail": detail, "owner": j.get("owner", "탐"), "note": j.get("note", ""),
                        "fail_after": j.get("fail_after", DEFAULT_FAIL_AFTER.get(j["kind"], 2))})
    return results


# ---------- 상태·알림 ----------
def merge_state(prev, results, at):
    """이전 상태와 합쳐 연속 실패 횟수, 시작 시각, 알림 대상을 계산한다."""
    new, alerts = {}, []
    for r in results:
        if r.get("reused"):  # 이번 회차에 점검하지 않은 항목: 상태와 연속 실패 횟수를 그대로 둔다
            new[r["id"]] = {k: v for k, v in r.items() if k != "reused"}
            continue
        p = prev.get(r["id"], {})
        bad = r["status"] in ("fail",)
        fails = p.get("fails", 0) + 1 if bad else 0
        since = p.get("since") if p.get("status") == r["status"] else at.isoformat()
        new[r["id"]] = {**r, "fails": fails, "since": since, "checked": at.isoformat()}
        if prev:
            need = r.get("fail_after", 2)
            if bad and fails == need:
                alerts.append(("down", r))
            elif p.get("status") == "fail" and not bad and p.get("fails", 0) >= p.get("fail_after", 2):
                alerts.append(("up", r))
    return new, alerts


def write_status(state, at):
    order = {"fail": 0, "warn": 1, "pending": 2, "ok": 3}
    items = sorted(state.values(), key=lambda r: (order[r["status"]], r["name"]))
    bad = [r for r in items if r["status"] == "fail"]
    lines = [f"# 상태판 (감시 자동 갱신 {at:%Y-%m-%d %H:%M} KST)", "",
             f"**🔴 문제 {len(bad)}건, 🟡 주의 {sum(r['status'] == 'warn' for r in items)}건, 전체 {len(items)}건**", "",
             "| 상태 | 항목 | 내용 | 시작 |", "|---|---|---|---|"]
    for r in items:
        lines.append(f"| {ICON[r['status']]} | {r['name']} | {r['detail']}{(' / ' + r['note']) if r.get('note') else ''} | {r['since'][5:16].replace('T', ' ')} |")
    os.makedirs(STATE_DIR, exist_ok=True)
    open(os.path.join(STATE_DIR, "STATUS.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def send(title, body):
    return run([sys.executable, MAILBOX, "send", "탐", title, "--from", "탐"], stdin=body)


def main():
    dry = "--dry-run" in sys.argv
    at = now()
    jobs = tomllib.load(open(os.path.join(HERE, "jobs.toml"), "rb"))["job"]
    state_file = os.path.join(STATE_DIR, "state.json")
    prev = json.load(open(state_file, encoding="utf-8")) if os.path.exists(state_file) else {}
    results = evaluate(jobs, at, prev)
    state, alerts = merge_state(prev, results, at)
    if dry:
        for r in sorted(state.values(), key=lambda r: r["status"]):
            print(ICON[r["status"]], r["name"], "|", r["detail"])
        return 0
    write_status(state, at)
    json.dump(state, open(state_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bad = [r for r in state.values() if r["status"] == "fail"]
    if not prev:  # 첫 실행은 요약 1통
        body = f"감시를 시작했습니다. 지금 문제 {len(bad)}건:\n" + "\n".join(f"- {r['name']}: {r['detail']}" for r in bad[:12]) + "\n상태판: C:\\work\\_ops\\STATUS.md"
        send("[감시] 시작: 지금 문제 %d건" % len(bad), body)
    for kind, r in alerts:
        head = "🔴 멈춤" if kind == "down" else "🟢 복구"
        send(f"[감시] {head}: {r['name']}", f"{r['name']}: {r['detail']}\n(연속 점검 결과, 상태판 C:\\work\\_ops\\STATUS.md)")
    print(f"점검 {len(state)}건, 문제 {len(bad)}건, 알림 {len(alerts)}건")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
