"""훅 래퍼의 출력 인코딩 시험(카빗DM 3차 항목 6·19): 기본 코드페이지가 cp949여도 차단문이 UTF-8로 나와야 한다.
실행: python .claude/hooks/test_hook_wrappers_utf8.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).parent
BASH = shutil.which('bash')
WRAPPERS = ['check-dash', 'check-tone', 'drive-gate', 'guide-notice-gate', 'mail-wake',
            'main-checkout-gate', 'now-not-later-gate', 'save-gate']


def test_wrappers_export_utf8():
    for n in WRAPPERS:
        body = (HOOKS / f'{n}.sh').read_text(encoding='utf-8')
        assert 'PYTHONUTF8=1' in body and 'PYTHONIOENCODING=utf-8' in body, n


def test_save_gate_block_message_is_utf8_even_with_cp949_default():
    if not BASH:
        return
    ev = [{'type': 'user', 'message': {'content': [{'type': 'text', 'text': '프로세스표에 저장하라는 거 꼭 저장하고'}]}},
          {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '알겠습니다'}]}}]
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        f.write('\n'.join(json.dumps(e, ensure_ascii=False) for e in ev))
        p = f.name
    try:
        env = dict(os.environ, PYTHONIOENCODING='cp949', CLAUDE_PROJECT_DIR=str(HOOKS.parent.parent))
        env.pop('PYTHONUTF8', None)
        r = subprocess.run([BASH, str(HOOKS / 'save-gate.sh')],
                           input=json.dumps({'transcript_path': p, 'stop_hook_active': False}).encode('utf-8'),
                           capture_output=True, env=env)
    finally:
        os.unlink(p)
    assert r.returncode == 2, r.returncode
    assert '저장 관문' in r.stderr.decode('utf-8')  # UTF-8로 읽혀야 한다


if __name__ == '__main__':
    test_wrappers_export_utf8()
    test_save_gate_block_message_is_utf8_even_with_cp949_default()
    print('ok')
