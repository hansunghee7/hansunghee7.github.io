#!/usr/bin/env python3
"""제미나이 웹앱 경유 질문(라우터 갈래 'gemini-web'). 2026-10-11 G1, 기본 꺼짐.

왜: 무료 AI Studio 키는 검색 연동 요청만 429이고, Vertex는 GCP 크레딧이 끝나면 못 쓴다. 구PC 크롬에 이미 로그인된
    제미나이 웹앱으로 질문하면 크레딧 없이 검색 답과 출처 링크를 받는다(이미지 생성은 같은 방식으로 이미 성공, logos_gem_batch.py).
위치: gemini_route.call() 안에서 ① 무료 키가 실패한 뒤, ② 회사 Vertex 앞. 환경 변수 GEMINI_WEB=1 일 때만 켜진다.
사람 빈도(메모리 규칙: 외부 자동화는 사람 빈도로, 계정을 바꿔 두드리지 않기, 차단 문구가 종료 조건):
  - 계정(포트)마다 하루 DAY_CAP 건, 같은 계정 호출 사이 MIN_GAP_SEC 초 이상, 질문 길이 MAX_Q 자.
  - 차단 문구·로그인 화면·계정 불일치가 나오면 그 계정은 그날 중지(다른 계정은 계속, 전면 중단 아님). 같은 계정을 재시도하지 않는다.
  - 허용 계정은 사장님이 이미지 생성용으로 지정한 무료 보조 계정. 환경 변수 GEMINI_WEB_PORTS(쉼표)로 바꾼다(기본 9224,9225).
상태: C:/work/_ops/gemini_web_state.json (포트 번호·횟수·시각·중지 사유만. 계정 이메일·질문·답 없음)
기록: C:/work/_ops/gemini_web_log.jsonl (who·포트·status·secs·바이트 수만)
원격: ssh 별칭 goosolar 에서 ~/workshop/gemini_web/gemini_web_ask.py(= tools/gemini_web/gemini_web_ask.py)를 돌린다. 설치: --install
사용(코드): import gemini_web; r = gemini_web.ask("질문", who="탐"); r["text"], r["sources"], r["status"], r["exit_code"]
사용(CLI):  python scripts/ops/gemini_web.py --who 탐 "질문"   /   --install   /   --status
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

STATE = Path("C:/work/_ops/gemini_web_state.json")
LOG = Path("C:/work/_ops/gemini_web_log.jsonl")
SSH_HOST = os.environ.get("GEMINI_WEB_HOST", "goosolar")
REMOTE_DIR = "~/workshop/gemini_web"
REMOTE_PY = "~/workshop/venv/bin/python"
REMOTE_SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "gemini_web" / "gemini_web_ask.py"
DAY_CAP = int(os.environ.get("GEMINI_WEB_DAY_CAP", "8"))
MIN_GAP_SEC = int(os.environ.get("GEMINI_WEB_MIN_GAP", "90"))
MAX_Q = 1500
STOP_STATUSES = ("blocked", "login", "mismatch", "consent")  # 이 결과면 그 계정은 그날 중지
EXIT_OK, EXIT_FAIL = 0, 2


def enabled():
    return os.environ.get("GEMINI_WEB") == "1"


def ports():
    return [p.strip() for p in os.environ.get("GEMINI_WEB_PORTS", "9224,9225").split(",") if p.strip()]


def _today():
    return f"{datetime.now():%Y-%m-%d}"


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def _log(who, port, status, secs, nbytes):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {"time": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "who": who, "port": port, "status": status, "secs": secs, "bytes": nbytes}
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def pick_account(st, now=None):
    """(포트, None) 또는 (None, 사유). 오늘 중지 안 됐고, 상한 미만이고, 간격이 지난 계정 중 오늘 호출이 가장 적은 것."""
    now = now if now is not None else time.time()
    day = st.get(_today(), {})
    best, why = None, []
    for p in ports():
        a = day.get(p, {})
        if a.get("stopped"):
            why.append(f"{p}:중지({a['stopped']})")
        elif a.get("calls", 0) >= DAY_CAP:
            why.append(f"{p}:일상한")
        elif now - a.get("last", 0) < MIN_GAP_SEC:
            why.append(f"{p}:간격")
        elif best is None or a.get("calls", 0) < day.get(best, {}).get("calls", 0):
            best = p
    return (best, None) if best else (None, ",".join(why) or "계정 없음")


def _run_remote(port, question, timeout):
    """원격 실행기를 부르고 JSON 한 줄을 읽는다. 시험에서 가짜로 바꾼다. 반환: dict."""
    cmd = f"f=$(mktemp); cat > $f; {REMOTE_PY} {REMOTE_DIR}/gemini_web_ask.py --port {int(port)} --question-file $f --timeout {int(timeout)}; rm -f $f"
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, cmd], input=question, capture_output=True,
                           text=True, encoding="utf-8", timeout=timeout + 60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"status": "error", "text": "", "sources": [], "secs": 0, "note": f"ssh 실패: {type(e).__name__}"}
    for line in reversed((r.stdout or "").strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {"status": "error", "text": "", "sources": [], "secs": 0, "note": f"원격 출력 없음(rc={r.returncode})"}


def ask(question, who="unknown", timeout=150):
    """반환: call()과 같은 키 dict(text, route, status, cost_note, sources, exit_code, tried). route=gemini-web|none. 실패해도 예외 없음."""
    def fail(status, note, port=None):
        return {"text": note, "route": "none", "status": status, "cost_note": "비용 없음", "sources": [], "exit_code": EXIT_FAIL, "tried": [("gemini-web", status)], "port": port}

    q = (question or "").strip()
    if not q or len(q) > MAX_Q:
        return fail("rejected", f"질문 길이 1~{MAX_Q}자만 허용(현재 {len(q)}자)")
    st = load_state()
    port, why = pick_account(st)
    if port is None:
        return fail("throttled", f"쓸 수 있는 계정 없음: {why}")
    day = st.setdefault(_today(), {})
    a = day.setdefault(port, {"calls": 0})
    a["calls"] += 1  # 호출 직전에 센다: 도중에 죽어도 횟수는 남는다
    a["last"] = time.time()
    save_state(st)
    res = _run_remote(port, q, timeout)
    status = str(res.get("status", "error"))
    text = str(res.get("text", ""))
    _log(who, port, status, res.get("secs", 0), len(text.encode("utf-8")))
    if status in STOP_STATUSES:
        a["stopped"] = f"{status} {datetime.now():%H:%M}"
        save_state(st)
        return fail(status, f"[gemini-web 계정 {port} 오늘 중지] {res.get('note', '')}", port)
    if status != "ok" or not text.strip():
        return fail(status if status != "ok" else "empty", f"[gemini-web 실패] {res.get('note', '')}", port)
    src = [{"title": s.get("title"), "uri": s.get("uri")} for s in res.get("sources", []) if s.get("uri")]
    return {"text": text, "route": "gemini-web", "status": "ok", "cost_note": f"제미나이 웹앱(계정 {port}, 비용 0, {res.get('secs', 0)}초)",
            "sources": src, "exit_code": EXIT_OK, "tried": [("gemini-web", "ok")], "port": port}


def install():
    """원격 실행기를 구PC에 복사한다(scp). 반환 코드."""
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", SSH_HOST, f"mkdir -p {REMOTE_DIR}"], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        return r.returncode
    return subprocess.run(["scp", "-q", str(REMOTE_SCRIPT), f"{SSH_HOST}:{REMOTE_DIR}/gemini_web_ask.py"], capture_output=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description="제미나이 웹앱 경유 질문(구PC, 사람 빈도 이하)")
    ap.add_argument("q", nargs="?", help="질문 문장, 또는 @파일경로")
    ap.add_argument("--who", default="unknown")
    ap.add_argument("--timeout", type=int, default=150)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    if a.install:
        rc = install()
        print("설치 " + ("성공" if rc == 0 else f"실패 rc={rc}"))
        return rc
    if a.status:
        print(json.dumps(load_state().get(_today(), {}), ensure_ascii=False))
        return 0
    if not a.q:
        ap.error("질문이 필요합니다")
    q = Path(a.q[1:]).read_text(encoding="utf-8") if a.q.startswith("@") else a.q
    r = ask(q, who=a.who, timeout=a.timeout)
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
