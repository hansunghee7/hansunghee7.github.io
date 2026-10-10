"""pipeline_db.py 시험: 네트워크 없이 opsdb._call 을 가짜 서버로 바꿔 출력 형식·비밀값 거부·표 미생성 안내·seed 호출 본문(대장 먼저)·add-run 의 last_success 갱신을 확인한다.
비밀값 모양 시험 문자열은 조각을 이어 붙여 만든다(소스에 키처럼 보이는 글자를 그대로 두지 않기 위해).

실행: python -m pytest scripts/ops/tests/test_pipeline_db.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
import opsdb  # noqa: E402

spec = importlib.util.spec_from_file_location("pipeline_db_under_test", OPS / "pipeline_db.py")
pdb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdb)

FAKE_SECRETS = [
    'sk' + '-' + 'abcdefghijklmnop1234',
    'AI' + 'za' + 'SyA1234567890abcdefghijklmnop',
    'sb_' + 'secret_' + 'abc',
    'gh' + 'p_' + 'abc123',
    'https://x.com/a?api' + '_key=zzz',
    'github' + '_pat_' + '11AAAA',
]


class Fake:
    """GET 은 표 이름별 준비된 응답, 그 밖은 호출 기록."""

    def __init__(self):
        self.tables = {}
        self.calls = []
        self.error = None

    def __call__(self, method, path, body=None, prefer=None, extra=None):
        self.calls.append({'method': method, 'path': path, 'body': body, 'prefer': prefer})
        if self.error:
            raise RuntimeError(self.error)
        if method == 'GET':
            table = path.lstrip('/').split('?')[0]
            return 200, self.tables.get(table, []), {}
        if method == 'POST' and prefer == 'return=representation':
            return 201, [{'id': 55}], {}
        return 204, None, {}


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(opsdb, '_call', f)
    return f


def writes(fake):
    return [c for c in fake.calls if c['method'] != 'GET']


PIPES = [
    {'slug': 'sns-collect', 'name': 'SNS 공개 채널 수집', 'kind': '스크래핑', 'status': '작동', 'ledger_slug': 'sns', 'last_success': '2026-10-11T01:00:00+00:00',
     'hours_since_success': 2.0, 'stale': False},
    {'slug': 'news-api', 'name': '뉴스 API', 'kind': 'API', 'status': '막힘', 'ledger_slug': 'sns', 'last_success': None, 'hours_since_success': None, 'stale': True,
     'freshness_hours': 24, 'watch_job_id': 'news-job'},
    {'slug': 'loose', 'name': '대장 없는 것', 'kind': '파일', 'status': '계획', 'ledger_slug': None, 'last_success': None, 'stale': False},
]
LEDGERS = [{'slug': 'sns', 'name': 'SNS 대장', 'status': '부분', 'pipelines': 2, 'stale_count': 1, 'blocked_count': 1}]


def test_status_groups_by_ledger(fake, capsys):
    fake.tables['v_pipeline_status'] = PIPES
    fake.tables['v_ledger_health'] = LEDGERS
    pdb.main(['status'])
    out = capsys.readouterr().out
    assert '3개 파이프라인, 대장 1곳' in out
    assert '[대장] SNS 대장 (sns)  [부분]' in out and '[대장 미지정]' in out
    assert 'sns-collect' in out and '마지막 성공 2026-10-11 01:00 (2시간 전)' in out
    assert '성공 기록 없음 <stale, 막힘>' in out
    assert '합계: 작동 1, 막힘 1, 계획 1, stale 1' in out


def test_stale_only(fake, capsys):
    fake.tables['v_pipeline_status'] = PIPES
    pdb.main(['stale'])
    out = capsys.readouterr().out
    assert '1개' in out and 'news-api' in out and '기준 24시간' in out and '감시 news-job' in out
    assert 'sns-collect' not in out


def test_stale_none(fake, capsys):
    pdb.main(['stale'])
    assert '없음' in capsys.readouterr().out


def test_ledgers_output(fake, capsys):
    fake.tables['v_ledger_health'] = LEDGERS
    pdb.main(['ledgers'])
    out = capsys.readouterr().out
    assert '데이터 대장 1곳' in out and '[부분]' in out and '파이프라인 2개' in out and 'stale 1' in out and '막힘 1' in out


def test_howto_output(fake, capsys):
    fake.tables['data_pipelines'] = [{'slug': 'news-api', 'name': '뉴스 API', 'kind': 'API', 'status': '막힘', 'status_note': '429', 'source': 'news.example/api',
                                      'engine': '헤르메스 크론', 'schedule': '매시', 'destination': 'news_items', 'ledger_slug': 'sns', 'auth_ref': '패스 이름 news',
                                      'how_to': 'python scripts/news.py --once', 'watch_job_id': 'news-job', 'process_ref': '공정 #9', 'limits': '하루 100건',
                                      'tos_risk': '낮음(공식 API)', 'last_success': None}]
    pdb.main(['howto', 'news-api'])
    out = capsys.readouterr().out
    for s in ('뉴스 API (news-api)  종류: API  상태: 막힘 (429)', '수동 실행 방법: python scripts/news.py --once', '감시 id news-job', '한계: 하루 100건',
              '약관 위험: 낮음(공식 API)', '인증 참조: 패스 이름 news'):
        assert s in out


def test_howto_unknown(fake):
    with pytest.raises(SystemExit) as e:
        pdb.main(['howto', 'nope'])
    assert '파이프라인 없음' in str(e.value)


def test_add_run_ok_updates_last_success(fake, capsys):
    fake.tables['data_pipelines'] = [{'slug': 'news-api'}]
    pdb.main(['add-run', 'news-api', '--ok', 'yes', '--rows', '120', '--note', '1회 실행'])
    posts = writes(fake)
    assert posts[0]['path'] == '/pipeline_runs'
    assert posts[0]['body'][0]['pipeline_slug'] == 'news-api' and posts[0]['body'][0]['ok'] is True and posts[0]['body'][0]['rows_in'] == 120
    assert posts[1]['method'] == 'PATCH' and posts[1]['path'] == '/data_pipelines?slug=eq.news-api'
    assert 'last_success' in posts[1]['body'] and 'last_checked' in posts[1]['body']
    assert 'run_id=55' in capsys.readouterr().out


def test_add_run_failure_keeps_last_success(fake):
    fake.tables['data_pipelines'] = [{'slug': 'news-api'}]
    pdb.main(['add-run', 'news-api', '--ok', 'no', '--note', '429'])
    patch = writes(fake)[1]
    assert 'last_checked' in patch['body'] and 'last_success' not in patch['body']


def test_set_status(fake):
    fake.tables['data_pipelines'] = [{'slug': 'news-api'}]
    pdb.main(['set-status', 'news-api', '작동', '--note', '첫 자동 실행 확인'])
    p = writes(fake)[0]
    assert p['method'] == 'PATCH' and p['body']['status'] == '작동' and p['body']['status_note'] == '첫 자동 실행 확인'
    with pytest.raises(SystemExit):
        pdb.main(['set-status', 'news-api', '이상함'])


def test_register_plans_and_prints_procedure(fake, capsys):
    fake.tables['pipeline_ledgers'] = [{'slug': 'sns'}]
    pdb.main(['register', 'new-pipe', '--name', '새 수집', '--kind', 'API', '--source', 'x.example', '--owner', '탐', '--schedule', '매일', '--engine', '크론',
              '--destination', 'tbl', '--watch-job', 'new-job', '--ledger', 'sns'])
    p = writes(fake)[0]
    assert p['path'] == '/data_pipelines?on_conflict=slug'
    row = p['body'][0]
    assert row['status'] == '계획' and row['watch_job_id'] == 'new-job' and row['ledger_slug'] == 'sns' and row['kind'] == 'API'
    out = capsys.readouterr().out
    assert '다음 절차' in out and 'jobs.toml' in out and 'add-run' in out


def test_register_rejects_duplicate_and_unknown_ledger(fake):
    fake.tables['data_pipelines'] = [{'slug': 'dup'}]
    with pytest.raises(SystemExit) as e:
        pdb.main(['register', 'dup', '--name', '중복'])
    assert '이미 있는' in str(e.value)
    fake.tables['data_pipelines'] = []  # 가짜 서버는 조건을 무시하므로 새 slug 상황은 표를 비워 만든다
    with pytest.raises(SystemExit) as e:
        pdb.main(['register', 'fresh', '--name', '새것', '--ledger', 'nope'])
    assert '데이터 대장 없음' in str(e.value)
    assert not writes(fake)


@pytest.mark.parametrize('secret', FAKE_SECRETS)
def test_secret_shapes_rejected(fake, secret):
    fake.tables['data_pipelines'] = [{'slug': 'news-api'}]
    with pytest.raises(SystemExit) as e:
        pdb.main(['add-run', 'news-api', '--ok', 'yes', '--note', f'키 {secret} 노출'])
    assert '비밀값' in str(e.value)
    assert not writes(fake)


def test_length_limit(fake):
    fake.tables['data_pipelines'] = [{'slug': 'news-api'}]
    with pytest.raises(SystemExit) as e:
        pdb.main(['set-status', 'news-api', '작동', '--note', 'x' * 2000])
    assert '너무 깁니다' in str(e.value)


def test_table_missing_message(fake):
    fake.error = 'DB 오류 HTTP 404: {"code":"PGRST205","message":"Could not find the table in the schema cache"}'
    with pytest.raises(SystemExit) as e:
        pdb.main(['status'])
    assert str(e.value) == '표 미생성: pipeline_schema.sql 실행 필요'


def test_seed_ledgers_first_then_pipelines_skipping_non_pipeline_jobs(fake, tmp_path, capsys):
    leds = [{'slug': 'sns', 'name': 'SNS 대장', 'status': '작동', 'freshness_hours': 24}]
    pls = [{'slug': 'news-api', 'name': '뉴스 API', 'kind': 'API', 'status': '작동', 'ledger_slug': 'sns'},
           {'slug': 'b', 'name': 'B', 'status': '계획', 'non_pipeline_jobs': ['x', 'y']},
           {'non_pipeline_jobs': ['메모용 객체']}]
    (tmp_path / 'seed_ledgers.json').write_text(json.dumps(leds, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'seed_pipelines.json').write_text(json.dumps(pls, ensure_ascii=False), encoding='utf-8')
    pdb.main(['seed', str(tmp_path)])
    posts = writes(fake)
    assert [p['path'] for p in posts] == ['/pipeline_ledgers?on_conflict=slug', '/data_pipelines?on_conflict=slug']
    assert posts[0]['prefer'] == 'resolution=merge-duplicates,return=minimal'
    assert posts[0]['body'][0]['slug'] == 'sns' and 'updated_at' in posts[0]['body'][0]
    assert [r['slug'] for r in posts[1]['body']] == ['news-api', 'b']
    assert all('non_pipeline_jobs' not in r for r in posts[1]['body'])
    assert '대장 1, 파이프라인 2' in capsys.readouterr().out


def test_seed_missing_files_and_bad_rows(fake, tmp_path, capsys):
    pdb.main(['seed', str(tmp_path)])
    assert '시드 파일 없음' in capsys.readouterr().out
    f = tmp_path / 'seed_pipelines.json'
    f.write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '이상'}]), encoding='utf-8')
    with pytest.raises(SystemExit):
        pdb.main(['seed', str(tmp_path)])
    f.write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '작동', 'extra_col': 'x'}]), encoding='utf-8')
    with pytest.raises(SystemExit) as e:
        pdb.main(['seed', str(tmp_path)])
    assert '알 수 없는 열' in str(e.value)
    assert not writes(fake)


def test_seed_secret_in_row_rejected(fake, tmp_path):
    (tmp_path / 'seed_ledgers.json').write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '작동', 'update_process': FAKE_SECRETS[0]}]), encoding='utf-8')
    with pytest.raises(SystemExit):
        pdb.main(['seed', str(tmp_path)])
    assert not fake.calls
