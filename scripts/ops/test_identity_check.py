import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import identity_check as ic


def test_persona_of():
    assert ic.persona_of('carvit_tam') == ('known', '탐')
    assert ic.persona_of('carvit-jitu') == ('known', '지투')
    assert ic.persona_of('carvit_kabit-tam') == ('known', '탐')
    assert ic.persona_of('carvit') == ('generic', None)
    assert ic.persona_of('carvit_zzz')[0] == 'unknown'


def test_check_ok_and_mixed():
    assert ic.check(['carvit_tam'], '탐') == []
    assert ic.check(['carvit', 'carvit_tam'], '탐') == []
    assert ic.check(['carvit-jitu', 'carvit_tam'])  # 섞임
    assert ic.check(['carvit_tam'], '노트')  # 기대 불일치
    assert ic.check(['carvit_zzz'])  # 미등록
    assert any('이름이 없다' in w for w in ic.check(['carvit']))  # generic만
    assert ic.who_line(['carvit', 'carvit_tam']).startswith('🪪 너는 탐(carvit_tam)')
    assert ic.who_line(['carvit-jitu', 'carvit_tam']) == ''


def test_cli_mixed_folder(tmp_path):
    cj = tmp_path / 'c.json'
    cj.write_text(json.dumps({'projects': {'C:/w/a': {'mcpServers': {'carvit-jitu': {}, 'carvit_tam': {}, 'other': {}}}}}), encoding='utf-8')
    r = subprocess.run([sys.executable, str(Path(ic.__file__)), '--cwd', 'C:\\w\\a', '--claude-json', str(cj), '--no-log'], capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL)
    assert r.returncode == 1 and '섞여' in r.stdout
    cj.write_text(json.dumps({'projects': {'C:/w/a': {'mcpServers': {'carvit_tam': {}}}}}), encoding='utf-8')
    r = subprocess.run([sys.executable, str(Path(ic.__file__)), '--cwd', 'C:/w/a', '--claude-json', str(cj), '--no-log'], capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL)
    assert r.returncode == 0 and '너는 탐' in r.stdout and 'session-start' in r.stdout
