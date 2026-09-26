import json, os, subprocess, sys, tempfile
H = os.path.join(os.path.dirname(__file__), "token-leak-gate.py")

# 값을 조립해서 만든다(리터럴로 그대로 두면 GitHub push protection이 진짜 키로 오탐해 push가 막힘).
FAKE_TG_TOKEN = "123456789" + ":" + "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" + "X"
FAKE_OPENAI_KEY = "sk-" + "abcdefghijklmnopqrstuvwx"
FAKE_STRIPE_KEY = "sk_live_" + "abcdefghijklmnopqrstuvwx"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "dQw4w9WgXcQrealsigxxxxxxxxxxxxxxxxxxxxxxx"


def run(payload, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable, H], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), capture_output=True, env=e)
    return p.returncode


def test_blocks_telegram_token():
    cmd = f'curl "https://api.telegram.org/bot{FAKE_TG_TOKEN}/getMe"'
    assert run({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 2


def test_blocks_openai_key():
    assert run({"tool_name": "Bash", "tool_input": {"command": f"export KEY={FAKE_OPENAI_KEY}"}}) == 2


def test_blocks_stripe_workos_key():
    assert run({"tool_name": "Bash", "tool_input": {"command": f"echo {FAKE_STRIPE_KEY}"}}) == 2


def test_blocks_jwt():
    assert run({"tool_name": "Bash", "tool_input": {"command": f"echo {FAKE_JWT}"}}) == 2


def test_allows_env_var_reference():
    assert run({"tool_name": "Bash", "tool_input": {"command": 'curl "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe"'}}) == 0


def test_allows_unrelated_command():
    assert run({"tool_name": "Bash", "tool_input": {"command": "echo hello"}}) == 0


def test_escape_hatch_logs():
    with tempfile.TemporaryDirectory() as d:
        logpath = os.path.join(d, "escape.log")
        cmd = f'echo {FAKE_TG_TOKEN} "[자격증명 확인됨: 재발급 직후 1회 검증]"'
        rc = run({"tool_name": "Bash", "tool_input": {"command": cmd}}, env={"TOKEN_LEAK_GATE_LOG": logpath})
        assert rc == 0
        assert os.path.exists(logpath)
        with open(logpath, encoding="utf-8") as f:
            assert "텔레그램" in f.read()


def test_blocks_write_content():
    assert run({"tool_name": "Write", "tool_input": {"file_path": "x.env", "content": f"TOKEN={FAKE_OPENAI_KEY}"}}) == 2


def test_blocks_edit_new_string():
    assert run({"tool_name": "Edit", "tool_input": {"file_path": "x.py", "old_string": "a", "new_string": FAKE_OPENAI_KEY}}) == 2


def test_allows_edit_without_secret():
    assert run({"tool_name": "Edit", "tool_input": {"file_path": "x.py", "old_string": "a", "new_string": "b"}}) == 0


def test_other_tool_untouched():
    assert run({"tool_name": "Read", "tool_input": {"file_path": "x"}}) == 0


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
