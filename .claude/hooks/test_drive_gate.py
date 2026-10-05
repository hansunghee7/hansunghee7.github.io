"""drive-gate.py 시험: python .claude/hooks/test_drive_gate.py  (목표 장부 C:/work/_ops/tam_drive.json 필요)"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

H = Path(__file__).with_name("drive-gate.py")


def run(final_text, active_flag=False):
    ev = [{"type": "user", "message": {"content": [{"type": "text", "text": "질문"}]}},
          {"type": "assistant", "message": {"content": [{"type": "text", "text": final_text}]}}]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write("\n".join(json.dumps(e, ensure_ascii=False) for e in ev))
        p = f.name
    try:
        raw = json.dumps({"transcript_path": p, "stop_hook_active": active_flag}).encode("utf-8")
        return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True).returncode
    finally:
        os.unlink(p)


block = [
    "라우터 1단계를 시작해도 될까요? 정하실 것: 1) 시작 2) 보류",
    "정하실 것: 수파베이스 관문 대상을 넓힐까요?",
    "내용 보고.\n[실행 대기: 사장님의 라우터 1단계 시작 여부]",
]
ok = [
    "라우터 1단계를 시작했습니다. 증거: 로그.",
    "크레딧 허용 문장이 필요합니다. [사람 개입 필요: 규칙상 금지]\n정하실 것: 허용하시겠어요?",
    "오늘 날씨는 맑습니다. 시작해도 될까요?",
    "[실행 대기: 내일 09:20 새김 사용량 첫 자동 실행 결과]",
]
bad = []
for t in block:
    if run(t) != 2:
        bad.append("막아야함: " + t[:30])
for t in ok:
    if run(t) != 0:
        bad.append("통과해야함: " + t[:30])
if run(block[0], True) != 0:
    bad.append("stop_hook_active는 통과해야함")
n = len(block) + len(ok) + 1
print("통과" if not bad else "실패: " + "; ".join(bad), f"({n - len(bad)}/{n})")
sys.exit(1 if bad else 0)
