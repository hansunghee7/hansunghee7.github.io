"""Carvit 에이전트 메일(내 에이전트 ↔ 동료 에이전트) 끝단 점검.

사용:
  python scripts/ops/agentmail_e2e.py              # 기본(자기 발송 시도, 거절되면 SKIP)
  python scripts/ops/agentmail_e2e.py --allow-peer # 자기 발송이 거절되면 동료(탐)에게 실제 발송
  python scripts/ops/agentmail_e2e.py --json       # 기계용 출력

점검 순서(단계마다 시간 측정):
  1 initialize        200 + mcp-session-id
  2 tools/list        agents, mail_send, mail_read 존재
  3 agents            is_me 에이전트 + 다른 에이전트 1명 이상, untrusted_text_notice
  4 mail_send         자기 자신에게 "[e2e] YYYY-MM-DD HH:MM" (거절 시 --allow-peer면 동료에게)
  5 mail_read         응답 파싱, untrusted_text_notice 포함, 자기 발송이면 방금 메일 확인

종료 코드: 0 = 실패 없음(SKIP 허용), 1 = 실패 1건 이상.
토큰은 타미 헤르메스 프로필 .env에서 실행 시점에 읽고 출력·기록하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone

URL = "https://mcp.carvit.ai/mcp"
ENV_PATH = r"C:/Users/PC/AppData/Local/hermes/profiles/tami/.env"
TOKEN_KEY = "CARVIT_MCP_TOKEN"
REQUIRED_TOOLS = ("agents", "mail_send", "mail_read")
PEER_NAME = "탐"
KST = timezone(timedelta(hours=9))

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


# ---------------------------------------------------------------- 파싱(네트워크 없음, 시험 대상)

def parse_body(text: str):
    """JSON 또는 SSE("data:" 줄) 본문을 dict로. 해석 불가면 None."""
    body = text or ""
    if "data:" in body:
        lines = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")]
        body = lines[-1] if lines else ""
    body = body.strip()
    if not body.startswith("{"):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def tool_result(rpc: dict | None):
    """tools/call 응답 → (is_error, text, payload_dict_or_None)."""
    if not isinstance(rpc, dict):
        return True, "응답 해석 불가", None
    if "error" in rpc:
        return True, str(rpc["error"].get("message", rpc["error"])), None
    res = rpc.get("result") or {}
    texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
    text = "\n".join(texts)
    payload = None
    if text.strip().startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
    return bool(res.get("isError")), text, payload


def check_tools_list(rpc: dict | None):
    names = [t.get("name") for t in ((rpc or {}).get("result") or {}).get("tools", [])]
    missing = [n for n in REQUIRED_TOOLS if n not in names]
    if missing:
        return FAIL, f"도구 없음: {', '.join(missing)} (전체 {len(names)}개)"
    return PASS, f"필수 도구 3개 확인(전체 {len(names)}개)"


def check_agents(rpc: dict | None):
    """→ (status, detail, me_name, other_names)."""
    is_err, text, p = tool_result(rpc)
    if is_err or not p:
        return FAIL, f"agents 오류: {text[:120]}", None, []
    agents = p.get("agents") or []
    me = [a for a in agents if a.get("is_me")]
    others = [a.get("name") for a in agents if not a.get("is_me")]
    if not me:
        return FAIL, "is_me 에이전트 없음", None, others
    if not others:
        return FAIL, f"나({me[0].get('name')}) 말고 다른 에이전트 없음", me[0].get("name"), []
    notice = "있음" if "untrusted_text_notice" in p else "없음"
    return PASS, f"나={me[0].get('name')}, 동료 {len(others)}명, 안전 안내 {notice}", me[0].get("name"), others


def is_self_send_rejection(rpc: dict | None) -> bool:
    is_err, text, _ = tool_result(rpc)
    return is_err and ("내 에이전트" in text or "self" in text.lower())


def check_send_ok(rpc: dict | None):
    is_err, text, p = tool_result(rpc)
    if is_err:
        return FAIL, f"발송 오류: {text[:120]}"
    if p is not None and p.get("sent") is True:
        return PASS, "sent: true"
    if p is not None and "sent" in p:
        return FAIL, f"sent={p.get('sent')}"
    return FAIL, f"sent 필드 없음: {text[:120]}"


def check_mail_read(rpc: dict | None, marker: str | None):
    """marker가 있으면(자기 발송 성공) 그 메일이 보여야 PASS."""
    is_err, text, p = tool_result(rpc)
    if is_err or p is None:
        return FAIL, f"mail_read 오류: {text[:120]}"
    if "untrusted_text_notice" not in p:
        return FAIL, "untrusted_text_notice 없음(보안 안내 누락)"
    mails = p.get("mail")
    if mails is None:
        mails = p.get("mails", [])
    count = p.get("count", len(mails) if isinstance(mails, list) else 0)
    extra = ", 동료 데이터 안내 있음" if "peer_data_notice" in p else ""
    if marker:
        found = any(marker in json.dumps(m, ensure_ascii=False) for m in (mails or []))
        if not found:
            return FAIL, f"방금 보낸 메일을 못 찾음(새 메일 {count}건)"
        return PASS, f"방금 보낸 메일 확인(새 메일 {count}건){extra}"
    return PASS, f"읽기 정상(새 메일 {count}건), 안전 안내 있음{extra}"


def summarize(steps: list[dict]) -> tuple[int, str]:
    fails = [s for s in steps if s["status"] == FAIL]
    skips = [s for s in steps if s["status"] == SKIP]
    total_ms = sum(s["ms"] for s in steps)
    if fails:
        line = f"에이전트 메일 점검 실패: {fails[0]['step']} 단계({len(fails)}건 실패), 총 {total_ms}ms"
        return 1, line
    tail = f", SKIP {len(skips)}건" if skips else ""
    return 0, f"에이전트 메일 점검 정상: {len(steps) - len(skips)}단계 통과{tail}, 총 {total_ms}ms"


# ---------------------------------------------------------------- 네트워크

def read_token() -> str:
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if line.startswith(TOKEN_KEY + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"{TOKEN_KEY} 없음(타미 프로필 .env)")


class Client:
    def __init__(self, token: str):
        import httpx

        self.c = httpx.Client(timeout=30)
        self.h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                  "Accept": "application/json, text/event-stream"}
        self.sid = None
        self.i = 0

    def post(self, method: str, params: dict | None = None, notify: bool = False):
        h = dict(self.h)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        msg = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self.i += 1
            msg["id"] = self.i
            msg["params"] = params or {}
        r = self.c.post(URL, headers=h, json=msg)
        return r, parse_body(r.text)

    def call(self, name: str, args: dict):
        return self.post("tools/call", {"name": name, "arguments": args})[1]

    def close(self):
        self.c.close()


def run(allow_peer: bool) -> list[dict]:
    steps: list[dict] = []

    def step(name, fn):
        t0 = time.perf_counter()
        try:
            status, detail = fn()
        except Exception as e:  # 네트워크·해석 예외는 그 단계 실패
            status, detail = FAIL, f"{type(e).__name__}: {str(e)[:120]}"
        steps.append({"step": name, "status": status, "detail": detail,
                      "ms": int((time.perf_counter() - t0) * 1000)})
        return status

    try:
        cl = Client(read_token())
    except Exception as e:
        steps.append({"step": "token", "status": FAIL, "detail": str(e)[:120], "ms": 0})
        return steps

    ctx: dict = {}
    try:
        def s_init():
            r, _ = cl.post("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                          "clientInfo": {"name": "agentmail-e2e", "version": "1"}})
            if r.status_code != 200:
                return FAIL, f"HTTP {r.status_code}"
            cl.sid = r.headers.get("mcp-session-id")
            if not cl.sid:
                return FAIL, "mcp-session-id 헤더 없음"
            cl.post("notifications/initialized", notify=True)
            return PASS, "HTTP 200, 세션 발급"

        if step("initialize", s_init) == FAIL:
            return steps

        if step("tools_list", lambda: check_tools_list(cl.post("tools/list")[1])) == FAIL:
            return steps

        def s_agents():
            st, d, me, others = check_agents(cl.call("agents", {}))
            ctx["me"], ctx["others"] = me, others
            return st, d

        if step("agents", s_agents) == FAIL:
            return steps

        stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        marker = f"[e2e] {stamp}"
        body = f"{marker} 에이전트 메일 끝단 점검(agentmail_e2e.py). 답장 필요 없음."

        def s_send():
            res = cl.call("mail_send", {"to": ctx["me"], "body": body})
            is_err, text, _ = tool_result(res)
            if not is_err:
                ctx["self_marker"] = marker
                return PASS, "자기 자신에게 발송 성공"
            if not is_self_send_rejection(res):
                return FAIL, f"자기 발송 오류: {text[:120]}"
            ctx["self_rejected"] = True
            if not allow_peer:
                return SKIP, "서버가 자기 발송 거절(정책), --allow-peer 없음"
            if PEER_NAME not in (ctx.get("others") or []):
                return FAIL, f"동료 '{PEER_NAME}' 없음"
            st, d = check_send_ok(cl.call("mail_send", {"to": PEER_NAME, "body": body}))
            return st, f"자기 발송 거절 → {PEER_NAME}에게 발송: {d}"

        step("mail_send", s_send)
        step("mail_read", lambda: check_mail_read(cl.call("mail_read", {}), ctx.get("self_marker")))
    finally:
        cl.close()
    return steps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    ap.add_argument("--allow-peer", action="store_true", help="자기 발송이 거절되면 동료(탐)에게 실제 발송")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    steps = run(a.allow_peer)
    code, line = summarize(steps)
    if a.json:
        print(json.dumps({"ok": code == 0, "summary": line, "at": datetime.now(KST).isoformat(timespec="seconds"),
                          "steps": steps}, ensure_ascii=False))
    else:
        print(line)
        for s in steps:
            print(f"  [{s['status']}] {s['step']} {s['ms']}ms - {s['detail']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
