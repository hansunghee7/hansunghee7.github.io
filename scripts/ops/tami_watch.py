# -*- coding: utf-8 -*-
"""페이블 타미 당직(2026-10-15 탐, 사장님: "페이블 타미 세팅하죠, 최고의 활용 포인트" / 사용 범위 = 이상이 있을 때만 부르기).
매시간 스크립트가 숫자만 본다(토큰 0). 이상이 있을 때만 타미(헤르메스 tami 프로필)를 페이블 모델로 1회 깨워 원인을 판정하게 하고 텔레그램으로 알린다.
보는 것(v1):
  ① 공장(구PC·신PC 브라우저 계정별): 크레딧 READ_H시간 넘게 못 읽음 / 크레딧 MIN_CREDIT 이상인데 새 컷이 IDLE_H시간 넘게 없음  (fit_db.py factory)
  ② 수집·주기 작업: 상태판(C:/work/_ops/STATUS.md)의 🔴 줄
같은 이상 묶음은 REPEAT_H시간 안에 다시 깨우지 않는다(상태 C:/work/_ops/tami_watch/state.json).
타미 권한: 읽기 전용 진단 지시(파일·로그 읽기, 구PC는 ssh goosolar로 읽기만). 고치기·재시작·발송은 하지 않고 판정과 추천만 낸다.
키: api_run.find_key()로 실행할 때만 환경변수로 넘긴다(설정 파일에 키를 쓰지 않음, 값은 출력하지 않음).
사용: python scripts/ops/tami_watch.py [--dry] [--force]   (--dry = 이상 목록만, --force = 반복 억제 무시)"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = Path("C:/work/_ops/tami_watch")
STATE = OUT / "state.json"
STATUS = Path("C:/work/_ops/STATUS.md")
FIT_DB = Path("C:/work/shorts-lab/tools/factory/fit_db.py")
HERMES = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "bin" / "hermes.exe"
TAMI_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "profiles" / "tami"
MODEL = "claude-fable-5-1"
READ_H, IDLE_H, MIN_CREDIT, REPEAT_H = 8, 12, 6, 6
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ago_h(stamp, now):
    """'10-15 16:28' 같은 표기를 지금부터 몇 시간 전인지로. 못 읽으면 None."""
    m = re.match(r"(\d{2})-(\d{2}) (\d{2}):(\d{2})", stamp or "")
    if not m:
        return None
    t = datetime(now.year, int(m[1]), int(m[2]), int(m[3]), int(m[4]))
    return (now - t).total_seconds() / 3600


def factory_anomalies(csv_text, now):
    out = []
    lines = [x for x in csv_text.splitlines() if x.count(",") >= 6]
    if not lines or not lines[0].startswith("account,"):
        return ["공장 장부를 읽지 못함(fit_db.py factory 출력 형식 다름)"]
    for ln in lines[1:]:
        c = ln.split(",")
        acct, pc, credits, read_at, last_cut = c[0], c[1], c[2], c[3], c[5]
        try:
            cr = int(credits)
        except ValueError:
            cr = None
        r = ago_h(read_at, now)
        if r is not None and r > READ_H:
            out.append(f"[{pc} {acct}] 크레딧을 {r:.0f}시간째 못 읽음(마지막 {read_at})")
        lc = ago_h(last_cut, now)
        if cr is not None and cr >= MIN_CREDIT and (lc is None or lc > IDLE_H):
            out.append(f"[{pc} {acct}] 크레딧 {cr} 남았는데 새 컷이 " + (f"{lc:.0f}시간째 없음" if lc else "기록 없음") + f" (메모: {c[7] if len(c) > 7 else ''})")
    return out


def status_anomalies(text):
    out = []
    for ln in text.splitlines():
        if ln.startswith("| 🔴"):
            c = ln.split("|")
            out.append("[수집·주기 작업] " + re.sub(r"\s+", " ", c[2]).strip()[:70] + " — " + re.sub(r"\s+", " ", c[3] if len(c) > 3 else "").strip()[:110])
    return out


def collect():
    now = datetime.now()
    items = []
    try:
        r = subprocess.run([sys.executable, str(FIT_DB), "factory"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=FLAGS,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        items += factory_anomalies(r.stdout, now)
    except (OSError, subprocess.SubprocessError) as e:
        items.append(f"공장 장부 읽기 실패: {e}")
    try:
        items += status_anomalies(STATUS.read_text(encoding="utf-8"))
    except OSError:
        items.append("상태판 파일 없음")
    return items


def wake_tami(items):
    import api_run
    key = api_run.find_key()
    if not key:
        return "타미 깨우기 실패: 키 없음"
    q = ("너는 우리 회사 당직이다(읽기 전용). 아래 이상 신호의 원인을 진단하라. 파일·로그를 읽어 근거를 확인하고, 구PC는 `ssh goosolar`로 읽기만 하라. "
         "고치기·재시작·삭제·발송은 절대 하지 않는다. 참고: 공장 장부 `python C:/work/shorts-lab/tools/factory/fit_db.py factory`, 상태판 C:/work/_ops/STATUS.md, 감시 대장 C:/work/hansunghee7.github.io/scripts/ops/jobs.toml.\n"
         "출력(한국어, 12줄 이내): 신호마다 '원인(확인됨/추정) / 근거 한 줄 / 누가 무엇을 하면 되는지(핏·탐·사장님)'. 끝에 '사장님이 할 일: 없음' 또는 한 줄.\n\n이상 신호:\n- " + "\n- ".join(items))
    env = dict(os.environ, ANTHROPIC_API_KEY=key, HERMES_HOME=str(TAMI_HOME), PYTHONIOENCODING="utf-8")
    r = subprocess.run([str(HERMES), "chat", "-q", q, "--oneshot", "-Q", "--provider", "anthropic", "-m", MODEL],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900, creationflags=FLAGS)
    text = re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + ("\n" + r.stderr if r.returncode else "")).replace(key, "***")
    with (Path("C:/work/_ops") / "agent_calls.csv").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%F %T')},타미-페이블,0,{r.returncode},{len(text.encode())},0\n")
    return text.strip()[-3000:]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    items = collect()
    if "--dry" in a:
        print("\n".join(items) or "이상 없음")
        return 0
    if not items:
        print("타미 당직: 이상 없음")
        return 0
    h = hashlib.sha1("\n".join(sorted(re.sub(r"\d+시간", "N시간", x) for x in items)).encode()).hexdigest()[:12]
    try:
        st = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    if "--force" not in a and st.get("hash") == h and time.time() - st.get("at", 0) < REPEAT_H * 3600:
        print(f"타미 당직: 이상 {len(items)}건(이미 보고함, {REPEAT_H}시간 안 반복 억제)")
        return 0
    verdict = wake_tami(items)
    rep = OUT / f"report_{time.strftime('%Y%m%d_%H%M')}.md"
    rep.write_text("## 이상 신호\n- " + "\n- ".join(items) + "\n\n## 페이블 타미 판정\n" + verdict, encoding="utf-8")
    STATE.write_text(json.dumps({"hash": h, "at": time.time(), "report": str(rep)}, ensure_ascii=False), encoding="utf-8")
    msg = f"[타미 당직] 이상 {len(items)}건\n" + "\n".join("· " + x for x in items[:6]) + "\n\n" + verdict[-1500:]
    tg = subprocess.run([sys.executable, str(HERE / "tg_boss.py"), "text", msg, "--persona", "탐"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=FLAGS)
    print(f"타미 당직: 이상 {len(items)}건 판정 → {rep} / 텔레그램 {'보냄' if tg.returncode == 0 else '실패 ' + (tg.stderr or tg.stdout)[-120:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
