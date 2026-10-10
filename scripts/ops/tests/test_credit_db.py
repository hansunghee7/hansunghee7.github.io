"""credit_db.py 시험: 네트워크 없이 opsdb._call 을 가짜 서버로 바꿔 출력 형식·비밀값 거부·표 미생성 안내·seed 호출 본문·add-event 잔액 동시 갱신을 확인한다.
비밀값 모양 시험 문자열은 조각을 이어 붙여 만든다(소스에 키처럼 보이는 글자를 그대로 두지 않기 위해).

실행: python -m pytest scripts/ops/tests/test_credit_db.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
import opsdb  # noqa: E402

spec = importlib.util.spec_from_file_location("credit_db_under_test", OPS / "credit_db.py")
cdb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cdb)

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
        return 204, None, {}


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(opsdb, '_call', f)
    return f


def writes(fake):
    return [c for c in fake.calls if c['method'] != 'GET']


ACC = [{'slug': 'openrouter'}]


def test_status_output(fake, capsys):
    fake.tables['v_credit_status'] = [
        {'slug': 'openrouter', 'name': '오픈라우터', 'kind': '유료선불', 'status': '정상', 'balance': 12.5, 'currency': 'USD', 'days_to_expiry': None,
         'balance_at': '2026-10-11T01:00:00+00:00', 'balance_age_hours': 3.0, 'low': False},
        {'slug': 'gcp-credit', 'name': 'GCP 무료 크레딧', 'kind': '무료크레딧', 'status': '주의', 'balance': 40000, 'currency': 'KRW', 'days_to_expiry': 12,
         'balance_at': '2026-10-01T01:00:00+00:00', 'balance_age_hours': 240.0, 'low': True},
        {'slug': 'newone', 'name': '신규', 'kind': '한도형', 'status': '미확인', 'balance': None, 'currency': None, 'days_to_expiry': -2,
         'balance_at': None, 'balance_age_hours': None, 'low': False},
    ]
    cdb.main(['status'])
    out = capsys.readouterr().out
    assert '3개 계정' in out
    assert '12.5 USD' in out and '만료 없음' in out and '확인 3시간 전' in out
    assert '40000 KRW' in out and '만료 12일 남음' in out and '낡음 240시간' in out and '<잔액 부족>' in out
    assert '잔액 미확인' in out and '만료 2일 지남' in out and '확인 기록 없음' in out
    assert '합계: 정상 1, 주의 1, 미확인 1' in out


def test_expiring_output(fake, capsys):
    fake.tables['v_credit_expiring'] = [{'slug': 'gcp-credit', 'name': 'GCP 무료 크레딧', 'status': '주의', 'balance': 40000, 'currency': 'KRW',
                                         'days_to_expiry': 12, 'balance_at': '2026-10-01T01:00:00+00:00', 'balance_age_hours': 240, 'reasons': '만료 임박, 확인 낡음'}]
    cdb.main(['expiring'])
    out = capsys.readouterr().out
    assert '주의가 필요한 계정 1개' in out and '사유: 만료 임박, 확인 낡음' in out


def test_expiring_empty(fake, capsys):
    cdb.main(['expiring'])
    assert '없음' in capsys.readouterr().out


def test_howto_output(fake, capsys):
    fake.tables['credit_accounts'] = [{'slug': 'openrouter', 'name': '오픈라우터', 'kind': '유료선불', 'status': '정상', 'balance': 12.5, 'currency': 'USD',
                                       'balance_at': '2026-10-11T01:00:00+00:00', 'expires_at': None, 'alert_threshold': 5, 'how_to_check': '대시보드 Credits 화면',
                                       'check_command': 'python scripts/ops/or_balance.py', 'account_email': 'simon@simplifier.co.kr', 'workspace': True,
                                       'resource_id': 'or-main', 'billing_ref': '카드 참조 B-1', 'refill_rule': '5달러 미만이면 충전'}]
    cdb.main(['howto', 'openrouter'])
    out = capsys.readouterr().out
    for s in ('오픈라우터 (openrouter)  종류: 유료선불  상태: 정상', '잔액: 12.5 USD', '대시보드 Credits 화면', 'python scripts/ops/or_balance.py',
              '5달러 미만이면 충전', 'simon@simplifier.co.kr  워크스페이스: 예', '자원 or-main, 청구 참조 카드 참조 B-1'):
        assert s in out


def test_howto_unknown(fake):
    with pytest.raises(SystemExit) as e:
        cdb.main(['howto', 'nope'])
    assert '계정 없음' in str(e.value)


def test_events_output(fake, capsys):
    fake.tables['credit_events'] = [{'id': 1, 'at': '2026-10-11T02:00:00+00:00', 'kind': '차감', 'amount': -3, 'balance_after': 97, 'who': '탐', 'note': '호출'}]
    cdb.main(['events', 'openrouter'])
    out = capsys.readouterr().out
    assert '2026-10-11 02:00 [차감] -3 -> 잔액 97 (탐) 호출' in out
    assert 'account_slug=eq.openrouter' in fake.calls[-1]['path']


def test_add_event_updates_balance_too(fake, capsys):
    fake.tables['credit_accounts'] = ACC
    cdb.main(['add-event', 'openrouter', '--kind', '차감', '--amount', '-3', '--balance-after', '97', '--who', '탐', '--note', '호출', '--evidence', 'log.txt'])
    posts = writes(fake)
    assert [p['method'] for p in posts] == ['POST', 'PATCH']
    ev = posts[0]
    assert ev['path'] == '/credit_events?on_conflict=account_slug,at,kind'
    assert ev['body'][0]['kind'] == '차감' and ev['body'][0]['amount'] == -3.0 and ev['body'][0]['balance_after'] == 97.0 and ev['body'][0]['who'] == '탐'
    pt = posts[1]
    assert pt['path'] == '/credit_accounts?slug=eq.openrouter'
    assert pt['body']['balance'] == 97.0 and pt['body']['balance_at'] == ev['body'][0]['at']
    assert '97 로 갱신' in capsys.readouterr().out


def test_add_event_without_balance_does_not_patch(fake):
    fake.tables['credit_accounts'] = ACC
    cdb.main(['add-event', 'openrouter', '--kind', '확인', '--note', '그냥 확인'])
    assert [p['method'] for p in writes(fake)] == ['POST']


def test_add_event_bad_kind_and_unknown_account(fake):
    with pytest.raises(SystemExit):
        cdb.main(['add-event', 'openrouter', '--kind', '이상함'])
    with pytest.raises(SystemExit) as e:
        cdb.main(['add-event', 'nope', '--kind', '차감'])
    assert '계정 없음' in str(e.value)
    assert not writes(fake)


def test_set_balance_patches_and_logs_check_event(fake):
    fake.tables['credit_accounts'] = ACC
    cdb.main(['set-balance', 'openrouter', '88.5', '--note', '화면 확인'])
    posts = writes(fake)
    assert posts[0]['method'] == 'PATCH' and posts[0]['body']['balance'] == 88.5 and 'balance_at' in posts[0]['body']
    assert posts[1]['path'] == '/credit_events?on_conflict=account_slug,at,kind'
    assert posts[1]['body'][0]['kind'] == '확인' and posts[1]['body'][0]['balance_after'] == 88.5


def test_set_status(fake):
    fake.tables['credit_accounts'] = ACC
    cdb.main(['set-status', 'openrouter', '소진', '--note', '0 원'])
    p = writes(fake)[0]
    assert p['method'] == 'PATCH' and p['body']['status'] == '소진' and p['body']['note'] == '0 원'
    with pytest.raises(SystemExit):
        cdb.main(['set-status', 'openrouter', '이상함'])


@pytest.mark.parametrize('secret', FAKE_SECRETS)
def test_secret_shapes_rejected(fake, secret):
    fake.tables['credit_accounts'] = ACC
    with pytest.raises(SystemExit) as e:
        cdb.main(['add-event', 'openrouter', '--kind', '확인', '--note', f'키 {secret} 노출'])
    assert '비밀값' in str(e.value)
    assert not writes(fake)


def test_length_limit(fake):
    fake.tables['credit_accounts'] = ACC
    with pytest.raises(SystemExit) as e:
        cdb.main(['set-status', 'openrouter', '정상', '--note', 'x' * 2000])
    assert '너무 깁니다' in str(e.value)


def test_table_missing_message(fake):
    fake.error = 'DB 오류 HTTP 404: {"code":"PGRST205","message":"Could not find the table in the schema cache"}'
    with pytest.raises(SystemExit) as e:
        cdb.main(['status'])
    assert str(e.value) == '표 미생성: credit_schema.sql 실행 필요'


def test_seed_upserts_accounts_then_events(fake, tmp_path, capsys):
    accs = [{'slug': 'openrouter', 'name': '오픈라우터', 'kind': '유료선불', 'currency': 'USD', 'balance': 12.5, 'status': '정상', 'workspace': False}]
    evs = [{'account_slug': 'openrouter', 'at': '2026-10-11T00:00:00+00:00', 'kind': '충전', 'amount': 20, 'balance_after': 20}]
    (tmp_path / 'seed_accounts.json').write_text(json.dumps(accs, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'seed_events.json').write_text(json.dumps(evs, ensure_ascii=False), encoding='utf-8')
    cdb.main(['seed', str(tmp_path)])
    posts = writes(fake)
    assert [p['path'] for p in posts] == ['/credit_accounts?on_conflict=slug', '/credit_events?on_conflict=account_slug,at,kind']
    assert posts[0]['prefer'] == 'resolution=merge-duplicates,return=minimal'
    assert posts[0]['body'][0]['slug'] == 'openrouter' and 'updated_at' in posts[0]['body'][0]
    assert posts[1]['body'] == evs
    assert '계정 1, 사건 1' in capsys.readouterr().out


def test_seed_missing_files_and_bad_rows(fake, tmp_path, capsys):
    cdb.main(['seed', str(tmp_path)])
    assert '시드 파일 없음' in capsys.readouterr().out
    f = tmp_path / 'seed_accounts.json'
    f.write_text(json.dumps([{'slug': 'a', 'name': 'A', 'status': '이상'}]), encoding='utf-8')
    with pytest.raises(SystemExit):
        cdb.main(['seed', str(tmp_path)])
    f.write_text(json.dumps([{'slug': 'a', 'name': 'A', 'extra_col': 'x'}]), encoding='utf-8')
    with pytest.raises(SystemExit) as e:
        cdb.main(['seed', str(tmp_path)])
    assert '알 수 없는 열' in str(e.value)
    assert not writes(fake)


def test_seed_secret_in_row_rejected(fake, tmp_path):
    (tmp_path / 'seed_accounts.json').write_text(json.dumps([{'slug': 'a', 'name': 'A', 'note': FAKE_SECRETS[0]}]), encoding='utf-8')
    with pytest.raises(SystemExit):
        cdb.main(['seed', str(tmp_path)])
    assert not fake.calls
