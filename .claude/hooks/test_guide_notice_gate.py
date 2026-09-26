import json, subprocess, sys, os
H = os.path.join(os.path.dirname(__file__), "guide-notice-gate.py")

def run(payload):
    p = subprocess.run([sys.executable, H], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), capture_output=True)
    return p.returncode

def test_blocks_boss_context():
    assert run({"tool_name": "SendMessage", "tool_input": {"to": "탐", "message": "[지투→탐] 사장님이 깨진 화면을 봤는데 검수 결과입니다"}}) == 2

def test_allows_update_only():
    assert run({"tool_name": "SendMessage", "tool_input": {"to": "탐", "message": "[지투→탐] UX 가이드 업데이트(2026-09-26.17): 1.29 상태 아이콘 - 뜻은 아이콘마다 올리면 표시"}}) == 0

def test_other_sender_untouched():
    assert run({"tool_name": "SendMessage", "tool_input": {"to": "탐", "message": "[노트→탐] 사장님 확인 요청 pinBase 전달"}}) == 0

def test_mailbox_blocked():
    cmd = 'python mailbox/mailbox.py send 탐 "제목" --from 지투 --body "판정: 위반입니다"'
    assert run({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 2

def test_mailbox_to_note_untouched():
    cmd = 'python mailbox/mailbox.py send 노트 "제목" --from 지투 --body "사장님 결정"'
    assert run({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 0

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
