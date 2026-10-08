# -*- coding: utf-8 -*-
"""Claude API 크레딧 실행 래퍼(2026-10-09 로컬탐). 에이전트는 claude -p 를 직접 부르지 않고 이 래퍼를 부른다.

왜: 프로모션 크레딧($100, 10/28 만료)을 하루 예산 안에서 쓰고, 모든 호출을 장부에 남기려고. 문서 규칙이 아니라 코드 관문이다(CLAUDE#4e7b).
키: 프로세스 환경변수 ANTHROPIC_API_KEY_OPS, 없으면 헤르메스 환경 파일(%LOCALAPPDATA%/hermes/.env)의 같은 이름 줄.
    값은 어디에도 출력하지 않고, 자식 프로세스 환경에만 ANTHROPIC_API_KEY 로 넣는다. 금고가 넣어 준다: pass.py envput <키 이름> ANTHROPIC_API_KEY_OPS
관문: 오늘(UTC) 장부 합계가 --daily-usd(기본 5.0) 이상이면 호출하지 않고 종료 코드 3.
종료 코드: 0 성공 / 2 호출 실패 / 3 하루 상한 초과 / 4 키 없음
사용: python credit_run.py --who 탐 --model claude-haiku-5-5 --prompt-file q.md [--out a.md] [--daily-usd 5] [--dry]
환경: CLAUDE_BIN(기본 claude), CREDIT_LEDGER(기본 C:/work/_ops/claude_api_usage.csv, 폴더가 없으면 현재 폴더)
"""
import argparse, csv, json, os, subprocess, sys, tempfile, time
from pathlib import Path


def ledger_path():
    p = os.environ.get("CREDIT_LEDGER")
    if p:
        return Path(p)
    base = Path("C:/work/_ops")
    return (base if base.is_dir() else Path(".")) / "claude_api_usage.csv"


def today_total(path):
    day = time.strftime("%Y-%m-%d", time.gmtime())
    total = 0.0
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("ts", "").startswith(day) and row.get("status") == "ok":
                    try:
                        total += float(row.get("cost_usd") or 0)
                    except ValueError:
                        pass
    return total


def append_ledger(path, row):
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "who", "model", "cost_usd", "in_tok", "out_tok", "status"])
        w.writerow(row)


def find_key():
    k = os.environ.get("ANTHROPIC_API_KEY_OPS")
    if k:
        return k.strip()
    envf = Path(os.environ.get("LOCALAPPDATA", ".")) / "hermes" / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("ANTHROPIC_API_KEY_OPS="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--out")
    ap.add_argument("--daily-usd", type=float, default=5.0)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    led = ledger_path()
    used = today_total(led)
    if used >= a.daily_usd:
        print("DAILY-CAP used=%.4f cap=%.2f: not called" % (used, a.daily_usd), file=sys.stderr)
        return 3
    key = find_key()
    if not key:
        print("NO-KEY: put ANTHROPIC_API_KEY_OPS via pass.py envput", file=sys.stderr)
        return 4
    prompt = Path(a.prompt_file).read_text(encoding="utf-8")
    if a.dry:
        print("DRY ok used=%.4f cap=%.2f model=%s chars=%d" % (used, a.daily_usd, a.model, len(prompt)))
        return 0
    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = key
    env.pop("ANTHROPIC_API_KEY_OPS", None)
    cmd = [os.environ.get("CLAUDE_BIN", "claude"), "-p", prompt, "--model", a.model, "--output-format", "json"]
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory() as cwd:  # project hooks must not run
        try:
            r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300, creationflags=flags)
        except Exception as e:
            append_ledger(led, [ts, a.who, a.model, 0, 0, 0, "fail:" + type(e).__name__])
            print("CALL-FAIL", type(e).__name__, file=sys.stderr)
            return 2
    try:
        d = json.loads(r.stdout)
    except Exception:
        append_ledger(led, [ts, a.who, a.model, 0, 0, 0, "fail:badjson"])
        print("CALL-FAIL bad output rc=%s" % r.returncode, file=sys.stderr)
        return 2
    u = d.get("usage") or {}
    cost = float(d.get("total_cost_usd") or 0)
    append_ledger(led, [ts, a.who, a.model, cost, u.get("input_tokens", 0), u.get("output_tokens", 0), "ok" if not d.get("is_error") else "fail:api"])
    text = d.get("result", "")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    print("OK cost=%.4f today=%.4f cap=%.2f" % (cost, used + cost, a.daily_usd), file=sys.stderr)
    return 0 if not d.get("is_error") else 2


if __name__ == "__main__":
    sys.exit(main())
