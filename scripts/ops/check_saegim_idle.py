#!/usr/bin/env python3
r"""새김 MCP 세션 유지 점검(백로그 41, 2026-09-25 탐): 고객처럼 한 번 연결해 조회하고,
연결을 쥔 채 몇 분 쉬었다가 같은 세션으로 다시 조회한다. 끊김("Truncated response body" 등, 백로그 40)이
유휴 뒤 재조회에서 나는지를 사람보다 먼저 잡기 위한 합성 감시.

점검 계정은 지투의 고객 경로 점검과 같은 것(C:\work\_ops\secrets\jitu_check_tenant.env)을 읽기만 한다.
헤르메스 no-agent 크론으로 돈다(사본: 헤르메스 scripts/). 정상이면 출력 없이 exit 0(빈 출력 = 알림 없음),
실패면 원인 한 줄 출력 + 탐에게 우편 + exit 1. --verbose면 정상일 때도 한 줄 찍는다.
사용: python scripts/ops/check_saegim_idle.py [--idle 300] [--verbose]
"""
from __future__ import annotations
import argparse, os, subprocess, sys, time
from pathlib import Path

SECRETS_ENV = Path(r"C:\work\_ops\secrets\jitu_check_tenant.env")
MAILBOX = r"C:\work\solar-bible\mailbox\mailbox.py"
# 헤르메스 번들 파이썬의 mcp는 pywin32 없이 깔려 import에서 죽는다(지투 실측 2026-09-24). 시스템 파이썬으로 다시 실행한다.
SYS_PY = r"C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if os.path.exists(SYS_PY) and os.path.normcase(sys.executable) != os.path.normcase(SYS_PY) and not os.environ.get("SAEGIM_IDLE_CHILD"):
    _env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    _env.update(SAEGIM_IDLE_CHILD="1", PYTHONIOENCODING="utf-8")
    sys.exit(subprocess.run([SYS_PY, os.path.abspath(__file__), *sys.argv[1:]], env=_env).returncode)


def load_env(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); out[k.strip()] = v.strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idle", type=int, default=300); ap.add_argument("--doc", default="UX_GUIDE"); ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    env = load_env(SECRETS_ENV)
    url, tid, sec = env["SAEGIM_MCP_URL"], env["SAEGIM_TENANT_ID"], env["SAEGIM_TENANT_SECRET"]
    import anyio, httpx
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def run() -> int:
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {tid}:{sec}"}, timeout=60.0) as http:
            async with streamable_http_client(url, http_client=http) as (read, write, *_):
                async with ClientSession(read, write) as s:
                    await s.initialize()
                    t0 = time.time(); r1 = await s.call_tool("list_sections", {"doc": a.doc}); d1 = time.time() - t0
                    if r1.isError:
                        print(f"FAIL 첫 조회 오류: {str(r1.content)[:120]}"); return 1
                    await anyio.sleep(a.idle)
                    t0 = time.time(); r2 = await s.call_tool("list_sections", {"doc": a.doc}); d2 = time.time() - t0
                    if r2.isError:
                        print(f"FAIL {a.idle}초 쉰 뒤 재조회 오류: {str(r2.content)[:120]}"); return 1
                    if a.verbose:
                        print(f"OK 첫 조회 {d1:.1f}초, {a.idle}초 유휴 뒤 재조회 {d2:.1f}초")
                    return 0
    try:
        rc = anyio.run(run)
    except Exception as e:  # 끊김은 대개 여기로 온다(전송 계층 예외)
        print(f"FAIL {type(e).__name__}: {str(e)[:150]}"); rc = 1
    if rc:
        subprocess.run([sys.executable, MAILBOX, "send", "탐", "[감시] 새김 세션 유지 점검 실패", "--from", "헤르메스",
                        "--body", "check_saegim_idle.py 실패(백로그 40 끊김 재현 가능성). 헤르메스 크론 출력의 FAIL 줄 참고."],
                       capture_output=True, timeout=30)
    return rc


if __name__ == "__main__":
    sys.exit(main())
