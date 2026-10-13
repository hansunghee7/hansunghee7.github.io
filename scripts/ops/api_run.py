# -*- coding: utf-8 -*-
"""Claude API 직접 호출 래퍼(2026-10-09 로컬탐). claude -p 는 호출마다 기본 안내문이 붙어 짧은 일에도 비싸서, 에이전트 틀 없이 Messages API를 직접 부른다.

credit_run.py 와 같은 관문을 쓴다: 키(ANTHROPIC_API_KEY_OPS, 값은 출력하지 않음), 하루 경보선(--daily-usd, 기본 100.0), 같은 장부(claude_api_usage.csv).
2026-10-13 사장님 승인("실험과 한도 빼고 다 승인, 최대한 사용, 1주일 사용 뒤 한도 계획"): 경보선을 넘어도 호출을 멈추지 않고 stderr와 경보 로그(api_run_alerts.log)에만 남긴다. 옛 정지 동작은 --hard-stop 으로만 켠다.
(상한을 막는 훅·설정은 저장소에서 찾지 못했다. 상한은 이 CLI 인자뿐이었다.)
비용은 응답의 usage 토큰에 가격표를 곱해 계산한다(가격은 2026-10-07 Anthropic 발표 기준, PRICES 에서 고친다. 실제 청구와 대조 전에는 추정치).
종료 코드: 0 성공 / 2 호출 실패 / 3 하루 상한 초과(--hard-stop 일 때만) / 4 키 없음
사용: python api_run.py --who 탐 --model claude-haiku-5-5 --prompt-file q.md [--system "한 줄 지시"] [--max-tokens 1024] [--timeout 600] [--out a.md] [--dry] [--hard-stop]
환경: ANTHROPIC_API_BASE(기본 https://api.anthropic.com, 시험용), CREDIT_LEDGER
"""
import argparse, csv, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

# 백만 토큰당 달러: (입력, 출력, 캐시 읽기, 캐시 쓰기). 10만 토큰 이하 요청 기준.
# [확인 필요] haiku-5-5 단가: 이 래퍼($0.10/$0.50)와 docs/모델_라우팅.md(하이쿠 4.5: $1/$5)가 10배 다르다. 콘솔 청구와 대조 전까지 값은 그대로 둔다.
# 오퍼스·페이블 단가는 docs/모델_라우팅.md [문서 기준 2026-09-08] 의 오퍼스 5 $5/$25, 페이블 5.1 $10/$50 을 쓴 추정이며 콘솔 대조 전이다.
# 캐시 읽기는 입력의 0.1배, 캐시 쓰기는 1.25배로 같은 비율을 적용한 추정이다.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-opus-5-5": (5.00, 25.00, 0.50, 6.25),
    "claude-fable-5": (10.00, 50.00, 1.00, 12.50),
}
# 모르는 모델 이름이 오면 0원으로 적지 않고 가장 비싼 단가로 보수적으로 기록하고 장부에 '가격 미확인' 을 표시한다.
FALLBACK_PRICE = max(PRICES.values(), key=lambda p: p[1])
UNPRICED_MARK = "가격미확인"


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
                if row.get("ts", "").startswith(day) and str(row.get("status")).startswith("ok"):
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


def alert(path, msg):
    try:
        with open(path.parent / "api_run_alerts.log", "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg))
    except OSError:
        pass


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
        p = FALLBACK_PRICE
    i, o, cr, cw = p
    return (usage.get("input_tokens", 0) * i + usage.get("output_tokens", 0) * o
            + usage.get("cache_read_input_tokens", 0) * cr + usage.get("cache_creation_input_tokens", 0) * cw) / 1e6


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # 한글 경보 문구가 cp949 콘솔에서 깨지거나 죽지 않게
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--system")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--out")
    ap.add_argument("--daily-usd", type=float, default=100.0, help="하루 경보선(기본 100). 넘어도 --hard-stop 이 없으면 멈추지 않는다")
    ap.add_argument("--hard-stop", action="store_true", help="경보선을 넘으면 호출하지 않고 종료 코드 3")
    ap.add_argument("--timeout", type=int, default=600, help="응답 대기 초(기본 600, 긴 출력용)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    led = ledger_path()
    used = today_total(led)
    if used >= a.daily_usd:
        msg = "DAILY-ALERT used=%.4f line=%.2f who=%s model=%s" % (used, a.daily_usd, a.who, a.model)
        alert(led, msg)
        if a.hard_stop:
            print(msg + ": not called", file=sys.stderr)
            return 3
        print(msg + ": 경보만, 계속 호출", file=sys.stderr)
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
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
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
    unpriced = a.model not in PRICES
    if unpriced:
        alert(led, "UNPRICED-MODEL %s: 최고 단가로 기록" % a.model)
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    append_ledger(led, [ts, a.who, a.model + "@api", "%.6f" % (cost or 0), u.get("input_tokens", 0), u.get("output_tokens", 0), "ok" + (":" + UNPRICED_MARK if unpriced else "")])
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    print("OK cost=%s in=%s out=%s today=%.4f cap=%.2f%s" % ("%.6f" % cost, u.get("input_tokens"), u.get("output_tokens"), used + (cost or 0), a.daily_usd, " (가격표에 없는 모델, 최고 단가로 기록)" if unpriced else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
