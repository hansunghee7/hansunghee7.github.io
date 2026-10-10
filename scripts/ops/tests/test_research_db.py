"""research_db.py 시험: 네트워크 없이 opsdb._call 을 가짜 서버로 바꿔 출력 형식·비밀값 거부·표 미생성 안내·seed 호출 본문을 확인한다.
비밀값 모양 시험 문자열은 조각을 이어 붙여 만든다(소스에 키처럼 보이는 글자를 그대로 두지 않기 위해).

실행: python -m pytest scripts/ops/tests/test_research_db.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
import opsdb  # noqa: E402

spec = importlib.util.spec_from_file_location("research_db_under_test", OPS / "research_db.py")
rdb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rdb)

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
            return 201, [{'id': 77}], {}
        return 204, None, {}


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(opsdb, '_call', f)
    return f


def writes(fake):
    return [c for c in fake.calls if c['method'] != 'GET']


MODS = [
    {'slug': 'super', 'name': '슈퍼리서치', 'status': '작동', 'kind': '체계'},
    {'slug': 'gem', 'name': '제미나이 리서치', 'status': '부분', 'kind': '모듈'},
    {'slug': 'vertex', 'name': '버텍스 대체', 'status': '막힘', 'kind': '경로'},
]


def test_status_output(fake, capsys):
    fake.tables['v_research_status'] = [
        {'slug': 'super', 'name': '슈퍼리서치', 'status': '작동', 'last_run_at': '2026-10-11T09:30:00+00:00', 'last_run_ok': True, 'open_issues': 0},
        {'slug': 'gem', 'name': '제미나이 리서치', 'status': '부분', 'last_run_at': None, 'last_run_ok': None, 'open_issues': 2},
    ]
    rdb.main(['status'])
    out = capsys.readouterr().out
    assert '2개 모듈' in out and '[작동]' in out and '[부분]' in out
    assert '2026-10-11 09:30 성공' in out
    assert '실행 기록 없음' in out and '열린 이슈 2건' in out
    assert '합계: 작동 1, 부분 1' in out


def test_howto_output(fake, capsys):
    fake.tables['v_research_howto'] = [{'slug': 'gem', 'name': '제미나이 리서치', 'status': '부분', 'entry': 'python scripts/ops/gemini_route.py',
                                        'how_to': '질문을 한 번에 몰아서 보낸다', 'limits': '무료키 호출 수', 'process_ref': '공정 카드 #12'}]
    fake.tables['research_issues'] = [{'id': 5, 'status': '열림', 'symptom': '429', 'fix': '키 교대'}]
    rdb.main(['howto', 'gem'])
    out = capsys.readouterr().out
    for s in ('제미나이 리서치 (gem)  상태: 부분', '실행 명령: python scripts/ops/gemini_route.py', '방법: 질문을', '한계: 무료키', '공정 카드 #12', '열린 이슈 1건', '#5 [열림] 429 -> 키 교대'):
        assert s in out


def test_howto_unknown(fake):
    with pytest.raises(SystemExit) as e:
        rdb.main(['howto', 'nope'])
    assert '모듈 없음' in str(e.value)


def test_tree_order_and_fallback(fake, capsys):
    fake.tables['research_modules'] = MODS
    fake.tables['research_links'] = [
        {'parent': 'super', 'child': 'vertex', 'seq': 2, 'role': 'fallback', 'required': False, 'note': '제미나이 막힐 때'},
        {'parent': 'super', 'child': 'gem', 'seq': 1, 'role': 'step', 'required': True, 'note': None},
    ]
    rdb.main(['tree', 'super'])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith('슈퍼리서치 (super) [작동]')
    assert lines[1].startswith('  1단계: 제미나이 리서치 (gem) [부분]')
    assert lines[2].startswith('  대체: 버텍스 대체 (vertex) [막힘] (선택) - 제미나이 막힐 때')


def test_issues_default_filters_open(fake, capsys):
    fake.tables['research_issues'] = [{'id': 1, 'slug': 'gem', 'found_at': '2026-10-10', 'symptom': '인용 불일치', 'cause': '링크 지어냄', 'fix': '재열람', 'status': '열림'}]
    rdb.main(['issues', 'gem'])
    out = capsys.readouterr().out
    assert '이슈 1건' in out and '원인: 링크 지어냄' in out and '조치: 재열람' in out
    q = fake.calls[-1]['path']
    assert 'slug=eq.gem' in q and 'status=in.' in q


def test_add_run_posts_row_and_prints_id(fake, capsys):
    fake.tables['research_modules'] = [{'slug': 'gem'}]
    rdb.main(['add-run', 'gem', '--who', '탐', '--question', '시장 규모', '--route', 'gemini', '--ok', 'yes', '--cost', '120', '--path', 'C:/x/out.md'])
    assert 'run_id=77' in capsys.readouterr().out
    post = writes(fake)[0]
    assert post['path'] == '/research_runs'
    assert post['body'] == [{'slug': 'gem', 'who': '탐', 'question': '시장 규모', 'route': 'gemini', 'result_path': 'C:/x/out.md', 'ok': True, 'cost_krw': 120.0}]


def test_add_issue_upserts_on_slug_symptom(fake):
    fake.tables['research_modules'] = [{'slug': 'gem'}]
    rdb.main(['add-issue', 'gem', '--symptom', '429', '--cause', '한도', '--fix', '교대', '--status', '열림'])
    post = writes(fake)[0]
    assert 'on_conflict=slug,symptom' in post['path']
    assert post['body'][0]['symptom'] == '429' and post['body'][0]['status'] == '열림'


def test_set_status_patches(fake):
    fake.tables['research_modules'] = [{'slug': 'gem'}]
    rdb.main(['set-status', 'gem', '막힘', '--note', '키 만료', '--verified'])
    p = writes(fake)[0]
    assert p['method'] == 'PATCH' and p['path'] == '/research_modules?slug=eq.gem'
    assert p['body']['status'] == '막힘' and p['body']['status_note'] == '키 만료' and 'last_verified' in p['body']


def test_set_status_rejects_bad_status(fake):
    with pytest.raises(SystemExit):
        rdb.main(['set-status', 'gem', '이상함'])


def test_link_check(fake):
    rdb.main(['link-check', '77', 'https://example.com/a', '200', '확인', '--note', '본문 일치'])
    p = writes(fake)[0]
    assert p['path'] == '/research_link_checks'
    assert p['body'] == [{'url': 'https://example.com/a', 'note': '본문 일치', 'run_id': 77, 'http': 200, 'verdict': '확인'}]


@pytest.mark.parametrize('secret', FAKE_SECRETS)
def test_secret_shapes_rejected(fake, secret):
    fake.tables['research_modules'] = [{'slug': 'gem'}]
    with pytest.raises(SystemExit) as e:
        rdb.main(['add-issue', 'gem', '--symptom', f'키 {secret} 노출'])
    assert '비밀값' in str(e.value)
    assert not writes(fake)


def test_length_limit(fake):
    fake.tables['research_modules'] = [{'slug': 'gem'}]
    with pytest.raises(SystemExit) as e:
        rdb.main(['add-issue', 'gem', '--symptom', 'x' * 2000])
    assert '너무 깁니다' in str(e.value)


def test_table_missing_message(fake):
    fake.error = 'DB 오류 HTTP 404: {"code":"PGRST205","message":"Could not find the table in the schema cache"}'
    with pytest.raises(SystemExit) as e:
        rdb.main(['status'])
    assert str(e.value) == '표 미생성: research_schema.sql 실행 필요'


def test_seed_upserts_in_order(fake, tmp_path, capsys):
    (tmp_path / 'seed_modules.json').write_text(json.dumps(MODS, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'seed_links.json').write_text(json.dumps([{'parent': 'super', 'child': 'gem', 'seq': 1, 'role': 'step'}]), encoding='utf-8')
    rdb.main(['seed', str(tmp_path)])
    posts = writes(fake)
    assert [p['path'] for p in posts] == ['/research_modules?on_conflict=slug', '/research_links?on_conflict=parent,child,role']
    assert posts[0]['prefer'] == 'resolution=merge-duplicates,return=minimal'
    assert [r['slug'] for r in posts[0]['body']] == ['super', 'gem', 'vertex'] and 'updated_at' in posts[0]['body'][0]
    assert posts[1]['body'] == [{'parent': 'super', 'child': 'gem', 'seq': 1, 'role': 'step'}]
    assert '모듈 3, 링크 1' in capsys.readouterr().out


def test_seed_missing_files_and_bad_rows(fake, tmp_path, capsys):
    rdb.main(['seed', str(tmp_path)])
    assert '시드 파일 없음' in capsys.readouterr().out
    (tmp_path / 'seed_modules.json').write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '이상'}]), encoding='utf-8')
    with pytest.raises(SystemExit):
        rdb.main(['seed', str(tmp_path)])
    (tmp_path / 'seed_modules.json').write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '작동', 'extra_col': 'x'}]), encoding='utf-8')
    with pytest.raises(SystemExit) as e:
        rdb.main(['seed', str(tmp_path)])
    assert '알 수 없는 열' in str(e.value)
    assert not writes(fake)


def test_seed_secret_in_row_rejected(fake, tmp_path):
    (tmp_path / 'seed_modules.json').write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '작동', 'how_to': FAKE_SECRETS[0]}]), encoding='utf-8')
    with pytest.raises(SystemExit):
        rdb.main(['seed', str(tmp_path)])
    assert not fake.calls
