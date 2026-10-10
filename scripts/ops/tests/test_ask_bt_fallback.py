"""ask_bt.sh 장애 전환(낙하) 시험. ssh·python을 PATH 앞의 가짜 명령으로 대체한다(네트워크·gcloud 호출 없음).

가짜 동작은 환경변수로 고른다: FAKE_GEMINI(ok|limit_err|limit_out|fail), FAKE_ROUTER(ok|fail), FAKE_SONNET(ok|limit_err), FAKE_VERTEX(ok|fail).
ssh 가짜는 인자에 '--model'이 있으면 sonnet 풀, 없으면 제미나이 풀로 본다.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "ask_bt.sh"
BASH = shutil.which("bash")

FAKE_SSH = r"""#!/usr/bin/env bash
cat > /dev/null
case "$*" in
  *--model*) mode="${FAKE_SONNET:-ok}"; name=sonnet ;;
  *) mode="${FAKE_GEMINI:-ok}"; name=gemini ;;
esac
case "$mode" in
  ok) echo "정상 답 from $name" ;;
  limit_out) echo "You have hit the rate limit. Try later." ;;
  limit_err) echo "Individual quota reached. Resets in 130h" >&2; exit 1 ;;
  fail) echo "boom" >&2; exit 255 ;;
  empty) echo "jetski: no output produced — a tool required the command permission" >&2 ;;
esac
"""

FAKE_PYTHON = r"""#!/usr/bin/env bash
case "$1" in
  *quota.py) exit 0 ;;
  -c) # 옴니라우터
    if [ "${FAKE_ROUTER:-fail}" = ok ]; then echo "정상 답 from router" > "$4"; exit 0; fi
    echo "router down" > "$4"; exit 1 ;;
  *ask_vertex.py)
    if [ "${FAKE_VERTEX:-ok}" = ok ]; then echo "정상 답 from vertex" > "$3"; exit 0; fi
    echo "RESOURCE_EXHAUSTED daily cap" > "$3"; exit 3 ;;
esac
exit 0
"""


@pytest.fixture
def env(tmp_path):
    if not BASH:
        pytest.skip("bash 없음")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (("ssh", FAKE_SSH), ("python", FAKE_PYTHON)):
        f = bindir / name
        f.write_bytes(body.replace("\r\n", "\n").encode("utf-8"))
        f.chmod(0o755)
    e = dict(os.environ)
    e["PATH"] = str(bindir) + os.pathsep + e["PATH"]
    e["AGENT_CALLS_CSV"] = (tmp_path / "calls.csv").as_posix()
    for k in ("BT_MODEL", "FAKE_GEMINI", "FAKE_ROUTER", "FAKE_SONNET", "FAKE_VERTEX"):
        e.pop(k, None)
    return e, tmp_path


def run(env, **over):
    e, tmp = env
    e = {**e, **over}
    q = tmp / "q.md"
    q.write_text("질문", encoding="utf-8")
    out = tmp / "out.md"
    r = subprocess.run([BASH, str(SCRIPT), q.as_posix(), out.as_posix()], env=e,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, encoding="utf-8", timeout=60)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    csv = (tmp / "calls.csv").read_text(encoding="utf-8") if (tmp / "calls.csv").exists() else ""
    return r, text, csv


def test_first_pool_ok_no_fallback(env):
    r, text, csv = run(env)
    assert r.returncode == 0, r.stderr
    assert text.splitlines()[0] == "<!-- 답한 풀: 비티 -->"
    assert "정상 답 from gemini" in text
    assert "비티-vertex" not in csv


def test_gemini_limit_in_stderr_falls_to_router(env):
    r, text, csv = run(env, FAKE_GEMINI="limit_err", FAKE_ROUTER="ok")
    assert r.returncode == 0, r.stderr
    assert "<!-- 답한 풀: 옴니라우터" in text and "from router" in text


def test_gemini_limit_message_in_stdout_falls(env):
    # 한도 문구가 stdout에 rc=0으로 나와도 낙하해야 한다(보고된 결함)
    r, text, csv = run(env, FAKE_GEMINI="limit_out", FAKE_ROUTER="ok")
    assert r.returncode == 0, r.stderr
    assert "rate limit" not in text
    assert "from router" in text
    assert "비티,"  in csv and ",1\n" in csv  # 비티 풀 한도 신호가 기록됨


def test_falls_through_router_sonnet_to_vertex(env):
    r, text, csv = run(env, FAKE_GEMINI="limit_out", FAKE_ROUTER="fail", FAKE_SONNET="limit_err")
    assert r.returncode == 0, r.stderr
    assert "<!-- 답한 풀: Vertex" in text and "from vertex" in text
    assert "비티-vertex" in csv and "비티-sonnet" in csv


def test_empty_answer_with_rc0_falls_to_next_pool(env):
    # 2026-10-11 실측: 비티(agy 헤드리스)가 도구 권한 자동 거절로 답 없이 종료 코드 0으로 끝나던 경우
    r, text, csv = run(env, FAKE_GEMINI="empty", FAKE_ROUTER="ok")
    assert r.returncode == 0, r.stderr
    assert "<!-- 답한 풀: 옴니라우터" in text and "from router" in text


def test_falls_to_sonnet_before_vertex(env):
    r, text, _ = run(env, FAKE_GEMINI="limit_out", FAKE_ROUTER="fail", FAKE_SONNET="ok")
    assert r.returncode == 0, r.stderr
    assert "<!-- 답한 풀: 비티-sonnet -->" in text


def test_all_fail_exit_3_with_last_error(env):
    r, text, _ = run(env, FAKE_GEMINI="limit_err", FAKE_ROUTER="fail", FAKE_SONNET="limit_err", FAKE_VERTEX="fail")
    assert r.returncode == 3
    assert "마지막 오류" in r.stderr and "Vertex 실패" in r.stderr


def test_explicit_model_does_not_fall_to_others(env):
    r, text, _ = run(env, BT_MODEL="vertex")
    assert r.returncode == 0, r.stderr
    assert "<!-- 답한 풀: Vertex" in text
