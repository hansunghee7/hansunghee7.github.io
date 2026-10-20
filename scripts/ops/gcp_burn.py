#!/usr/bin/env python3
"""GCP 크레딧 시한부 고성능 과제 큐(2026-10-20 탐, 사장님 승인 공정자산 후보 ①).

왜: GCP 크레딧(회사 풀 12/10 만료)이 하루 필요 소진량보다 훨씬 느리게 쓰이고 있다. 에이전트들이 미뤄 둔
    읽기·분석형 과제를 큐에 쌓아 두면 이 스크립트가 매일 Vertex(크레딧이 덮는 경로)로 소화한다.
    AI Studio(Gemini API 키) 경로는 크레딧이 안 덮으므로 쓰지 않는다: ask_vertex.py를 VERTEX_NO_FAILOVER로 불러
    상한·장애 때 무료 키·라우터로 새는 길을 막는다.

흐름: queue.jsonl 과제 → (이미 성공·3회 실패면 건너뜀) → 하루 상한 확인 → ask_vertex.py(기존 래퍼, 키 값 없음) → ledger.jsonl 한 줄
하루 상한(달러) = (남은 GCP 크레딧 원 − 예약분) ÷ 환율 ÷ 만료(12/10)까지 남은 일수 × 0.8
    남은 크레딧은 gcp_credit_report.py와 같은 방식(vertex_budget.json 기준 잔액 − gcp_usage 캐시의 이후 실사용)으로 추정한다.
    못 읽으면 보수적 기본값 5달러/일, 이유는 ledger의 cap 줄에 남긴다.
재시도: 같은 과제는 최대 3번 시도(실패 3회면 포기, ledger로 센다). ask_vertex 자체 상한(종료 코드 3)은 시도로 세지 않고 그날 멈춘다.
비밀값: 조립한 프롬프트에 키·토큰 모양 문자열이 보이면 보내지 않는다(값은 출력하지 않음).

과제 한 줄(JSON): {"id": "...", "title": "...", "prompt": "...", "context_files": ["경로 또는 glob"],
                   "model": "gemini-3.6-flash", "est_usd": 0.1, "max_context_chars": 60000, "search": false}
사용: python scripts/ops/gcp_burn.py [--dry] [--max-usd 1.0] [--only ID] [--queue ...] [--ledger ...] [--results ...]
종료 코드: 0 정상(할 일 없음 포함) / 2 과제 실패 있음 / 3 상한 도달로 멈춤
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path(os.environ.get("GCP_BURN_DIR", "C:/work/_ops/gcp_burn"))
OPS = Path("C:/work/_ops")
EXPIRY = date.fromisoformat(os.environ.get("GCP_BURN_EXPIRY", "2026-12-10"))  # 회사 풀 만료(개인 풀 12/23보다 이르다)
USD_KRW = float(os.environ.get("GCP_BURN_USD_KRW", "1400"))  # vertex_budget.json 예약 메모와 같은 가정
SAFETY = 0.8
DEFAULT_CAP_USD = 5.0
MAX_ATTEMPTS = 3
DEFAULT_MODEL = "gemini-3.6-flash"
SECRET_PAT = re.compile(
    r"AIza[0-9A-Za-z_\-]{30,}|sk-[A-Za-z0-9_\-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9\-]{10,}|pypi-[A-Za-z0-9_\-]{40,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|\"private_key\"\s*:|ya29\.[0-9A-Za-z_\-]{20,}|\b\d{9,10}:AA[0-9A-Za-z_\-]{30,}")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def remaining_krw():
    """남은 크레딧(원) 추정. gcp_credit_report.py와 같은 계산에 예약분(핏 영상 등)을 뺀다."""
    sys.path.insert(0, str(HERE))
    import gcp_credit_report as g
    b = json.loads((OPS / "vertex_budget.json").read_text(encoding="utf-8"))
    used = 0.0
    for _, f in g.PROJECTS:
        u, _per = g.used_since(f, b["as_of"])
        if u is None:
            raise RuntimeError(f"실사용 캐시 {f} 못 읽음")
        used += u
    reserved = sum(float(r.get("krw", 0)) for r in b.get("reserved", []))
    return float(b["balance"]) - used - reserved


def daily_cap(today=None, remain_fn=None):
    """(하루 상한 달러, 설명) 돌려준다. 실패하면 기본값 5달러와 이유."""
    today = today or date.today()
    days = max((EXPIRY - today).days, 1)
    try:
        remain = (remain_fn or remaining_krw)()
        if remain <= 0:
            return 0.0, f"남은 크레딧 추정 ₩{remain:,.0f}(0 이하)라 오늘 상한 0"
        cap = remain / USD_KRW / days * SAFETY
        return round(cap, 4), f"(남은 ₩{remain:,.0f} ÷ {USD_KRW:.0f}원/달러 ÷ {days}일) × {SAFETY} = ${cap:.2f}"
    except Exception as e:  # noqa: BLE001
        return DEFAULT_CAP_USD, f"잔액 못 읽음({type(e).__name__}: {str(e)[:80]}), 보수적 기본값 ${DEFAULT_CAP_USD:.2f}"


def read_jsonl(p):
    if not Path(p).exists():
        return []
    out = []
    for ln in Path(p).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def append(p, row):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with Path(p).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def spent_today(ledger, today=None):
    d = (today or date.today()).isoformat()
    return sum(float(r.get("est_usd") or 0) for r in ledger if r.get("kind") == "call" and str(r.get("time", "")).startswith(d))


def task_state(ledger, tid):
    """(성공 여부, 실패 횟수)."""
    calls = [r for r in ledger if r.get("kind") == "call" and r.get("task") == tid]
    return any(r.get("ok") for r in calls), sum(1 for r in calls if not r.get("ok"))


def build_prompt(task):
    parts = [task["prompt"].strip()]
    limit = int(task.get("max_context_chars", 60000))
    used = 0
    for pat in task.get("context_files", []):
        for fp in sorted(glob.glob(pat)) or [pat]:
            p = Path(fp)
            if not p.is_file():
                parts.append(f"\n[자료 없음: {p.name}]")
                continue
            txt = p.read_text(encoding="utf-8", errors="replace")
            room = limit - used
            if room <= 0:
                parts.append(f"\n[분량 상한으로 생략: {p.name}]")
                continue
            if len(txt) > room:
                txt = txt[:room] + "\n[...분량 상한으로 잘림]"
            used += len(txt)
            parts.append(f"\n\n=== 자료: {p.name} ===\n{txt}")
    return "".join(parts)


def run_ask(prompt_path, out_path, model, search):
    """기존 래퍼 ask_vertex.py 호출. 무료 키·라우터로 새지 않게 막는다(AI Studio는 크레딧 제외)."""
    env = dict(os.environ, VERTEX_NO_FAILOVER="1", VERTEX_NO_ROUTER="1", PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, str(HERE / "ask_vertex.py"), str(prompt_path), str(out_path), "--who", "탐-burn", "--model", model]
    if search:
        cmd.append("--search")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, r.stderr or ""


def parse_stderr(err):
    m = re.search(r"토큰 입력 (\d+)·출력 (\d+)", err)
    k = re.search(r"추정 약 ₩([\d,\.]+)", err)
    pj = re.search(r"청구 프로젝트: (\S+)", err)
    return {"in_tok": int(m.group(1)) if m else 0, "out_tok": int(m.group(2)) if m else 0,
            "est_krw": float(k.group(1).replace(",", "")) if k else 0.0, "project": pj.group(1) if pj else ""}


def main(argv=None, ask=None, remain_fn=None, today=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--max-usd", type=float, default=None, help="이번 실행만의 추가 상한(달러)")
    ap.add_argument("--only", default=None, help="이 id 과제만")
    ap.add_argument("--queue", default=str(BASE / "queue.jsonl"))
    ap.add_argument("--ledger", default=str(BASE / "ledger.jsonl"))
    ap.add_argument("--results", default=str(BASE / "results"))
    a = ap.parse_args(argv)
    ask = ask or run_ask
    today = today or date.today()
    ledger = read_jsonl(a.ledger)
    cap, why = daily_cap(today, remain_fn)
    spent = spent_today(ledger, today)
    run_spent = 0.0
    print(f"하루 상한 ${cap:.2f} [{why}], 오늘 이미 ${spent:.4f}" + (f", 이번 실행 상한 ${a.max_usd:.2f}" if a.max_usd is not None else ""))
    if not a.dry:
        append(a.ledger, {"kind": "cap", "time": now(), "cap_usd": cap, "why": why, "spent_today_usd": round(spent, 4)})
    tasks = [t for t in read_jsonl(a.queue) if not a.only or t.get("id") == a.only]
    failed, stopped = False, False
    for t in tasks:
        tid, model = t.get("id"), t.get("model", DEFAULT_MODEL)
        done, fails = task_state(ledger, tid)
        if done:
            print(f"- {tid}: 이미 성공, 건너뜀")
            continue
        if fails >= MAX_ATTEMPTS:
            print(f"- {tid}: 실패 {fails}회로 포기 상태, 건너뜀")
            continue
        est = float(t.get("est_usd") or 0.05)
        if spent + est > cap or (a.max_usd is not None and run_spent + est > a.max_usd):
            print(f"- {tid}: 상한 도달(오늘 ${spent:.4f} + 예상 ${est:.2f}), 멈춤")
            if not a.dry:
                append(a.ledger, {"kind": "stop", "time": now(), "task": tid, "reason": "상한", "spent_today_usd": round(spent, 4), "cap_usd": cap})
            stopped = True
            break
        prompt = build_prompt(t)
        if SECRET_PAT.search(prompt):
            print(f"- {tid}: 비밀값 모양 문자열 발견, 보내지 않음(값은 출력 안 함)")
            if not a.dry:
                append(a.ledger, {"kind": "skip", "time": now(), "task": tid, "reason": "비밀값 의심"})
            continue
        if a.dry:
            print(f"- {tid}: [dry] {t.get('title')} / {model} / 프롬프트 {len(prompt):,}자 / 예상 ${est:.2f}")
            spent += est
            run_spent += est
            continue
        res_dir = Path(a.results)
        res_dir.mkdir(parents=True, exist_ok=True)
        pfile = res_dir / f"{tid}_prompt.md"
        pfile.write_text(prompt, encoding="utf-8")
        while fails < MAX_ATTEMPTS:
            out = res_dir / f"{tid}_{datetime.now():%Y%m%d_%H%M%S}.md"
            rc, err = ask(pfile, out, model, bool(t.get("search")))
            info = parse_stderr(err)
            usd = info["est_krw"] / USD_KRW
            if rc == 3:
                print(f"- {tid}: ask_vertex 자체 상한(종료 3), 오늘 멈춤")
                append(a.ledger, {"kind": "stop", "time": now(), "task": tid, "reason": "ask_vertex 상한(종료 3)"})
                stopped = True
                break
            ok = rc == 0 and out.exists() and not out.read_text(encoding="utf-8", errors="replace").startswith("[호출 실패")
            row = {"kind": "call", "time": now(), "task": tid, "title": t.get("title"), "model": model, **info,
                   "est_usd": round(usd, 5), "ok": ok, "rc": rc, "attempt": fails + 1,
                   "result": str(out) if ok else "", "err": "" if ok else err.strip().splitlines()[-1][:200] if err.strip() else f"rc={rc}"}
            append(a.ledger, row)
            ledger.append(row)
            spent += usd
            run_spent += usd
            print(f"- {tid}: {'성공' if ok else '실패'} 시도 {fails + 1} / 토큰 {info['in_tok']}+{info['out_tok']} / ${usd:.4f} / {row['result'] or row['err']}")
            if ok:
                break
            fails += 1
        else:
            failed = True
        if stopped:
            break
    print(f"끝: 오늘 누적 ${spent:.4f} / 상한 ${cap:.2f}")
    return 3 if stopped else (2 if failed else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
