"""심플리파이어 다이얼로그(질문하기 Worker)를 호출해 답을 마크다운으로 붙여 쓴다.

사용: python scripts/ask_dialog.py "질문(500자 이내)" <출력.md>
- 답은 사장님 기존 글을 근거로 한 RAG 응답이다. 사장님 발언이 아니라 참고 자료다.
- 공유 시크릿은 insight-7b3e9f2c/ask.html의 ASK_SHARED_SECRET에서 실행할 때 읽는다.
  값을 다른 파일에 복사하지 않는다. 환경변수·시크릿 저장소를 뒤지지 않는다.
- User-Agent를 붙이지 않으면 Cloudflare가 403 error code 1010으로 막는다(2026-09-20 실측).
  브라우저 흉내가 아니라 정직한 식별자를 쓴다.
- 종료 코드: 0 정상(Worker 또는 폴백이 답함), 3 한도, 4 빈 답, 5 403/차단, 6 타임아웃, 7 기타 오류,
  8 폴백도 실패. 0이 아닌 값은 Worker 실패 사유(폴백까지 실패했을 때의 최종 코드)다.
  Worker가 실패하면 로컬 근거 검색 + 공유 라우터(gemini_route)로 자동 폴백한다. 출력의 "경로: worker|fallback"로 구분한다.
  한도(3)를 받으면 20분간 Worker를 부르지 않고 바로 폴백한다(상태 파일 dialog_worker_state.json).
- Worker의 제미나이 키 사용량은 미확인이다. 글 한 편에 2~3회 이내로만 부른다.
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://simplifier-ask.simon-8be.workers.dev/"
REPO = Path(__file__).resolve().parent.parent
STATE_FILE = Path(os.environ.get("DIALOG_STATE_FILE") or "C:/work/_ops/dialog_worker_state.json")
REST_SECONDS = 20 * 60
EXIT_OK, EXIT_LIMIT, EXIT_EMPTY, EXIT_BLOCKED, EXIT_TIMEOUT, EXIT_OTHER, EXIT_FALLBACK_FAIL = 0, 3, 4, 5, 6, 7, 8
ASK_HTML = Path(__file__).resolve().parent.parent / "insight-7b3e9f2c" / "ask.html"


def read_secret():
    m = re.search(r"ASK_SHARED_SECRET\s*=\s*['\"]([^'\"]+)['\"]", ASK_HTML.read_text(encoding="utf-8"))
    if not m:
        sys.exit("ask.html에서 ASK_SHARED_SECRET을 찾지 못했다")
    return m.group(1)


def ask(question):
    if len(question) > 500:
        sys.exit("질문은 500자 이내여야 한다(%d자)" % len(question))
    body = json.dumps({"question": question, "history": []}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "simplifier-maya-desk/1.0 (internal)",
        "X-Ask-Secret": read_secret(),
    })
    out = {"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "question": question,
           "text": "", "sources": [], "log_id": None, "followups": [], "error": None}
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            event = None
            for raw in r:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if event == "chunk":
                        out["text"] += data.get("text", "")
                    elif event == "sources":
                        out["sources"] = data.get("sources", [])
                    elif event == "log_id":
                        out["log_id"] = data.get("id")
                    elif event == "followups":
                        out["followups"] = data.get("questions", [])
                    elif event == "error":
                        out["error"] = json.dumps(data, ensure_ascii=False)
    except urllib.error.HTTPError as e:
        out["error"] = "HTTP %d %s" % (e.code, e.read().decode("utf-8", "replace")[:200])
    except Exception as e:  # 네트워크 차단(클라우드 세션 정책 등)도 여기로 온다
        out["error"] = str(e)[:200]
    return out

def classify(out):
    """Worker 결과를 종료 코드로 분류한다. error 문구·HTTP 코드·빈 답을 본다."""
    err = out.get("error") or ""
    low = err.lower()
    m = re.match(r"HTTP (\d{3})", err)
    http = int(m.group(1)) if m else None
    if http == 429:
        return EXIT_LIMIT
    if http == 403 or "error code: 1010" in low or "error code 1010" in low:
        return EXIT_BLOCKED
    # 문구 판정은 보조: HTTP 코드가 없는 SSE 오류에서 한도 취지 문구('20분' 단독은 근거 아님)
    if http is None and ("한도" in err or "몰려" in err or "rate limit" in low):
        return EXIT_LIMIT
    if "timed out" in low or "timeout" in low:
        return EXIT_TIMEOUT
    if err:
        return EXIT_OTHER
    if not (out.get("text") or "").strip():
        return EXIT_EMPTY
    return EXIT_OK


def worker_resting(now=None):
    """상태 파일에 쉬는 시각이 남아 있으면 True(Worker를 부르지 않는다)."""
    try:
        until = float(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("rest_until", 0))
    except FileNotFoundError:
        return False
    except Exception as e:  # 파싱 오류는 휴식 없음으로 처리
        print("상태 파일 읽기 실패, 휴식 없음으로 처리: %s" % str(e)[:80], file=sys.stderr)
        return False
    return (now if now is not None else time.time()) < until


def set_rest(now=None, seconds=REST_SECONDS):
    t = now if now is not None else time.time()
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_name(STATE_FILE.name + ".%d.tmp" % os.getpid())
        tmp.write_text(json.dumps({
            "rest_until": t + seconds,
            "rest_until_text": datetime.datetime.fromtimestamp(t + seconds).strftime("%Y-%m-%d %H:%M:%S"),
            "reason": "worker 한도"}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATE_FILE)  # 원자적 교체
    except Exception as e:
        print("상태 파일 쓰기 실패: %s" % str(e)[:80], file=sys.stderr)


def _tokens(text):
    """한글은 2글자 조각(조사 영향 완화), 영문·숫자는 단어 단위."""
    toks = set()
    for w in re.findall(r"[0-9A-Za-z]{2,}|[가-힣]+", text.lower()):
        if re.match(r"[가-힣]", w):
            toks.update(w[i:i + 2] for i in range(len(w) - 1))
        else:
            toks.add(w)
    return toks


def _paragraphs(raw):
    raw = re.sub(r"\A---\n.*?\n---\n", "", raw, count=1, flags=re.S)
    return [p.strip() for p in re.split(r"\n\s*\n", raw)
            if len(p.strip()) >= 40 and not p.strip().startswith(("<", "|", "!["))]


def search_local(question, k=4, dirs=None, max_chars=600):
    """log_assets/markdown(및 book/ 의 md)에서 질문과 가장 겹치는 문단 k개. 반환 [(파일명, 문단)]."""
    q = _tokens(question)
    if not q:
        return []
    dirs = dirs or [REPO / "log_assets" / "markdown", REPO / "book"]
    scored = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            raw = f.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^published:\s*false", raw[:1500], re.M):
                continue
            mt = re.search(r"^title:\s*(.+)$", raw[:1500], re.M)
            title_toks = _tokens(f.stem + " " + (mt.group(1) if mt else ""))
            for para in _paragraphs(raw):
                hit = len(q & _tokens(para))
                th = len(q & title_toks)  # 제목·파일명 겹침은 가중치 3배
                if hit >= 2 or (th >= 1 and hit >= 1):
                    scored.append(((hit + 3 * th) / (len(para) ** 0.3), f.name, para[:max_chars]))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], {}
    for _sc, name, para in scored:
        if seen.get(name, 0) >= 2:
            continue
        seen[name] = seen.get(name, 0) + 1
        out.append((name, para))
        if len(out) >= k:
            break
    return out


def build_prompt(question, excerpts):
    ex = "\n\n".join("[발췌 %d] (%s)\n%s" % (i + 1, n, p) for i, (n, p) in enumerate(excerpts))
    return ("아래 사장님 글 발췌만 근거로 답하라. 발췌에 없으면 '답할 수 없다'고 말하라. "
            "답에 근거가 된 발췌 번호를 [발췌 N] 형식으로 인용하라. 사장님 말투나 1인칭 경험담처럼 쓰지 말고, "
            "발췌 인용으로만 답하고, 발췌에 없으면 답할 수 없다고 말하라.\n\n"
            "%s\n\n질문: %s" % (ex or "(관련 발췌 없음)", question))


def fallback(question, worker_code, worker_error):
    """로컬 근거 검색 + 공유 라우터. 라우터 호출 1회."""
    out = {"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "question": question,
           "text": "", "sources": [], "log_id": None, "followups": [], "error": None,
           "route": "fallback", "worker_code": worker_code, "worker_error": worker_error, "router": None}
    excerpts = search_local(question)
    out["sources"] = [{"title": n, "similarity": None, "source_url": "(로컬 발췌) " + n} for n, _ in excerpts]
    if not excerpts:
        out["error"] = "폴백: 관련 발췌를 찾지 못했다"
        return out
    try:
        sys.path.insert(0, str(REPO / "scripts" / "ops"))
        import gemini_route
        r = gemini_route.call(build_prompt(question, excerpts), search=False, who="dialog-fallback")
    except Exception as e:
        out["error"] = "폴백 라우터 오류: " + str(e)[:150]
        return out
    out["router"] = r.get("route")
    if r.get("exit_code") == 0 and (r.get("text") or "").strip():
        out["text"] = r["text"].strip()
    else:
        out["error"] = "폴백 라우터 실패: %s" % r.get("status")
    return out


def ask_with_failover(question):
    """Worker 우선, 실패(한도·403·빈 답·타임아웃·오류)면 폴백. 반환 (out, exit_code)."""
    if worker_resting():
        code, werr = EXIT_LIMIT, "Worker 휴식 중(상태 파일)"
    else:
        w = ask(question)
        code = classify(w)
        if code == EXIT_OK:
            w["route"] = "worker"
            return w, EXIT_OK
        werr = w.get("error") or "빈 답"
        if code == EXIT_LIMIT:
            set_rest()
    fb = fallback(question, code, werr)
    if not fb["error"] and fb["text"]:
        return fb, EXIT_OK
    return fb, code

def render(out):
    lines = ["## 질문 (%s, log_id %s)" % (out.get("time", ""), out.get("log_id")), "", out.get("question", ""), "",
             "### 답변 (사장님 기존 글 기반 RAG 응답, 사장님 발언 아님)", "", out["text"] or "(답 없음)", "",
             "### 참고 자료"]
    lines += ["- %s (유사도 %s) %s" % (s["title"], ("%.2f" % s["similarity"]) if s.get("similarity") is not None else "없음", s["source_url"])
              for s in out["sources"]]
    lines += ["", "### 후속 질문 제안"] + ["- " + q for q in out.get("followups", [])]
    if out.get("error"):
        lines += ["", "### 오류", out["error"]]
    route = out.get("route", "worker")
    lines += ["", "### 경로: %s%s" % (route, (" (Worker 실패 코드 %s, 라우터 %s, 로컬 발췌 기반이라 유사도 없음)" % (
        out.get("worker_code"), out.get("router"))) if route == "fallback" else "")]
    return "\n".join(lines) + "\n\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    if len(sys.argv[1]) > 500:
        sys.exit("질문은 500자 이내여야 한다(%d자)" % len(sys.argv[1]))
    result, code = ask_with_failover(sys.argv[1])
    with open(sys.argv[2], "a", encoding="utf-8", newline="\n") as f:
        f.write(render(result))
    print("경로 %s, 답변 %d자, 참고 자료 %d건, log_id %s, 오류 %s, 종료코드 %d" % (
        result.get("route", "worker"), len(result["text"]), len(result["sources"]), result["log_id"], result["error"], code))
    sys.exit(code)
