#!/usr/bin/env python3
"""빠른 작업용 제미나이 호출기: 키 2개 순환, 하루 소진 카운터, 실패 시 다른 키로 넘김.

- 다이얼로그(Worker)용 키는 절대 쓰지 않는다: 대장에서 role=dialog 인 지문은
  로딩 단계에서 제외하고, 호출 직전에도 한 번 더 검사한다(코드로 강제, 대장 registry/gemini-keys.json 기준).
- 키 값은 화면·로그·JSON에 절대 쓰지 않는다. 지문(fp)만 쓴다.
- 카운터: C:\\work\\_ops\\gemini_counters.json (키 지문 x 태평양시 날짜). 무료 한도는 태평양시 자정에 초기화.

사용:
  python scripts/ops/gemini_fast.py --status
  python scripts/ops/gemini_fast.py "질문"            # 순환 호출, 답과 지연(초), 사용한 키 지문 출력
  python scripts/ops/gemini_fast.py --each "질문"     # 키별로 1회씩 호출해 지연 비교
"""
import argparse, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 키 대장(비공개 저장소): 값은 없고 지문·용도·읽는 파일/변수 이름만 있다. role=dialog 키는 절대 쓰지 않는다.
REGISTRY = Path("C:/work/simplifier-cxo-db/registry/gemini-keys.json")
DEFAULT_MODEL = "gemini-flash-lite-latest"  # 다이얼로그 Worker와 같은 모델(공개 질문 지연 비교용)
COUNTER = Path(r"C:\work\_ops\gemini_counters.json")


def fp(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:6]


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["keys"]


def dialog_fps():
    return {k["fp"] for k in registry() if k.get("role") == "dialog"}


def load_keys():
    """대장에서 role=fast 인 키만, 대장의 (파일, 변수)로 값을 읽어 지문이 대장과 같을 때만 쓴다."""
    keys = []
    for e in registry():
        if e.get("role") != "fast":
            continue
        try:
            text = open(e["source"]["file"], encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        m = re.search(rf"^\s*(?:set\s+)?{e['source']['var']}\s*=\s*['\"]?([^\s'\"]+)", text, re.M | re.I)
        if not m or fp(m.group(1)) != e["fp"] or e["fp"] in dialog_fps():
            continue  # 지문 불일치(키가 바뀜)나 다이얼로그 키는 로딩하지 않는다
        keys.append({"name": e["id"], "fp": e["fp"], "value": m.group(1)})
    return keys


def today_pt() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%d")  # 태평양 표준시 근사


def read_counter():
    try:
        return json.loads(COUNTER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def bump(fp_, ok, secs):
    c = read_counter()
    day = c.setdefault(today_pt(), {})
    k = day.setdefault(fp_, {"calls": 0, "ok": 0, "fail": 0, "secs": 0.0})
    k["calls"] += 1
    k["ok" if ok else "fail"] += 1
    k["secs"] = round(k["secs"] + secs, 2)
    for old in sorted(c)[:-14]:
        del c[old]
    COUNTER.parent.mkdir(parents=True, exist_ok=True)
    COUNTER.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def call(key, prompt, model):
    assert key["fp"] not in dialog_fps(), "다이얼로그 키는 사용 금지"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": key["value"]})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        secs = time.time() - t
        bump(key["fp"], True, secs)
        return {"ok": True, "text": text, "secs": round(secs, 2), "fp": key["fp"]}
    except urllib.error.HTTPError as e:
        secs = time.time() - t
        bump(key["fp"], False, secs)
        return {"ok": False, "status": e.code, "secs": round(secs, 2), "fp": key["fp"]}
    except Exception as e:  # 네트워크·파싱 오류
        secs = time.time() - t
        bump(key["fp"], False, secs)
        return {"ok": False, "status": type(e).__name__, "secs": round(secs, 2), "fp": key["fp"]}


def ask(prompt, model=DEFAULT_MODEL):
    """오늘 호출이 적은 키부터 시도하고, 실패(429·5xx 등)하면 다음 키로 넘긴다."""
    day = read_counter().get(today_pt(), {})
    keys = sorted(load_keys(), key=lambda k: day.get(k["fp"], {}).get("calls", 0))
    if not keys:
        return {"ok": False, "status": "사용 가능한 키 없음"}
    last = None
    for k in keys:
        last = call(k, prompt, model)
        if last["ok"]:
            return last
    return last


def poller_usage_today():
    """헤르메스 폴러(탐 키의 여분 사용, 사장님 2026-09-22)의 오늘 gemini 실행 건수·토큰. usage_audit.jsonl에서 읽는다."""
    path = Path("C:/Users/PC/AppData/Local/hermes/cron/usage_audit.jsonl")
    n = tok = fail = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "폴러 사용량: 감사 기록 없음"
    for line in lines:
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("ts", "")[:10] == today and str(j.get("model", "")).startswith("gemini"):
            n += 1
            tok += j.get("total_tokens") or 0
            fail += 1 if j.get("error") else 0
    return f"폴러(헤르메스) 오늘 UTC gemini 실행 {n}건, 토큰 {tok:,}, 오류 {fail}건"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--each", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    if a.status:
        print("사용 가능 키:", [(k["name"], k["fp"]) for k in load_keys()], "/ 제외(다이얼로그 추정):", sorted(dialog_fps()))
        print(json.dumps(read_counter().get(today_pt(), {}), ensure_ascii=False))
        print(poller_usage_today())
        return
    if not a.prompt:
        ap.error("질문이 필요합니다")
    if a.each:
        for k in load_keys():
            r = call(k, a.prompt, a.model)
            print(k["name"], k["fp"], "OK" if r["ok"] else f"실패 {r['status']}", f"{r['secs']}초", (r.get("text") or "")[:60].replace("\n", " "))
        return
    r = ask(a.prompt, a.model)
    print("OK" if r["ok"] else f"실패 {r.get('status')}", f"{r.get('secs')}초", "키", r.get("fp"))
    if r["ok"]:
        print(r["text"])


if __name__ == "__main__":
    sys.exit(main())
