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
    r = subprocess.run([sys.executable, str(Path(ic.__file__)), '--cwd', 'C:\\w\\a', '--claude-json', str(cj), '--no-log', '--no-monitor'], capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL)
    assert r.returncode == 1 and '섞여' in r.stdout
    cj.write_text(json.dumps({'projects': {'C:/w/a': {'mcpServers': {'carvit_tam': {}}}}}), encoding='utf-8')
    r = subprocess.run([sys.executable, str(Path(ic.__file__)), '--cwd', 'C:/w/a', '--claude-json', str(cj), '--no-log', '--no-monitor'], capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL)
    assert r.returncode == 0 and '너는 탐' in r.stdout and 'session-start' in r.stdout


def test_persona_key():
    assert ic.persona_key(['carvit', 'carvit_tam']) == 'tam'
    assert ic.persona_key(['carvit_kabit-maya']) == 'maya'
    assert ic.persona_key(['carvit-jitu', 'carvit_tam']) == ''
    assert ic.persona_key(['carvit']) == ''


def test_monitor_line(tmp_path):
    root = tmp_path / '_ops'
    # 이름을 모르면 아무 말도 하지 않는다
    assert ic.monitor_line('', str(root), cmdlines=[]) == ''
    # 설정 파일이 없으면 만들라고 안내
    assert '설정 없음' in ic.monitor_line('tam', str(root), cmdlines=[])
    cfg = root / 'carvit_tam' / 'autoreceive_config.json'
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{}', encoding='utf-8')
    # 설정은 있는데 프로세스가 없으면 켜는 명령까지 보여 준다
    out = ic.monitor_line('tam', str(root), cmdlines=['python other.py --config x'])
    assert '모니터 꺼짐' in out and 'Monitor' in out and cfg.as_posix() in out
    # 켜져 있으면 조용하다(역슬래시·대소문자가 달라도 같은 경로로 본다)
    on = ['python carvit_autoreceive.py --config ' + str(cfg).replace('/', chr(92)).upper()]
    assert ic.monitor_line('tam', str(root), cmdlines=on) == ''
    # 다른 사람의 설정으로 도는 프로세스는 내 것으로 치지 않는다
    other = ['python carvit_autoreceive.py --config ' + (root / 'carvit_maya' / 'autoreceive_config.json').as_posix()]
    assert '모니터 꺼짐' in ic.monitor_line('tam', str(root), cmdlines=other)


def test_monitor_line_unknown_process_list_is_silent(tmp_path, monkeypatch):
    cfg = tmp_path / '_ops' / 'carvit_tam' / 'autoreceive_config.json'
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(ic, 'running_commandlines', lambda: None)
    assert ic.monitor_line('tam', str(tmp_path / '_ops')) == ''


def test_monitor_line_ignores_unrelated_process_with_same_path(tmp_path):
    root = tmp_path / '_ops'
    cfg = root / 'carvit_tam' / 'autoreceive_config.json'
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{}', encoding='utf-8')
    fake = ['python unrelated.py --arg ' + cfg.as_posix()]
    assert '모니터 꺼짐' in ic.monitor_line('tam', str(root), cmdlines=fake)


def test_monitor_line_silent_without_ops_root_on_unknown_platform(monkeypatch):
    monkeypatch.delenv('CARVIT_OPS_ROOT', raising=False)
    monkeypatch.setattr(ic.os, 'name', 'posix')
    assert ic.monitor_line('tam', cmdlines=[]) == ''


def test_monitor_line_env_ops_root(tmp_path, monkeypatch):
    root = tmp_path / 'ops'
    monkeypatch.setenv('CARVIT_OPS_ROOT', str(root))
    assert '설정 없음' in ic.monitor_line('tam', cmdlines=[])
