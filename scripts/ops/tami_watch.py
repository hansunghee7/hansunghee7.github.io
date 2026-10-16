# -*- coding: utf-8 -*-
"""오퍼스 타미 당직(구 페이블 타미)(2026-10-15 탐, 사장님: "페이블 타미 세팅하죠, 최고의 활용 포인트" / 사용 범위 = 이상이 있을 때만 부르기).
매시간 스크립트가 숫자만 본다(토큰 0). 이상이 있을 때만 타미(헤르메스 tami 프로필)를 페이블 모델로 1회 깨워 원인을 판정하게 하고 텔레그램으로 알린다.
보는 것(v1):
  ① 공장(구PC·신PC 브라우저 계정별): 크레딧 READ_H시간 넘게 못 읽음 / 크레딧 MIN_CREDIT 이상인데 새 컷이 IDLE_H시간 넘게 없음  (fit_db.py factory)
  ② 수집·주기 작업: 상태판(C:/work/_ops/STATUS.md)의 🔴 줄
  ③ 데이터 수집 파이프 대장(opsdb data_pipelines): 작동 중인데 마지막 성공이 신선도 기준을 넘은 파이프
판정 연결: 담당 에이전트 우편함(공장=핏, 파이프=대장 담당, 나머지=탐), 사장님 할 일이 있을 때만 텔레그램.
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
MAILBOX = Path("C:/work/solar-bible/mailbox/mailbox.py")
CHANNEL_REPO = "hansunghee7/tami-duty-channel"  # 비공개, 타미 계정(ilovetommy)만 협업자(사장님 허용 10/15)
CHANNELS = {"탐": 1, "핏": 2, "마야": 3}  # 담당별 채널 PR 번호(병합 금지), 그 세션이 구독한다
TAMI_GH = Path("C:/work/_ops/tami_gh")  # 타미 계정 gh 로그인 폴더(키 값은 운영체제 자격 증명 저장소)
HERMES = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "bin" / "hermes.exe"
TAMI_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "profiles" / "tami"
MODELS = ("claude-opus-5-5",)  # 오퍼스 타미(사장님 10/16 "오퍼스 타미로 가죠", 페이블은 프로모션 크레딧 미적용으로 거절됨)
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


def pipeline_anomalies(rows, now):
    """데이터 수집 파이프 대장(data_pipelines): '작동' 파이프의 마지막 성공이 기준 신선도를 넘으면 이상(사장님 10/15 "데이터 파이프라인 수집도 판정")."""
    out = []
    for p in rows:
        if p.get("status") != "작동" or not p.get("freshness_hours"):
            continue
        ls = p.get("last_success")
        try:
            age = (now - datetime.fromisoformat(str(ls)).astimezone().replace(tzinfo=None)).total_seconds() / 3600 if ls else None
        except ValueError:
            age = None
        if age is None or age > float(p["freshness_hours"]):
            out.append((age, f"[수집 파이프·{p.get('owner') or '탐'}] {p.get('name', p.get('slug'))} — 마지막 성공 " + (f"{age:.0f}시간 전" if age is not None else "기록 없음") + f"(기준 {p['freshness_hours']}시간)"))
    ages = [a for a, _ in out if a is not None]
    # 여러 파이프가 거의 같은 시각에 멈췄으면 파이프마다가 아니라 '마지막 성공을 옮겨 적는 동기화'가 멈춘 것(10/15 첫 실행: 28개가 97~134시간 전으로 몰림)
    if len(out) >= 5 and ages and max(ages) - min(ages) < 48:
        return [f"[수집 파이프·탐] 대장의 마지막 성공 기록이 {len(out)}개 파이프에서 함께 멈춤({min(ages):.0f}~{max(ages):.0f}시간 전) — 파이프 고장보다 동기화(pipeline_sync.py) 정체 의심"]
    return [t for _, t in out]


def owner_of(item):
    """이상 신호를 받을 에이전트: 공장은 핏, 수집 파이프는 대장의 담당, 나머지 주기 작업은 탐."""
    if item.startswith(("[구PC", "[신PC", "공장")):
        return "핏"
    m = re.match(r"\[수집 파이프·([^\]]+)\]", item)
    return m.group(1) if m else "탐"


def collect():
    now = datetime.now()
    items = []
    try:
        import opsdb
        items += pipeline_anomalies(opsdb.select("data_pipelines", "slug,name,owner,status,freshness_hours,last_success", limit=500), now)
    except Exception as e:  # DB가 안 되면 파이프 판정만 빠진다
        items.append(f"수집 파이프 대장 읽기 실패: {str(e)[:80]}")
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


def fell_back(log, start):
    """이번 호출에서 헤르메스가 대체 모델로 넘어갔으면 그 이유 한 줄, 아니면 빈 문자열."""
    try:
        with open(log, "rb") as f:
            f.seek(start)
            new = f.read().decode("utf-8", "replace")
    except OSError:
        return ""
    if "credit balance is too low" in new:
        return "클로드 크레딧 부족(400)"
    m = re.search(r"Fallback activated: ([^\n]+)", new)
    return ("대체 모델 전환 " + m.group(1)[:80]) if m else ""


def wake_tami(items):
    import api_run
    key = api_run.find_key()
    if not key:
        return "타미 깨우기 실패: 키 없음"
    q = ("너는 우리 회사 당직이다(읽기 전용). 아래 이상 신호의 원인을 진단하라. 파일·로그를 읽어 근거를 확인하고, 구PC는 `ssh goosolar`로 읽기만 하라. "
         "고치기·재시작·삭제·발송은 절대 하지 않는다. 참고: 공장 장부 `python C:/work/shorts-lab/tools/factory/fit_db.py factory`, 상태판 C:/work/_ops/STATUS.md, 감시 대장 C:/work/hansunghee7.github.io/scripts/ops/jobs.toml.\n"
         "출력(한국어, 12줄 이내): 신호마다 '원인(확인됨/추정) / 근거 한 줄 / 누가 무엇을 하면 되는지(핏·탐·사장님)'. 끝에 '사장님이 할 일: 없음' 또는 한 줄.\n\n이상 신호:\n- " + "\n- ".join(items))
    env = dict(os.environ, ANTHROPIC_API_KEY=key, HERMES_HOME=str(TAMI_HOME), PYTHONIOENCODING="utf-8")
    # 판정이 안 나오면(10/15 22:50 실측: 페이블이 '잔액 부족' 400 → 헤르메스가 로컬 qwen으로 넘어가 엉뚱한 실패) 다음 모델로. 판정 성공 = '사장님이 할 일' 줄이 있음
    log = Path(TAMI_HOME) / "logs" / "agent.log"
    for model in MODELS:
        start = log.stat().st_size if log.exists() else 0
        r = subprocess.run([str(HERMES), "chat", "-q", q, "--oneshot", "-Q", "--provider", "anthropic", "-m", model],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900, creationflags=FLAGS)
        text = re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + ("\n" + r.stderr if r.returncode else "")).replace(key, "***")
        # 10/16 실측: 클로드가 '잔액 부족'으로 거절되면 헤르메스가 무료 대체 모델(qwen·nemotron)로 넘어가 답하는데,
        # 겉으로는 '판정 모델: claude-opus-5-5'로 찍혔다(10/15 22:41부터 52회). 무료 엔진은 판정 금지라 대체 모델 답은 실패로 본다.
        fell = fell_back(log, start)
        if fell:
            text = f"(클로드 호출 실패로 대체 모델이 답함: {fell}, 판정으로 쓰지 않음)\n" + text
        ok = "사장님이 할 일" in text and not fell
        with (Path("C:/work/_ops") / "agent_calls.csv").open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%F %T')},타미-{model},0,{r.returncode if ok else 9},{len(text.encode())},0\n")
        if ok:
            return f"(판정 모델: {model})\n" + text.strip()[-3000:]
    return "판정 실패(모든 모델): " + text.strip()[-400:]


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
    # 판정을 일할 에이전트에게 연결(사장님 10/15 "판정한 게 핏이나 워크플로우에게 연결되는 구조인가요?"): 담당 우편함으로, 사장님 할 일이 있을 때만 텔레그램
    owners = sorted({owner_of(x) for x in items})
    sent = []
    for who in owners:
        mine = [x for x in items if owner_of(x) == who]
        body = "이상 신호(" + who + " 담당):\n- " + "\n- ".join(mine) + f"\n\n페이블 타미 판정 전문: {rep}\n\n" + verdict[-2500:]
        r = subprocess.run([sys.executable, str(MAILBOX), "send", who, f"타미 당직 이상 {len(mine)}건", "--from", "타미", "--body", body,
                            "--ask", "판정의 '누가 무엇을' 중 내 몫을 처리하고, 끝나면 공장 장부·대장 상태를 고친다"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=FLAGS, cwd=str(MAILBOX.parent.parent))
        sent.append(f"{who}{'' if r.returncode == 0 else '(실패)'}")
        # 떠 있는 세션을 바로 깨우기(10/15 실측: 타미 계정 댓글 → 구독 세션 약 27초 뒤 깨어남, 교신 001 안내서 4절 C 방식). 우편은 닫힌 세션용으로 그대로 둔다
        if who in CHANNELS and TAMI_GH.exists():
            c = subprocess.run(["gh", "pr", "review", str(CHANNELS[who]), "--repo", CHANNEL_REPO, "--comment", "--body", body[:60000]],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=FLAGS,
                               env=dict(os.environ, GH_CONFIG_DIR=str(TAMI_GH)))
            sent[-1] += "+채널" if c.returncode == 0 else "+채널실패"
    boss_line = next((ln for ln in verdict.splitlines() if "사장님이 할 일" in ln), "")
    tg_note = "텔레그램 안 보냄(사장님 할 일 없음)"
    if boss_line and "없음" not in boss_line:
        msg = f"[타미 당직] 사장님 확인 필요\n{boss_line.strip()}\n\n" + "\n".join("· " + x for x in items[:6])
        tg = subprocess.run([sys.executable, str(HERE / "tg_boss.py"), "text", msg, "--persona", "탐"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=FLAGS)
        tg_note = "텔레그램 " + ("보냄" if tg.returncode == 0 else "실패")
    print(f"타미 당직: 이상 {len(items)}건 판정 → {rep} / 우편: {', '.join(sent)} / {tg_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
