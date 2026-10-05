"""save-gate.py 시험: python .claude/hooks/test_save_gate.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

H = Path(__file__).with_name('save-gate.py')


def run(boss, final='답변', cmd=None, active=False):
    ev = [{'type': 'user', 'message': {'content': [{'type': 'text', 'text': boss}]}}]
    content = []
    if cmd:
        content.append({'type': 'tool_use', 'name': 'Bash', 'input': {'command': cmd}})
    content.append({'type': 'text', 'text': final})
    ev.append({'type': 'assistant', 'message': {'content': content}})
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        f.write('\n'.join(json.dumps(e, ensure_ascii=False) for e in ev))
        p = f.name
    try:
        return subprocess.run([sys.executable, str(H)], input=json.dumps({'transcript_path': p, 'stop_hook_active': active}).encode('utf-8'), capture_output=True).returncode
    finally:
        os.unlink(p)


block = [
    ('이런 걸 에이전트들이 절대 까먹지 말라고 프로세스표에 정리해두라는 겁니다', '정리했습니다', None),
    ('프로세스표에 저장하라는 거 꼭 저장하고', '알겠습니다', None),
    ('아래 단계로 정리해두세요', '네', None),
]
ok = [
    ('이런 걸 절대 까먹지 말라고 프로세스표에 정리해두라는 겁니다', '카드 추가', 'python scripts/ops/proc.py add 카빗패스등록 "제목" --do x'),
    ('프로세스표에 저장하라고', '[저장 불필요: 이미 같은 카드가 있음] 확인', None),
    ('오늘 날씨 어때요', '맑음', None),
    ('토큰량 감소 맘에 듭니다', '네', None),
]
bad = []
for b, f, c in block:
    if run(b, f, c) != 2:
        bad.append('막아야함: ' + b[:24])
for b, f, c in ok:
    if run(b, f, c) != 0:
        bad.append('통과해야함: ' + b[:24])
if run(block[0][0], '네', None, True) != 0:
    bad.append('stop_hook_active 통과')
n = len(block) + len(ok) + 1
print('통과' if not bad else '실패: ' + '; '.join(bad), f'({n - len(bad)}/{n})')
sys.exit(1 if bad else 0)
