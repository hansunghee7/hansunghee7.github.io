import json, subprocess, sys, os
H = os.path.join(os.path.dirname(__file__), "token-leak-gate.py")


def run(payload):
    p = subprocess.run([sys.executable, H], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), capture_output=True)
    return p.returncode


def test_blocks_telegram_token():
    cmd = 'curl "https://api.telegram.org/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/getMe"'
    assert run({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 2


def test_blocks_openai_key():
    assert run({"tool_name": "Bash", "tool_input": {"command": "export KEY=sk-abcdefghijklmnopqrstuvwx"}}) == 2


def test_allows_env_var_reference():
    assert run({"tool_name": "Bash", "tool_input": {"command": 'curl "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe"'}}) == 0


def test_allows_unrelated_command():
    assert run({"tool_name": "Bash", "tool_input": {"command": "echo hello"}}) == 0


def test_escape_hatch():
    cmd = 'echo 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw "[자격증명 확인됨: 재발급 직후 1회 검증]"'
    assert run({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 0


def test_other_tool_untouched():
    assert run({"tool_name": "Read", "tool_input": {"file_path": "x"}}) == 0


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
