# -*- coding: utf-8 -*-
"""Claude API 직접 호출 래퍼(2026-10-09 로컬탐). claude -p 는 호출마다 기본 안내문이 붙어 짧은 일에도 비싸서, 에이전트 틀 없이 Messages API를 직접 부른다.

credit_run.py 와 같은 관문을 쓴다: 키(ANTHROPIC_API_KEY_OPS, 값은 출력하지 않음), 하루 상한(--daily-usd, 기본 5.0), 같은 장부(claude_api_usage.csv).
비용은 응답의 usage 토큰에 가격표를 곱해 계산한다(가격은 2026-10-07 Anthropic 발표 기준, PRICES 에서 고친다. 실제 청구와 대조 전에는 추정치).
종료 코드: 0 성공 / 2 호출 실패 / 3 하루 상한 초과 / 4 키 없음
사용: python api_run.py --who 탐 --model claude-haiku-5-5 --prompt-file q.md [--system "한 줄 지시"] [--max-tokens 1024] [--out a.md] [--dry]
환경: ANTHROPIC_API_BASE(기본 https://api.anthropic.com, 시험용), CREDIT_LEDGER
"""
import argparse, csv, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

# 백만 토큰당 달러: (입력, 출력, 캐시 읽기, 캐시 쓰기). 10만 토큰 이하 요청 기준.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
}


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


def cost_of(model, usage):
    p = PRICES.get(model)
    if not p:
        return None
    i, o, cr, cw = p
    return (usage.get("input_tokens", 0) * i + usage.get("output_tokens", 0) * o
            + usage.get("cache_read_input_tokens", 0) * cr + usage.get("cache_creation_input_tokens", 0) * cw) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--system")
    ap.add_argument("--max-tokens", type=int, default=1024)
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
    body = {"model": a.model, "max_tokens": a.max_tokens, "messages": [{"role": "user", "content": prompt}]}
    if a.system:
        body["system"] = a.system
    base = os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com").rstrip("/")
    req = urllib.request.Request(base + "/v1/messages", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        append_ledger(led, [ts, a.who, a.model + "@api", 0, 0, 0, "fail:http%d" % e.code])
        print("CALL-FAIL http", e.code, e.read()[:200].decode("utf-8", "replace"), file=sys.stderr)
        return 2
    except Exception as e:
        append_ledger(led, [ts, a.who, a.model + "@api", 0, 0, 0, "fail:" + type(e).__name__])
        print("CALL-FAIL", type(e).__name__, file=sys.stderr)
        return 2
    u = d.get("usage") or {}
    cost = cost_of(a.model, u)
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    append_ledger(led, [ts, a.who, a.model + "@api", "%.6f" % (cost or 0), u.get("input_tokens", 0), u.get("output_tokens", 0), "ok"])
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    print("OK cost=%s in=%s out=%s today=%.4f cap=%.2f%s" % ("%.6f" % cost if cost is not None else "unknown-model", u.get("input_tokens"), u.get("output_tokens"), used + (cost or 0), a.daily_usd, "" if cost is not None else " (가격표에 없는 모델)"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
