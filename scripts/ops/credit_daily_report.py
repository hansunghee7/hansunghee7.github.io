# -*- coding: utf-8 -*-
"""Claude API 프로모션 크레딧(US$99.50, 10/28 UTC 만료) 일일 소진 리포트 (2026-10-13 탐).

사장님 지시(2026-10-13): 한도는 두지 않되 일일 사용량 리포트를 사장님과 탐이 인지할 수 있게, 탐이 보고 행동할 수 있게.
읽는 곳: 호출 장부 C:/work/_ops/claude_api_usage.csv (api_run.py·credit_run.py가 기록. 래퍼 기준이라 콘솔과 오차가 있다).
계획서: C:/work/_ops/pass_openbeta/credit_plan/클로드API_크레딧_소진계획_초안_1013.md 1절(체크포인트)·3절(예비 작업).

사용:
  python credit_daily_report.py status            리포트·행동 목록·상태 파일 갱신(텔레그램 없음). 지연·위험이면 종료 코드 1(감시 대장 cmd 항목용)
                                                  한국시간 21시 이후 오늘 아직 안 보냈으면 텔레그램도 보냄(스케줄러가 못 돌았을 때의 안전망)
  python credit_daily_report.py daily             갱신 + 텔레그램 5줄(하루 1회만, --force로 재전송)
  python credit_daily_report.py record-console --remaining 97.2 --source "콘솔 화면 읽기"   콘솔 잔액 대조 기록(에이전트가 기록)
옵션: --now 2026-10-16T21:00 (한국시간 가짜 현재, 시험용)
환경: CREDIT_LEDGER, CREDIT_DAILY_DIR(기본 C:/work/_ops/credit_daily), CREDIT_NO_TELEGRAM=1(시험)
상태: 앞섬 / 정상 / 지연 / 위험 / 완료.  장부 비용 = 래퍼 기록값(가격 미확인 모델은 래퍼가 최고 단가로 넣는다).
"""
import argparse, csv, json, os, subprocess, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
TOTAL = 99.50                                   # 분모: 프로모션 잔액(10/13 콘솔)
START = datetime(2026, 10, 13, 0, 0, tzinfo=KST)
DEADLINE = datetime(2026, 10, 27, 21, 0, tzinfo=KST)
GOAL = 98.5                                     # 마감 최소 누적
# (시각, 최소 누적 달러). 사이는 직선으로 잇는다.
CHECKPOINTS = [
    (START, 0.0),
    (datetime(2026, 10, 17, 0, 0, tzinfo=KST), 25.0),   # 10/16 24시
    (datetime(2026, 10, 21, 0, 0, tzinfo=KST), 52.0),   # 10/20 24시
    (datetime(2026, 10, 25, 0, 0, tzinfo=KST), 80.0),   # 10/24 24시
    (DEADLINE, GOAL),
]
LATE_USD, DANGER_USD = 3.0, 8.0                 # 계획서 1절 증액 규칙
AHEAD_RATIO = 1.3                               # 최소 목표의 130% 초과면 앞섬
CONSOLE_STALE_DAYS = 2

# 예비 작업(계획서 3절). (이름, 대략 달러, 한 줄 명령 또는 미구현 표시)
RESERVE = [
    ("묶음5 병합 PR diff 리뷰", 15.0, 'python C:/work/_ops/pass_openbeta/credit_plan/runC/b05_pr_review.py'),
    ("묶음1 카빗 패스 단방향 재검증(변경 조각)", 12.2, 'python C:/work/_ops/pass_openbeta/credit_plan/runA/run1.py'),
    ("묶음3 N181 표본 40→80 확대", 27.0, '# 미구현: 헤르메스 A/B 실행 스크립트가 아직 없음(계획서 2절 묶음3 선결 과제)'),
    ("묶음9 경험 카드 2회 독립 추출", 13.0, '# 미구현: 블로그 400편 추출 스크립트가 아직 없음(계획서 2절 묶음9)'),
    ("묶음8 상담 시뮬 300→600", 11.6, '# 미구현: 상담 시뮬 스크립트가 아직 없음(계획서 2절 묶음8)'),
    ("묶음12 품질 평가 40→100쌍", 7.8, '# 미구현: 품질 평가 스크립트가 아직 없음(계획서 2절 묶음12)'),
    ("묶음7 백로그 정리 재실행", 4.2, 'python C:/work/_ops/pass_openbeta/credit_plan/runB/b7.py'),
]


def ledger_path():
    p = os.environ.get("CREDIT_LEDGER")
    return Path(p) if p else Path("C:/work/_ops/claude_api_usage.csv")


def daily_dir():
    return Path(os.environ.get("CREDIT_DAILY_DIR") or "C:/work/_ops/credit_daily")


