#!/usr/bin/env python3
"""제미나이 공용 라우터(2026-10-11, 대장 N151·N160, 목표 G1).

왜: 호출부마다 무료 키/Vertex 순서를 따로 구현해서 첫 호출부터 429가 나고 기록도 흩어졌다.
    정본 정책 docs/제미나이_키_정책.md 의 순서를 한 곳에서 지킨다.
순서: ① 무료 AI Studio 키 -> ② 회사 Vertex(simplifier-vertex-credit) -> ③ 개인 Vertex.
    429·한도·차단(401/402/403)·과부하(5xx)·인증 실패는 다음 단계로 낙하하고 quota.py 대장에 막힘을 기록한다.
금액 관문: ask_vertex.py 의 DAY_KRW(일)·TOTAL_KRW(누적)를 import해 그대로 쓴다. 넘으면 Vertex 단계는 거부한다(무료 단계는 영향 없음).
재사용: 키 읽기=gemini_fast.load_keys(대장 role=fast 키)+환경 변수 이름(GOOGLE_API_KEY, GEMINI_API_KEY), Vertex 토큰·단가·기록=ask_vertex.
기록: C:/work/_ops/gemini_route_log.jsonl (who·route·status·ms·바이트 수만. 질문·답·키 값 없음).
값 규칙: 키·토큰은 메모리에서만 쓰고 반환값·로그·예외 메시지에 넣지 않는다(키 모양 문자열은 출력 직전 마스킹).

사용(코드): from gemini_route import call; r = call("질문", search=True, who="핏"); r["text"], r["route"], r["status"]
사용(CLI):  python scripts/ops/gemini_route.py --who 핏 --search "질문"
종료 코드: 0 성공 / 2 모든 단계 호출 실패 / 3 Vertex 일·누적 금액 상한 때문에 거부 / 4 쓸 수 있는 인증(키·토큰)이 하나도 없음
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROUTE_LOG = Path("C:/work/_ops/gemini_route_log.jsonl")
FREE_ENV_NAMES = ("GOOGLE_API_KEY", "GEMINI_API_KEY")  # pass.py envput 으로 이미 들어가 있는 환경 변수 이름만 읽는다
FALL_CODES = (401, 402, 403, 429, 500, 502, 503, 504)  # 이 코드면 다음 단계로 낙하
EXIT = {"ok": 0, "failed": 2, "capped": 3, "noauth": 4}
KEY_LIKE = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|ya29\.[0-9A-Za-z_\-\.]{20,}|Bearer\s+[0-9A-Za-z_\-\.]{20,}|sk-[0-9A-Za-z_\-]{20,}")


def mask(s):
    return KEY_LIKE.sub("[키모양값 가림]", str(s))


# ---- 바깥 세계와 닿는 얇은 함수들(시험에서 가짜로 바꾼다) ----
def _http_post(url, headers, body, timeout):
    """(상태코드, JSON 또는 None). 네트워크 오류는 코드 0."""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:  # noqa: BLE001  네트워크·파싱 오류. 내용은 키가 섞일 수 있어 버린다
        return 0, None


def _free_keys():
    """[(이름, 값)] 환경 변수 먼저, 그다음 키 대장의 일반 키(오늘 호출이 적은 순). 값은 반환 후 바깥으로 나가지 않는다."""
    out, seen = [], set()
    for n in FREE_ENV_NAMES:
        v = os.environ.get(n)
        if v and v not in seen:
            seen.add(v)
            out.append((n, v))
    try:
        import gemini_fast as g
        day = g.read_counter().get(g.today_pt(), {})
        for k in sorted(g.load_keys(), key=lambda k: day.get(k["fp"], {}).get("calls", 0)):
            if k["value"] not in seen:
                seen.add(k["value"])
                out.append((k["fp"], k["value"]))
    except Exception:  # noqa: BLE001  대장이 없으면 환경 변수만
        pass
    return out


def _token(account):
    import ask_vertex as av
    return av.token(account)


def _day_krw():
    """오늘 사용 추정 금액: 호출 기록과 프로젝트 전체 실사용 중 큰 쪽(ask_vertex 와 같은 규칙)."""
    import ask_vertex as av
    krw = av.today_use()[1]
    try:
        import gcp_usage
        krw = max(krw, gcp_usage.today_krw())
    except Exception:  # noqa: BLE001
        pass
    return krw


def _quota_hit(pool, msg):
    try:
        import io
        import contextlib
        import quota
        with contextlib.redirect_stdout(io.StringIO()):
            quota.main(["hit", pool, msg])
    except Exception:  # noqa: BLE001  기록 실패가 호출을 막지 않는다
        pass


def _quota_blocked(pool):
    try:
        import quota
        return quota.blocked_until(quota.load_state(), pool, datetime.now()) is not None
    except Exception:  # noqa: BLE001
        return False


# ---- 본체 ----
def _body(prompt, search):
    b = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if search:
        b["tools"] = [{"googleSearch": {}}]
    return b


def _parse(j):
    c = ((j or {}).get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []))
    g = c.get("groundingMetadata") or {}
    src = [{"title": ch.get("web", {}).get("title"), "uri": ch.get("web", {}).get("uri")} for ch in g.get("groundingChunks", []) if ch.get("web")]
    return text, src, (j or {}).get("usageMetadata", {}), len(g.get("webSearchQueries", []))


def _log(who, route, status, ms, nbytes):
    try:
        ROUTE_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {"time": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "who": who, "route": route, "status": status, "ms": ms, "bytes": nbytes}
        with ROUTE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _vertex_usage_row(who, model, search, tin, tout, sq, est, sec, rc):
    import ask_vertex as av
    av.LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not av.LOG.exists()
    with av.LOG.open("a", encoding="utf-8", newline="") as f:
        if new:
            f.write(av.HEAD + "\n")
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S},{who},{model},{int(search)},{tin},{tout},{sq},{est:.2f},{sec},{rc}\n")


def call(prompt, model="gemini-3.6-flash", search=False, who="unknown", timeout=300):
    """반환: dict(text, route, status, cost_note, sources, exit_code). route=free|vertex-company|vertex-personal|none."""
    timeout = int(os.environ.get("VERTEX_TIMEOUT") or timeout)
    attempts = []  # (route, status 문자열)
    capped = False

    def done(text, route, status, cost, src, t0, code):
        _log(who, route, status, int((time.time() - t0) * 1000), len(text.encode("utf-8")))
        return {"text": text, "route": route, "status": status, "cost_note": cost, "sources": src, "exit_code": code, "tried": attempts}

    t_all = time.time()
    # ① 무료 키
    keys = _free_keys()
    fpool = "제미나이-무료" + ("-검색" if search else "")  # 검색 연동은 무료 키에서 따로 막혀 있어(10/11 진단) 검색 429가 일반 호출까지 막지 않게 풀을 나눈다
    if not _quota_blocked(fpool):
        for name, val in keys:
            t0 = time.time()
            code, j = _http_post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 {"x-goog-api-key": val}, _body(prompt, search), timeout)
            if code == 200 and j:
                text, src, _u, _q = _parse(j)
                return done(text, "free", "ok", "무료 키(비용 0)", src, t0, 0)
            attempts.append(("free", f"HTTP{code}"))
            _log(who, "free", f"HTTP{code}", int((time.time() - t0) * 1000), 0)
            if code == 429:  # 429는 분당/일 어느 쪽인지 모르므로 짧게(1분)만 막고 다음 호출에서 다시 본다
                _quota_hit(fpool, f"who={who} HTTP429 Resets in 1m")
            if code not in FALL_CODES and code != 0:
                break  # 400 등 질문 자체 문제는 키를 바꿔도 소용없음
    else:
        attempts.append(("free", "skipped_blocked"))
    if not keys:
        attempts.append(("free", "no_key"))

    # ②·③ Vertex
    import ask_vertex as av
    stages = [("vertex-company", av.COMPANY_PROJECT, av.COMPANY_ACCOUNT), ("vertex-personal", av.PROJECT, av.ACCOUNT)]
    cap_msg = ""
    try:
        krw = _day_krw()
        total = av.total_since()
    except Exception:  # noqa: BLE001
        krw, total = 0.0, 0.0
    if krw >= av.DAY_KRW:
        capped, cap_msg = True, f"일 상한 초과(오늘 약 ₩{krw:,.0f} / 상한 ₩{av.DAY_KRW:,.0f})"
    elif total >= av.TOTAL_KRW:
        capped, cap_msg = True, f"누적 상한 초과(약 ₩{total:,.0f} / 상한 ₩{av.TOTAL_KRW:,.0f})"
    auth_missing = 0
    if capped:
        attempts.append(("vertex", "capped"))
    else:
        for route, proj, acct in stages:
            try:
                tok = _token(acct)
            except Exception:  # noqa: BLE001
                tok = ""
            if not tok:
                auth_missing += 1
                attempts.append((route, "no_token"))
                continue
            t0 = time.time()
            url = f"https://aiplatform.googleapis.com/v1/projects/{proj}/locations/{av.REGION}/publishers/google/models/{model}:generateContent"
            code, j = _http_post(url, {"Authorization": "Bearer " + tok}, _body(prompt, search), timeout)
            tok = ""
            if code == 200 and j:
                text, src, u, sq = _parse(j)
                tin = int(u.get("promptTokenCount", 0))
                tout = int(u.get("candidatesTokenCount", 0)) + int(u.get("thoughtsTokenCount", 0))
                est = tin / 1e6 * av.PRICE_IN + tout / 1e6 * av.PRICE_OUT + sq * av.PRICE_SEARCH
                try:
                    _vertex_usage_row(who, model, search, tin, tout, sq, est, int(time.time() - t0), 0)
                except OSError:
                    pass
                return done(text, route, "ok", f"추정 약 ₩{est:,.1f}(입력 {tin}·출력 {tout}·검색 {sq}건)", src, t0, 0)
            attempts.append((route, f"HTTP{code}"))
            _log(who, route, f"HTTP{code}", int((time.time() - t0) * 1000), 0)
            if code == 429:
                _quota_hit("제미나이-" + route, f"who={who} HTTP429 Resets in 1m")

    # 전부 실패
    if capped and not any(s.startswith("HTTP") for r, s in attempts if r != "free"):
        code, status = EXIT["capped"], "capped"
        msg = f"[라우터 거부] {cap_msg}. 무료 키는 이미 실패({_free_summary(attempts)}). 내일 또는 상한 조정 뒤 다시."
    elif auth_missing == 2 and not keys:
        code, status = EXIT["noauth"], "noauth"
        msg = "[라우터 실패] 쓸 수 있는 인증이 없음(무료 키·회사/개인 gcloud 토큰 모두 없음). 환경 변수 이름 GOOGLE_API_KEY 또는 gcloud 로그인을 확인."
    else:
        code, status = EXIT["failed"], "failed"
        msg = "[라우터 실패] 모든 단계 실패: " + ", ".join(f"{r}={s}" for r, s in attempts)
    msg = mask(msg)
    return done(msg, "none", status, "비용 없음(호출 실패)", [], t_all, code)


def _free_summary(attempts):
    return ",".join(s for r, s in attempts if r == "free") or "시도 없음"


def main(argv=None):
    ap = argparse.ArgumentParser(description="제미나이 공용 라우터(무료 키 -> 회사 Vertex -> 개인 Vertex)")
    ap.add_argument("q", help="질문 문장, 또는 @파일경로")
    ap.add_argument("--who", default="unknown")
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args(argv)
    prompt = Path(a.q[1:]).read_text(encoding="utf-8") if a.q.startswith("@") else a.q
    r = call(prompt, model=a.model, search=a.search, who=a.who, timeout=a.timeout)
    if r["exit_code"] == 0:
        print(r["text"])
        for s in r["sources"]:
            print(f"- {s.get('title')}: {s.get('uri')}", file=sys.stderr)
        print(f"[경로 {r['route']}] {r['cost_note']}", file=sys.stderr)
    else:
        print(r["text"], file=sys.stderr)
    return r["exit_code"]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
