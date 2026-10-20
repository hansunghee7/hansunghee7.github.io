#!/usr/bin/env python3
"""구PC 자동 실행 로그 한 장 요약(log_digest, 탐 2026-10-20).

왜 있나
-------
구PC(ssh goosolar)에는 크론, 깃허브 자체 실행기(job_gate.log·Worker 로그·keepalive),
헤르메스, 백업, 공장 idle_guard 로그가 흩어져 있다. 실패가 나면 사람이(또는 당직
타미가) 여러 파일을 열어 시각을 맞춰 보며 원인 후보를 찾느라 시간이 걸렸다
(예: 10/19 reseed-guides 3연속 취소는 Worker 로그의 취소 시각과 job_gate.log의
메모리 대기 줄을 맞대 보고서야 원인이 보였다). 이 도구는 그 대조를 규칙으로 고정해
최근 24시간을 20줄 이내 한 장으로 만든다.

원칙
----
- 구PC는 읽기만 한다(tail·grep·find·journalctl, 수정·재시작 없음).
- LLM을 부르지 않는다(규칙 기반, 토큰 0). 원인은 "후보"이고 판정은 사람이 한다.
- 키·토큰 모양 문자열(24자 이상 영숫자 덩어리 등)은 출력 전에 *** 로 가린다.

사용
----
  python scripts/ops/log_digest.py                      # 지금부터 24시간 전까지, 파일로 저장
  python scripts/ops/log_digest.py --end-kst "2026-10-19 15:00"   # 과거 창 재현
  python scripts/ops/log_digest.py --stdout             # 저장 없이 화면에만
결과: C:/work/_ops/log_digest/<KST 날짜>.md (재현 창은 <날짜>_<시각>.md)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
OUT_DIR = Path("C:/work/_ops/log_digest")
SSH_HOST = "goosolar"
MAX_LINES = 20
GATE_MEM_MB = 3072  # job_started.sh 관문의 일반 작업 메모리 하한

# ---------------------------------------------------------------- 마스킹
_MASKS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat|xox[abpr]|sk|AIza)[-_A-Za-z0-9]{12,}"),
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}"),          # 텔레그램 봇 토큰 모양
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # 메일 주소
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),              # IPv4
    re.compile(r"[A-Za-z0-9]{24,}"),                         # 24자 이상 영숫자 덩어리
]


def mask(text: str) -> str:
    for rx in _MASKS:
        text = rx.sub("***", text)
    return text


# ---------------------------------------------------------------- 원격 수집
# 원격에서 읽기 전용 명령만 돈다. $1=창 시작(UTC, 'YYYYmmdd-HHMMSS'), $2=창 끝, $3=journalctl --since
REMOTE_SCRIPT = r'''
SK="$1"; EK="$2"; JS="$3"
D="$HOME/actions-runner/_diag"; L="$HOME/workshop/logs"
echo "@@gate"; tail -n 8000 "$D/job_gate.log" 2>/dev/null
echo "@@workers"
for f in "$D"/Worker_*.log; do
  b=$(basename "$f"); k=${b#Worker_}; k=${k%-utc.log}
  [[ "$k" < "$SK" ]] && continue; [[ "$k" > "$EK" ]] && continue
  wf=$(grep -m1 -o '\.github/workflows/[A-Za-z0-9_.-]*\.yml' "$f" | sed 's#.*/##; s#\.yml$##')
  job=$(grep -m1 '"jobDisplayName"' "$f" | sed 's/.*: "//; s/".*//')
  res=$(grep -m1 'Job result after all job steps finish:' "$f" | sed 's/.*finish: //')
  can=$(grep -m1 'Cancellation/Shutdown message received' "$f" | cut -c2-20)
  end=$(tail -n 1 "$f" | cut -c2-20)
  echo "W|$k|$wf|$job|$res|$can|$end"
done
echo "@@keepalive"; tail -n 30 "$D/keepalive.log" 2>/dev/null
echo "@@checks"; tail -n 3000 "$HOME/ops/checks/checks.log" 2>/dev/null
echo "@@backup_private"; tail -n 60 "$L/backup_private.log" 2>/dev/null
echo "@@backup_hdd"; tail -n 30 "$L/backup_hdd.log" 2>/dev/null
echo "@@backup_hdd_verify"; tail -n 30 "$HOME/ops/backup_hdd.log" 2>/dev/null
echo "@@idle_guard"; tail -n 400 "$L/idle_guard.log" 2>/dev/null
echo "@@hermes"; journalctl -u hermes-agent --since "$JS" --no-pager 2>/dev/null | grep -E 'WARNING|ERROR|CRITICAL|Traceback|Failed|failed' | tail -n 200
echo "@@watch"; tail -n 1 "$HOME/ops/watch.log" 2>/dev/null
echo "@@now"
echo "MEM $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
for m in /srv/carvit-store /srv/carvit-bulk /srv/carvit-fast; do mountpoint -q "$m" && echo "MOUNT $m OK" || echo "MOUNT $m NG"; done
pgrep -f 'bin/[R]unner.Listener' >/dev/null && echo "RUNNER OK" || echo "RUNNER NG"
systemctl is-active --quiet hermes-agent && echo "HERMES OK" || echo "HERMES NG"
echo "@@end"
'''


def fetch_remote(start: datetime, end: datetime, host: str = SSH_HOST) -> str:
    """ssh로 원격 수집 스크립트를 돌려 구획(@@이름)으로 나뉜 텍스트를 받는다."""
    sk = start.astimezone(UTC).strftime("%Y%m%d-%H%M%S")
    ek = end.astimezone(UTC).strftime("%Y%m%d-%H%M%S")
    js = start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", host, "bash", "-s", "--", sk, ek, f"'{js}'"],
        # 바이트로 보낸다: 윈도우 text 모드는 \n을 \r\n으로 바꿔 원격 bash가 깨진다(첫 실측에서 발견)
        input=REMOTE_SCRIPT.replace("\r\n", "\n").encode("utf-8"), capture_output=True,
        timeout=180, **kw,
    )
    out = r.stdout.decode("utf-8", errors="replace")
    if r.returncode != 0 and "@@end" not in out:
        err = r.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ssh 수집 실패 rc={r.returncode}: {mask(err)[:200]}")
    return out


def split_sections(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for line in raw.splitlines():
        if line.startswith("@@"):
            cur = line[2:].strip()
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(line.rstrip("\r"))
    return out


# ---------------------------------------------------------------- 사건 모델
@dataclass
class Event:
    name: str
    ts: datetime          # UTC
    kind: str             # ok | fail | warn
    text: str = ""
    cause: str = ""       # 규칙이 붙인 원인 후보(있으면 표보다 우선)
    gate_low: list = field(default_factory=list)  # 이 작업 시간 안 관문 대기 줄의 3GB 미만 avail 값
    gate_window: bool = False                      # 리셋 회피창 대기였는가


@dataclass
class GateLine:
    ts: datetime
    kind: str             # pass | wait | giveup
    avail: int | None
    window: bool
    text: str


@dataclass
class Item:
    name: str
    last_ok: datetime | None = None
    fails: int = 0
    warns: int = 0
    rep: str = ""
    causes: list[str] = field(default_factory=list)
    gate_hits: int = 0                             # 관문 대기와 겹친 실패 수
    gate_low: list = field(default_factory=list)
    gate_window: bool = False

    def cause_list(self) -> list[str]:
        """관문 대기 근거가 있으면 그것을 맨 앞에(시각 대조로 얻은 가장 강한 근거)."""
        out = []
        if self.gate_hits:
            parts = []
            if self.gate_low:
                parts.append(f"구PC 여유 메모리 3GB 미만(관측 {min(self.gate_low)}~{max(self.gate_low)}MB) 관문 대기")
            if self.gate_window:
                parts.append("크레딧 리셋 직후 회피창 대기")
            out.append(" + ".join(parts or ["관문 대기"])
                       + f" → 작업 제한시간 초과 취소({self.gate_hits}/{self.fails}회가 관문 대기와 겹침)")
        rest = [c for c in self.causes if c]
        if out:
            rest = [c for c in rest if not c.startswith("규칙표에 없는")]
        return out + rest


def _utc(s: str, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(s, fmt).replace(tzinfo=UTC)
    except ValueError:
        return None


def _iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s).astimezone(UTC)
    except ValueError:
        return None


_GATE_RX = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (.*)$")
_AVAIL_RX = re.compile(r"avail=(\d+)MB")


def parse_gate(lines: list[str]) -> list[GateLine]:
    """job_gate.log(구PC 시각=UTC). 통과/대기/포기·미충족 줄을 구분한다."""
    out = []
    for ln in lines:
        m = _GATE_RX.match(ln)
        if not m:
            continue
        ts = _utc(m.group(1), "%Y-%m-%d %H:%M:%S")
        body = m.group(2)
        a = _AVAIL_RX.search(body)
        avail = int(a.group(1)) if a else None
        if body.startswith("통과"):
            kind = "pass"
        elif "포기" in body or "미충족" in body:
            kind = "giveup"
        elif "대기" in body:
            kind = "wait"
        else:
            continue
        out.append(GateLine(ts, kind, avail, "window=y" in body, body))
    return out


def gate_overlap(gate: list[GateLine], start: datetime, end: datetime) -> tuple[list[int], bool, bool]:
    """작업 시작~끝 사이 관문 대기 줄 → (3GB 미만 avail 값들, 회피창 대기 여부, 대기 줄 있음).
    job_gate.log에는 job 이름이 없어 같은 시각 동시 작업은 구분하지 못한다(한계)."""
    w = [g for g in gate if g.kind == "wait" and start <= g.ts <= end + timedelta(minutes=1)]
    low = [g.avail for g in w if g.avail is not None and g.avail < GATE_MEM_MB]
    return low, any(g.window for g in w), bool(w)


def _worker_fail(name, st, t, text, gate) -> "Event":
    low, win, hit = gate_overlap(gate, st, t)
    e = Event(name, t, "fail", text)
    if hit:
        e.cause, e.gate_low, e.gate_window = "@gate", low, win
    return e


def parse_workers(lines: list[str], gate: list[GateLine]) -> list[Event]:
    """Worker 로그 요약 줄 W|시작|워크플로|job|결과|취소시각|끝시각."""
    out = []
    for ln in lines:
        if not ln.startswith("W|"):
            continue
        p = (ln.split("|") + [""] * 7)[:7]
        _, k, wf, job, res, can, end = p
        st = _utc(k, "%Y%m%d-%H%M%S")
        if st is None:
            continue
        name = f"실행기 {wf or '?'}/{job or '?'}"
        can_ts = _utc(can, "%Y-%m-%d %H:%M:%S") if can else None
        end_ts = _utc(end, "%Y-%m-%d %H:%M:%S") if end else None
        if res == "Succeeded":
            out.append(Event(name, end_ts or st, "ok", "성공"))
        elif can_ts or res in ("Canceled", "Cancelled"):
            t = can_ts or end_ts or st
            mins = int((t - st).total_seconds() // 60)
            out.append(_worker_fail(name, st, t, f"시작 {mins}분 뒤 취소(Cancellation)", gate))
        elif res:
            out.append(_worker_fail(name, st, end_ts or st, f"작업 결과 {res}", gate))
        # 결과·취소 둘 다 없으면 아직 도는 중 → 사건 아님
    return out


def gate_events(gate: list[GateLine], echo: bool = False) -> list[Event]:
    """관문 포기 줄. echo=True(실행기 실패가 이미 관문 대기로 설명됨)면 '주의'로 낮춘다:
    취소된 작업의 관문 훅이 뒤늦게 '포기'를 찍는 메아리라 같은 사건을 두 번 세지 않기 위해서다."""
    out = []
    for g in gate:
        if g.kind == "giveup":
            out.append(Event("실행기 관문(job_started)", g.ts, "warn" if echo else "fail", g.text,
                             "관문 조건(메모리 3GB·리셋 회피창) 미충족으로 포기"
                             + (" — 위 실행기 실패와 같은 사건의 기록" if echo else "")))
        elif g.kind == "pass":
            out.append(Event("실행기 관문(job_started)", g.ts, "ok", g.text))
    return out


_CHECK_RX = re.compile(r"^== (\S+) (\S+) rc=(\d+)")


def parse_checks(lines: list[str]) -> list[Event]:
    """checks.log: '== ISO 이름 rc=N' 머리줄과 그 아래 상세 줄."""
    out, cur, detail = [], None, []

    def flush():
        if cur:
            ts, name, rc = cur
            if rc == 0:
                out.append(Event(f"점검 {name}", ts, "ok"))
            else:
                rep = next((d.strip() for d in detail if d.strip() and not d.strip().endswith(":")), "")
                rep = rep or next((d.strip() for d in detail if d.strip()), f"rc={rc}")
                out.append(Event(f"점검 {name}", ts, "fail", rep))

    for ln in lines:
        m = _CHECK_RX.match(ln)
        if m:
            flush()
            ts = _iso(m.group(1))
            cur = (ts, m.group(2), int(m.group(3))) if ts else None
            detail = []
        elif cur:
            detail.append(ln)
    flush()
    return out


def parse_backup(lines: list[str], name: str) -> list[Event]:
    """'== ISO' 머리줄 뒤 OK/FAIL/DONE 줄."""
    out, ts = [], None
    for ln in lines:
        s = ln.strip()
        if s.startswith("== "):
            ts = _iso(s[3:].split()[0])
            continue
        if ts is None:
            continue
        if s.startswith("FAIL") or "ERROR" in s or "실패" in s:
            out.append(Event(name, ts, "fail", s))
        elif s.startswith("OK") or s == "DONE":
            out.append(Event(name, ts, "ok", s))
    return out


_IG_RX = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC (.*)$")


def parse_idle_guard(lines: list[str]) -> list[Event]:
    out = []
    for ln in lines:
        m = _IG_RX.match(ln)
        if not m:
            continue
        ts = _utc(m.group(1), "%Y-%m-%d %H:%M:%S")
        body = m.group(2)
        if re.search(r"Traceback|Error|오류|실패", body):
            out.append(Event("공장 idle_guard", ts, "fail", body))
        elif "큐가 비어" in body:
            out.append(Event("공장 대기열", ts, "warn", body, "다음 편 큐가 비어 있음(핏이 다음 편 투입 필요)"))
        else:
            out.append(Event("공장 idle_guard", ts, "ok"))
    return out


_HERMES_RX = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)[,.]\d+ (WARNING|ERROR|CRITICAL) (.*)$")


def parse_hermes(lines: list[str]) -> list[Event]:
    out = []
    for ln in lines:
        m = _HERMES_RX.search(ln)
        if not m:
            continue
        ts = _utc(m.group(1), "%Y-%m-%d %H:%M:%S")
        kind = "warn" if m.group(2) == "WARNING" else "fail"
        out.append(Event("헤르메스 게이트웨이", ts, kind, m.group(3).strip()))
    return out


def parse_now(lines: list[str]) -> dict:
    st = {"mem": None, "mounts": {}, "runner": None, "hermes": None}
    for ln in lines:
        p = ln.split()
        if not p:
            continue
        if p[0] == "MEM" and len(p) > 1 and p[1].isdigit():
            st["mem"] = int(p[1])
        elif p[0] == "MOUNT" and len(p) > 2:
            st["mounts"][p[1]] = p[2] == "OK"
        elif p[0] == "RUNNER":
            st["runner"] = p[-1] == "OK"
        elif p[0] == "HERMES":
            st["hermes"] = p[-1] == "OK"
    return st


# ---------------------------------------------------------------- 원인 후보 규칙표
# (대표 오류 문구 정규식, 원인 후보). 위에서부터 첫 번째 일치를 쓴다. 새 사고가 나면 여기에 한 줄 더한다.
CAUSE_RULES = [
    (r"Killed|OOM|out of memory|MemoryError", "메모리 부족으로 프로세스 강제 종료(OOM)"),
    (r"No space|ENOSPC|공간 부족", "디스크 공간 부족"),
    (r"mountpoint|마운트|Transport endpoint", "디스크·rclone 마운트 NG"),
    (r"FAIL verify", "백업 번들 검증 실패(그 날짜 번들 없음·HDD 마운트·백업 시각 순서 후보)"),
    (r"pull 실패", "구PC 저장소 사본 git pull 실패(인증 만료·로컬 충돌 후보)"),
    (r"401|403|Unauthorized|[Aa]uth(?:entication)? failed|invalid_grant|expired|만료|인증", "인증 만료·권한 거절"),
    (r"폴리싱|기한|일 전\(기준", "정기 점검 기한 경과 알림(작업 고장 아님)"),
    (r"NetworkError|Timeout|timed out|ConnectionRefused|연결", "네트워크 일시 오류(자동 재시도 대상)"),
    (r"Traceback|Error|오류", "스크립트 예외(원문 로그 확인 필요)"),
]


def rule_cause(text: str) -> str:
    for rx, cause in CAUSE_RULES:
        if re.search(rx, text):
            return cause
    return "규칙표에 없는 패턴(원문 확인, 맞으면 CAUSE_RULES에 추가)"


# ---------------------------------------------------------------- 묶기
def group(events: list[Event], start: datetime, end: datetime) -> "OrderedDict[str, Item]":
    items: "OrderedDict[str, Item]" = OrderedDict()
    for e in sorted(events, key=lambda e: e.ts):
        it = items.setdefault(e.name, Item(e.name))
        if e.kind == "ok":
            if e.ts <= end:
                it.last_ok = e.ts if it.last_ok is None or e.ts > it.last_ok else it.last_ok
            continue
        if not (start <= e.ts <= end):
            continue
        if e.kind == "fail":
            it.fails += 1
        else:
            it.warns += 1
        if not it.rep:
            it.rep = mask(e.text)[:90]
        if e.cause == "@gate":
            it.gate_hits += 1
            it.gate_low += e.gate_low
            it.gate_window = it.gate_window or e.gate_window
            continue
        c = e.cause or rule_cause(e.text)
        if c not in it.causes:
            it.causes.append(c)
    return items


def collect_events(sec: dict[str, list[str]]) -> tuple[list[Event], dict]:
    gate = parse_gate(sec.get("gate", []))
    ev: list[Event] = []
    workers = parse_workers(sec.get("workers", []), gate)
    ev += workers
    ev += gate_events(gate, echo=any(e.cause == "@gate" for e in workers))
    ev += parse_checks(sec.get("checks", []))
    ev += parse_backup(sec.get("backup_private", []), "백업 비공개 저장소")
    ev += parse_backup(sec.get("backup_hdd", []), "백업 HDD")
    ev += parse_backup(sec.get("backup_hdd_verify", []), "백업 HDD 검증")
    ev += parse_idle_guard(sec.get("idle_guard", []))
    ev += parse_hermes(sec.get("hermes", []))
    now = parse_now(sec.get("now", []))
    now["watch"] = (sec.get("watch") or [""])[-1].strip()
    now["keepalive_starts"] = [ln for ln in sec.get("keepalive", []) if ln.strip()]
    return ev, now


# ---------------------------------------------------------------- 한 장 만들기
def _k(ts: datetime | None) -> str:
    return ts.astimezone(KST).strftime("%m-%d %H:%M") if ts else "창 안에 없음"


def render(items: "OrderedDict[str, Item]", now: dict, start: datetime, end: datetime) -> str:
    bad = [i for i in items.values() if i.fails]
    warn = [i for i in items.values() if not i.fails and i.warns]
    ok = [i for i in items.values() if not i.fails and not i.warns and i.last_ok]
    bad.sort(key=lambda i: -i.fails)
    warn.sort(key=lambda i: -i.warns)

    head = f"# 구PC 실행 로그 한 장 {end.astimezone(KST):%Y-%m-%d} (창 {_k(start)}~{_k(end)} KST, 규칙 기반·토큰 0)"
    if bad:
        top = bad[0]
        concl = (f"결론: 실패 {len(bad)}종 총 {sum(i.fails for i in bad)}회. 가장 많은 것은 {top.name} "
                 f"{top.fails}회, 원인 후보 = {top.cause_list()[0]}")
    elif warn:
        concl = f"결론: 실패 없음, 주의 {len(warn)}종({warn[0].name}: {warn[0].cause_list()[0]})"
    else:
        concl = "결론: 실패·주의 없음"
    lines = [head, concl]

    body = []
    for i in bad:
        body.append(f"- [실패] {i.name}: {i.fails}회 · 마지막 성공 {_k(i.last_ok)} · \"{i.rep}\" → 원인 후보: "
                    + "; ".join(i.cause_list()[:2]))
    for i in warn:
        body.append(f"- [주의] {i.name}: {i.warns}회 · \"{i.rep[:60]}\" → {i.cause_list()[0]}")
    tail = []
    if ok:
        names = ", ".join(i.name for i in ok[:6]) + (f" 외 {len(ok) - 6}" if len(ok) > 6 else "")
        tail.append(f"- 정상(창 안 실패 없음) {len(ok)}종: {names}")
    m = now.get("mounts", {})
    mem = now.get("mem")
    st = [f"여유 메모리 {mem}MB" + (" (관문 3GB 미만)" if mem is not None and mem < GATE_MEM_MB else "") if mem is not None else "메모리 미확인",
          f"마운트 {sum(m.values())}/{len(m)} OK" + ("" if all(m.values()) else " NG: " + ",".join(k for k, v in m.items() if not v)),
          f"실행기 {'떠 있음' if now.get('runner') else '안 떠 있음'}",
          f"헤르메스 {'active' if now.get('hermes') else '비활성'}"]
    if now.get("watch"):
        st.append(f"watch \"{mask(now['watch'])[:30]}\"")
    tail.append("- 지금: " + " · ".join(st))
    tail.append("- 한계: 원인은 규칙표 추정(판정은 사람), 원문은 ssh goosolar 의 같은 로그를 tail로 확인")

    room = MAX_LINES - len(lines) - len(tail)
    if len(body) > room:
        hidden = len(body) - (room - 1)
        body = body[: room - 1] + [f"- … 외 {hidden}건(--stdout 로 전체 보기는 MAX_LINES 조정)"]
    out = "\n".join(mask(l) for l in lines + body + tail)
    return out + "\n"


def build(raw: str, start: datetime, end: datetime) -> str:
    ev, now = collect_events(split_sections(raw))
    return render(group(ev, start, end), now, start, end)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="구PC 자동 실행 로그 한 장 요약(읽기 전용, 규칙 기반)")
    ap.add_argument("--end-kst", help="창 끝 시각(KST, 'YYYY-MM-DD HH:MM'). 기본 지금")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--host", default=SSH_HOST)
    ap.add_argument("--stdout", action="store_true", help="파일로 저장하지 않고 화면에만")
    ap.add_argument("--raw-in", help="(시험·재현용) ssh 대신 이 파일의 수집 텍스트를 쓴다")
    a = ap.parse_args(argv)

    for s in (sys.stdout, sys.stderr):  # pythonw면 None이다(10/20 brief_snapshot 사고)
        if s is not None and hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    replay = bool(a.end_kst)
    end = (datetime.strptime(a.end_kst, "%Y-%m-%d %H:%M").replace(tzinfo=KST) if replay
           else datetime.now(KST)).astimezone(UTC)
    start = end - timedelta(hours=a.hours)
    raw = Path(a.raw_in).read_text(encoding="utf-8") if a.raw_in else fetch_remote(start, end, a.host)
    text = build(raw, start, end)
    if a.stdout:
        print(text, end="")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ek = end.astimezone(KST)
    path = OUT_DIR / (f"{ek:%Y-%m-%d}_{ek:%H%M}.md" if replay else f"{ek:%Y-%m-%d}.md")
    path.write_text(text, encoding="utf-8")
    print(f"저장: {path} ({len(text.splitlines())}줄)")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