def parse_ts(s):
    s = s.strip().replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(KST)


def read_ledger(path):
    """장부에서 10/13 이후 성공 행만. 실패 행(fail:...)은 돈이 안 든 것으로 본다."""
    rows = []
    if not Path(path).exists():
        return rows
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            st = (r.get("status") or "").strip()
            if not st.startswith("ok"):
                continue
            try:
                t = parse_ts(r["ts"])
                cost = float(r.get("cost_usd") or 0)
            except (ValueError, KeyError):
                continue
            if t < START:
                continue
            rows.append({"t": t, "who": r.get("who", ""), "model": r.get("model", ""), "cost": cost,
                         "unpriced": "가격미확인" in st})
    return rows


def target_at(t):
    """시각 t의 최소 누적 목표(체크포인트 사이 직선)."""
    if t <= CHECKPOINTS[0][0]:
        return 0.0
    for (t0, v0), (t1, v1) in zip(CHECKPOINTS, CHECKPOINTS[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return GOAL


def next_checkpoint(t):
    for ct, v in CHECKPOINTS[1:]:
        if t <= ct:
            return ct, v
    return DEADLINE, GOAL


def classify(spent, target):
    gap = target - spent                      # 양수 = 모자람
    if spent >= GOAL:
        return "완료", gap
    if gap >= DANGER_USD:
        return "위험", gap
    if gap >= LATE_USD:
        return "지연", gap
    if spent > target * AHEAD_RATIO and spent - target >= 2.0:
        return "앞섬", gap
    return "정상", gap


def load_console(d):
    p = d / "console_check.json"
    if not p.exists():
        return {"baseline_usd": TOTAL, "checks": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {"baseline_usd": TOTAL, "checks": []}


def init_console(d):
    p = d / "console_check.json"
    if not p.exists():
        d.mkdir(parents=True, exist_ok=True)
        data = {"note": "에이전트가 기록한다: python credit_daily_report.py record-console --remaining <콘솔 잔액 달러> --source <출처>. 구조: checks[] = {date, remaining_usd, source, recorded_at}. 콘솔 소진 = baseline - remaining",
                "baseline_usd": TOTAL,
                "checks": [{"date": "2026-10-13", "remaining_usd": 99.50, "source": "사장님 콘솔 화면(10/13 08:53 KST), 원금 100·사용 0.50",
                            "recorded_at": "2026-10-13T08:53:00+09:00"}]}
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compute(now):
    rows = read_ledger(ledger_path())
    spent = sum(r["cost"] for r in rows)
    today = now.date()
    today_cost = sum(r["cost"] for r in rows if r["t"].date() == today)
    by_day = defaultdict(lambda: defaultdict(float))
    by_who = defaultdict(float)
    for r in rows:
        by_day[r["t"].date().isoformat()][r["model"]] += r["cost"]
        by_who[r["who"]] += r["cost"]
    target = target_at(now)
    status, gap = classify(spent, target)
    hours_left = max((DEADLINE - now).total_seconds() / 3600, 0.0)
    days_left = hours_left / 24
    need_rate = max(GOAL - spent, 0.0) / days_left if days_left > 0.01 else float("inf") if spent < GOAL else 0.0
    return dict(rows=rows, spent=spent, today=today_cost, by_day=by_day, by_who=by_who, target=target,
                status=status, gap=gap, days_left=days_left, need_rate=need_rate,
                unpriced=sum(1 for r in rows if r["unpriced"]), unpriced_usd=sum(r["cost"] for r in rows if r["unpriced"]))


def pick_actions(status, gap):
    """권고 행동 목록: (설명, 명령). 계획서 1절 증액 규칙."""
    acts = []
    if status in ("지연", "위험"):
        need = gap * 1.2
        acts.append((f"모자란 {gap:.1f}달러의 120%인 약 {need:.1f}달러어치를 예비 작업에서 추가 발주", None))
        left = need
        for name, usd, cmd in RESERVE:
            if left <= 0:
                break
            acts.append((f"{name} (약 {usd:.1f}달러)", cmd))
            left -= usd
        if left > 0:
            acts.append((f"예비 목록을 다 써도 약 {left:.1f}달러 부족: 묶음을 새로 설계하거나 상위 모델 교차 패스를 추가", None))
        if status == "위험":
            acts.append(("배치 호출을 끄고 동기 호출로 바꾸며 캐시를 쓰지 않는다", "# 래퍼는 배치 미지원이라 이미 동기. 프롬프트 캐시 옵션 사용 중이면 끈다"))
            acts.append(("상위 모델(Opus·Fable) 비중을 늘린다(소각이 아니라 독립 패스·교차 검증으로)", None))
    elif status == "앞섬":
        acts.append(("최소 목표의 130%를 넘어 앞서 있음: 후순위 묶음(9·11·12)을 미룬다. 속도를 늦추려고 의미 없는 일을 하지는 않는다", None))
    elif status == "완료":
        acts.append(("목표 98.5달러 달성: 추가 발주 중지, 콘솔 대조만 남음", None))
    else:
        acts.append(("정상: 계획대로 진행. 추가 발주 없음", None))
    return acts


def advice_line(c):
    st = c["status"]
    if st in ("지연", "위험"):
        return f"예비 작업 약 {c['gap'] * 1.2:.0f}달러어치 추가 발주(탐, credit_actions.md)"
    if st == "앞섬":
        return "후순위 묶음을 미룬다"
    if st == "완료":
        return "추가 발주 중지"
    return "계획대로 진행"


def console_summary(c, now):
    con = load_console(daily_dir())
    checks = sorted(con.get("checks", []), key=lambda x: x.get("date", ""))
    if not checks:
        return "콘솔 대조 필요: 기록 없음", None
    last = checks[-1]
    age = (now.date() - datetime.fromisoformat(last["date"]).date()).days
    cspent = con.get("baseline_usd", TOTAL) - float(last["remaining_usd"])
    try:
        cut = datetime.fromisoformat(last["recorded_at"]).astimezone(KST)
    except (KeyError, ValueError):
        cut = datetime.fromisoformat(last["date"]).replace(hour=23, minute=59, tzinfo=KST)
    ledger_to_date = sum(r["cost"] for r in c["rows"] if r["t"] <= cut)
    diff = ledger_to_date - cspent
    need = "콘솔 대조 필요" if age >= CONSOLE_STALE_DAYS else "대조 최근"
    return (f"{need}: 마지막 대조일 {last['date']}({age}일 전), 콘솔 소진 {cspent:.2f} 대 장부 {ledger_to_date:.2f} (장부-콘솔 {diff:+.2f}), 출처 {last['source']}", last)


def render(c, now):
    pct = c["spent"] / TOTAL * 100
    ncp_t, ncp_v = next_checkpoint(now)
    con_line, _ = console_summary(c, now)
    L = []
    L.append(f"# 크레딧 일일 소진 리포트 ({now:%Y-%m-%d %H:%M} KST)")
    L.append("")
    L.append(f"- 상태: **{c['status']}**  (누적 {c['spent']:.2f}달러 = {pct:.1f}%, 지금 최소 목표 {c['target']:.2f}달러, 차이 {c['spent'] - c['target']:+.2f})")
    L.append(f"- 오늘 사용: {c['today']:.2f}달러. 마감(10/27 21:00 KST)까지 {c['days_left']:.1f}일, 98.5달러를 채우려면 하루 {c['need_rate']:.2f}달러 필요(계획 평균 6.8, 목표 7.5)")
    L.append(f"- 다음 체크포인트: {ncp_t:%m/%d %H:%M} 최소 {ncp_v:.0f}달러")
    L.append(f"- 분모 {TOTAL}달러(프로모션 잔액, 10/13 콘솔). 장부는 래퍼 기준이라 콘솔과 오차가 있다")
    L.append(f"- {con_line}")
    if c["unpriced"]:
        L.append(f"- 가격 미확인 모델 호출 {c['unpriced']}건({c['unpriced_usd']:.2f}달러)은 래퍼가 최고 단가로 넣은 추정이라 실제보다 클 수 있다")
    L.append("")
    L.append("## 일별 x 모델별 사용(달러)")
    if not c["by_day"]:
        L.append("- 10/13 이후 장부 기록 없음")
    for day in sorted(c["by_day"]):
        parts = ", ".join(f"{m} {v:.3f}" for m, v in sorted(c["by_day"][day].items(), key=lambda x: -x[1]))
        L.append(f"- {day}: 합계 {sum(c['by_day'][day].values()):.3f} ({parts})")
    L.append("")
    L.append("## 묶음별")
    L.append("- 장부에 묶음 표시 열이 없어 **묶음 미상**으로 둔다(호출자 이름은 참고만).")
    tot = sum(c["by_who"].values())
    L.append(f"- 묶음 미상 합계 {tot:.3f}달러. 호출자별: " + (", ".join(f"{w} {v:.3f}" for w, v in sorted(c["by_who"].items(), key=lambda x: -x[1])) or "없음"))
    L.append("")
    L.append("## 권고 행동")
    for text, cmd in pick_actions(c["status"], c["gap"]):
        L.append(f"- {text}")
        if cmd:
            L.append(f"  - `{cmd}`")
    return "\n".join(L) + "\n"


def render_actions(c, now):
    L = [f"# 크레딧 다음 행동 목록 (갱신 {now:%Y-%m-%d %H:%M} KST)", "",
         f"상태 **{c['status']}**, 누적 {c['spent']:.2f}/{TOTAL}달러, 최소 목표 {c['target']:.2f}달러, 하루 필요 {c['need_rate']:.2f}달러. 근거: 계획서 1절 증액 규칙·3절 예비 작업. 이 파일은 점검 때마다 덮어쓴다.", ""]
    for text, cmd in pick_actions(c["status"], c["gap"]):
        L.append(f"- {text}")
        if cmd:
            L.append(f"  ```\n  {cmd}\n  ```")
    return "\n".join(L) + "\n"


def telegram_text(c, now):
    return "\n".join([
        f"[크레딧 {now:%m/%d}] 오늘 사용 {c['today']:.2f}달러",
        f"누적 소진 {c['spent']:.2f}/{TOTAL}달러 ({c['spent'] / TOTAL * 100:.1f}%)",
        f"목표 대비 {c['status']} (최소 목표 {c['target']:.1f}달러, 차이 {c['spent'] - c['target']:+.1f})",
        f"필요한 일일 속도 {c['need_rate']:.2f}달러/일 (마감 10/27 21시)",
        f"권고: {advice_line(c)}"])


def send_telegram(text):
    if os.environ.get("CREDIT_NO_TELEGRAM"):
        print("텔레그램 건너뜀(CREDIT_NO_TELEGRAM)")
        return True
    script = Path(__file__).resolve().parent / "tg_boss.py"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.run([sys.executable, str(script), "text", text, "--persona", "탐"], capture_output=True,
                       encoding="utf-8", errors="replace", timeout=120, creationflags=flags)
    print((p.stdout or "").strip() or (p.stderr or "").strip()[:200])
    return p.returncode == 0 and "ok" in (p.stdout or "")


def run(mode, now, force=False):
    d = daily_dir()
    d.mkdir(parents=True, exist_ok=True)
    init_console(d)
    c = compute(now)
    rep = render(c, now)
    (d / f"report_{now:%Y-%m-%d}.md").write_text(rep, encoding="utf-8")
    (d / "latest.md").write_text(rep, encoding="utf-8")
    (d / "credit_actions.md").write_text(render_actions(c, now), encoding="utf-8")
    state = {"checked": now.isoformat(), "status": c["status"], "spent": round(c["spent"], 4), "target": round(c["target"], 4),
             "gap": round(c["gap"], 4), "today": round(c["today"], 4), "need_rate": round(c["need_rate"], 4)}
    (d / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    sent_mark = d / f"telegram_sent_{now:%Y-%m-%d}.txt"
    want_tg = (mode == "daily") or (mode == "status" and now.hour >= 21)
    sent = None
    if want_tg and (force or not sent_mark.exists()):
        sent = send_telegram(telegram_text(c, now))
        if sent:
            sent_mark.write_text(now.isoformat(), encoding="utf-8")
    c["_paths"] = (d / f"report_{now:%Y-%m-%d}.md", d / "credit_actions.md")
    c["_tg"] = "sent" if sent else ("fail" if sent is False else ("dup" if want_tg else ""))
    return c, sent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["status", "daily", "record-console"])
    ap.add_argument("--now")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--remaining", type=float)
    ap.add_argument("--source", default="")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now).replace(tzinfo=KST) if a.now else datetime.now(KST)
    if a.mode == "record-console":
        if a.remaining is None or not a.source:
            sys.exit("--remaining 과 --source 필수")
        d = daily_dir()
        init_console(d)
        con = load_console(d)
        con["checks"].append({"date": now.date().isoformat(), "remaining_usd": a.remaining, "source": a.source,
                              "recorded_at": now.isoformat(timespec="seconds")})
        (d / "console_check.json").write_text(json.dumps(con, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"콘솔 대조 기록: {now.date()} 잔액 {a.remaining}")
        return 0
    c, sent = run(a.mode, now, a.force)
    bad = c["status"] in ("지연", "위험")
    if bad:
        # 감시 대장(watch.py cmd)이 첫 줄을 '지금 문제'로 띄운다
        print(f"크레딧 소진 {c['status']}: 누적 {c['spent']:.1f}달러, 최소 목표 {c['target']:.1f}달러보다 {c['gap']:.1f}달러 부족. 행동 {c['_paths'][1]}")
    print(f"리포트: {c['_paths'][0]}")
    print(f"행동 목록: {c['_paths'][1]}")
    print(f"상태: {c['status']} 누적 {c['spent']:.2f}달러 오늘 {c['today']:.2f}달러 하루 필요 {c['need_rate']:.2f}달러")
    tg = c["_tg"]
    if tg:
        print({"sent": "텔레그램 전송 성공", "fail": "텔레그램 전송 실패", "dup": "텔레그램: 오늘 이미 보냄"}[tg])
    return 1 if bad else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
