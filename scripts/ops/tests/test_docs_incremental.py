"""docs_incremental.py: 실패 사유 기록·비밀 가림·시간 예산 시험(DB·ollama 호출 없음)."""
import importlib.util
import sys
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("docs_incremental_under_test", OPS / "docs_incremental.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_scrub_hides_secrets():
    jwtlike = '.'.join(['e' + 'yJ' + 'a' * 12, 'b' * 12, 'c' * 12])  # 소스에 토큰 꼴을 직접 쓰지 않으려 조립
    out = m.scrub(f"401 apikey=abcdef123456 and {jwtlike} ok")
    assert 'abcdef123456' not in out and jwtlike not in out and '401' in out


def test_record_error_writes_stage_and_type(tmp_path, monkeypatch):
    f = tmp_path / 'err.txt'
    monkeypatch.setattr(m, 'ERR_FILE', f)
    line = m.record_error('임베딩', TimeoutError('timed out token=SECRETVALUE99'))
    text = f.read_text(encoding='utf-8')
    assert '단계=임베딩' in text and 'TimeoutError' in text and 'SECRETVALUE99' not in text
    assert line.strip() == text.strip()
    m.clear_error()
    assert not f.exists()


def test_budget_default_below_job_timeout():
    assert m.BUDGET_SEC < 900


def test_embedding_budget_stops_and_resumes(monkeypatch, capsys):
    """예산이 지났으면 임베딩 첫 행 전에 멈추고 정상 종료(다음 실행이 embedding is null 행부터 이어 채움)."""
    saved = []
    rows = [{'path': f'p{i}', 'title': 't', 'headings': '', 'summary': '', 'tags': '', 'questions': ''} for i in range(3)]
    monkeypatch.setattr(m, 'BUDGET_SEC', -1)
    monkeypatch.setattr(m, 'clear_error', lambda: None)
    monkeypatch.setattr(m.opsdb, 'select', lambda t, cols, **k: rows if k.get('where') == {'embedding': 'is.null'} else [])
    monkeypatch.setattr(m.opsdb, 'upsert', lambda *a, **k: saved.append(a) or 0)
    monkeypatch.setattr(m.opsdb, 'count', lambda t: 0)
    monkeypatch.setattr(m.imp, 'collect', lambda: [])
    monkeypatch.setattr(m.imp, 'ROOTS', {})
    monkeypatch.setattr(m.sys, 'argv', ['x'])
    assert m.main() == 0
    out = capsys.readouterr().out
    assert '시간 예산' in out and '임베딩 0/3' in out and not saved
