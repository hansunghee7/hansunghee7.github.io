#!/usr/bin/env python3
"""recall.py 검색 개선 단위시험(외부 접속 없음: 임시 캐시 파일과 가짜 예외로만).

이메일·키처럼 보이는 문자열은 런타임에 조각을 이어 붙여 만든다(공개 저장소 유출 검사 오탐 방지).
실행: python -m pytest -q scripts/test_recall_improve.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, 'ops')):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

import recall  # noqa: E402

AT = '@'


@pytest.fixture(autouse=True)
def _all_features_on(monkeypatch):
    monkeypatch.delenv('RECALL_OFF', raising=False)


def write_cache(tmp_path, monkeypatch, **over):
    data = {'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'eps': {}, 'grants': [], 'cards': [], 'boss': [], 'docs': [], 'logs': []}
    data.update(over)
    path = tmp_path / 'recall_cache.json'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(recall, 'CACHE', path)
    return path


def card(p, no, t, d='', b=''):
    return {'p': p, 'no': no, 't': t, 'd': d, 'b': b}


# ---------- 1. 낱말: 조사·어미 떼기 ----------
def test_tokens_strip_josa_and_eomi():
    assert '배포' in recall.tokens('배포하는 방법')
    assert '배포' in recall.tokens('배포했나요')
    assert '배포' in recall.tokens('배포를')


def test_tokens_keep_short_stems():
    # 떼고 남는 말이 두 글자 미만이면 떼지 않는다('제한'의 '한'은 어미가 아니다)
    assert '제한' in recall.tokens('제한')
    assert '권한' in recall.tokens('권한')


def test_tokens_norm_switch_off(monkeypatch):
    monkeypatch.setenv('RECALL_OFF', 'norm')
    assert '배포' not in recall.tokens('배포하는')


# ---------- 2. 일반 동의어 ----------
def test_syn_daily_size_limit():
    assert len(recall.SYN_DAILY) <= 20


def test_synonym_counts_as_one_unit(tmp_path, monkeypatch):
    # 질문은 '허락', 기록은 '승인': 동의어로 걸리고, 같은 묶음 두 낱말은 1점으로만 센다
    write_cache(tmp_path, monkeypatch, cards=[card('탐', '1', '발신 승인 규칙', '승인 컨펌 허가')])
    res = recall.query('허락 규칙')
    assert [c['no'] for c in res['cards']] == ['1']
    assert res['ranked'][0][0] == 'cards'
    monkeypatch.setenv('RECALL_OFF', 'syn')
    assert recall.query('허락 규칙')['cards'] == []  # 동의어 없이는 '규칙' 하나만 맞아 기준(2개) 미달


# ---------- 3. 낡은 항목 강등 ----------
def test_stale_mark_detection():
    assert recall.stale_mark('[대체됨 10/10 지시] 옛 규칙')
    assert recall.stale_mark('(폐기) 옛 방식')
    assert not recall.stale_mark('[정정] 현행 규칙')
    assert not recall.stale_mark('대체됨이라는 말이 본문 가운데 있는 제목')


def test_stale_card_hidden_by_default_but_shown_in_history(tmp_path, monkeypatch):
    write_cache(tmp_path, monkeypatch, cards=[card('핏', '1', '[대체됨] 자막 위치 하단 고정', '자막 위치 하단'),
                                              card('핏', '2', '자막 위치 중앙 고정', '자막 위치 중앙')])
    assert [c['no'] for c in recall.query('자막 위치 고정')['cards']] == ['2']
    assert {c['no'] for c in recall.query('자막 위치 고정', history=True)['cards']} == {'1', '2'}


def test_stale_doc_section_hidden(tmp_path, monkeypatch):
    docs = [{'f': 'docs/a.md', 'h': '(폐기) 옛 배포 절차', 'd': '배포 절차 실행기 순서'},
            {'f': 'docs/a.md', 'h': '배포 절차', 'd': '배포 절차 실행기 순서'}]
    write_cache(tmp_path, monkeypatch, docs=docs)
    assert [d['h'] for d in recall.query('배포 절차 실행기 순서')['docs']] == ['배포 절차']


# ---------- 4. 순위: 정본 문서 슬롯 ----------
def test_merge_ranked_guarantees_doc_slot():
    layers = {'cards': [(1.0, 'c%d' % i) for i in range(5)], 'boss': [(0.9, 'b%d' % i) for i in range(3)],
              'docs': [(0.5, 'd0'), (0.4, 'd1')]}
    out = recall.merge_ranked(layers)
    kinds = [k for k, _ in out]
    assert 'docs' in kinds[:3]
    assert kinds[:3].count('docs') == 1  # 상위 3개 안에는 문서 한 자리만
    assert len(out) <= 10


def test_merge_ranked_orders_by_hit_ratio():
    layers = {'eps': [(0.2, 'e')], 'cards': [(0.8, 'c')]}
    assert [k for k, _ in recall.merge_ranked(layers, doc_slot=0)] == ['cards', 'eps']


def test_rank_switch_off_keeps_layer_order(tmp_path, monkeypatch):
    monkeypatch.setenv('RECALL_OFF', 'rank')
    write_cache(tmp_path, monkeypatch, cards=[card('탐', '1', '배포 실행기 순서', '배포 실행기')],
                docs=[{'f': 'docs/a.md', 'h': '배포 실행기 순서', 'd': '배포 실행기 순서 설명'}])
    kinds = [k for k, _ in recall.query('배포 실행기 순서')['ranked']]
    assert kinds == sorted(kinds, key=recall.LAYER_ORDER.index)


# ---------- 5. 캐시 신선도 ----------
def test_cache_age_and_note():
    now = time.mktime(time.strptime('2026-10-21 12:00:00', '%Y-%m-%d %H:%M:%S'))
    assert recall.cache_age_h('2026-10-21 08:00:00', now=now) == pytest.approx(4.0)
    assert recall.cache_age_h('엉뚱한 값') is None
    assert recall.cache_note({'cache_age_h': 1.0, 'cache_at': 'x'}) == ''
    assert '4시간 전' in recall.cache_note({'cache_age_h': 4.0, 'cache_at': '2026-10-21 08:00:00'})


def test_render_puts_cache_note_on_top():
    res = {'cache_age_h': 5.0, 'cache_at': '2026-10-21 07:00:00', 'ranked': [('cards', card('탐', '1', '제목'))]}
    lines = recall.render(res)
    assert lines[0].startswith('· 캐시가') and '공정 카드 [탐#1]' in lines[1]


def test_refresh_skipped_when_fresh_or_locked(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(recall.subprocess, 'Popen', lambda *a, **k: calls.append(a))
    lock = tmp_path / 'x.building'
    assert recall.refresh_in_background({'cache_age_h': 0.1}, lock=lock) is False
    lock.write_text('now', encoding='utf-8')
    assert recall.refresh_in_background({'cache_age_h': 2.0}, lock=lock) is False
    assert calls == []
    lock.unlink()
    assert recall.refresh_in_background({'cache_age_h': 2.0}, lock=lock) is True
    assert len(calls) == 1 and lock.exists()


# ---------- 6. 지식DB 층 오류를 삼키지 않는다 ----------
def test_kb_layer_error_is_reported(monkeypatch):
    class FakeOps:
        @staticmethod
        def rpc(name, params):
            raise RuntimeError('HTTP 404 {"code":"PGRST202","message":"질의 원문이 섞인 본문"}')
    monkeypatch.setitem(sys.modules, 'opsdb', FakeOps)
    monkeypatch.setattr(recall, '_embed', lambda text: None)
    assert recall.kb_layer('아무 질문') == []
    note = recall.kb_error_note()
    assert note.startswith('· 지식DB 층 오류:')
    assert 'HTTP 404' in note and 'PGRST202' in note and 'kb_search' in note
    assert '질의 원문' not in note  # 오류 본문은 옮기지 않는다


def test_kb_layer_systemexit_does_not_escape(monkeypatch):
    class FakeOps:
        @staticmethod
        def rpc(name, params):
            raise SystemExit('설정 없음')
    monkeypatch.setitem(sys.modules, 'opsdb', FakeOps)
    monkeypatch.setattr(recall, '_embed', lambda text: None)
    assert recall.kb_layer('아무 질문') == []
    assert '운영 DB 설정 없음' in recall.kb_error_note()


def test_kb_layer_success_clears_error(monkeypatch):
    class FakeOps:
        @staticmethod
        def rpc(name, params):
            return [{'src': 'x'}]
    monkeypatch.setitem(sys.modules, 'opsdb', FakeOps)
    monkeypatch.setattr(recall, '_embed', lambda text: None)
    recall.KB_ERR = '옛 오류'
    assert recall.kb_layer('아무 질문') == [{'src': 'x'}]
    assert recall.kb_error_note() == ''


# ---------- 7. 출력 가림 ----------
def test_mask_email_phone_key():
    outside = 'kim.boss' + AT + 'gmail.com'
    company = 'tam' + AT + 'simplifier.co.kr'
    image = 'logo' + AT + '2x.png'
    jwt = 'ey' + 'J' + 'a' * 12 + '.' + 'b' * 12 + '.' + 'c' * 12
    s = f'연락 {outside} / 공용 {company} / 그림 {image} / 전화 010-1234-5678 / 키 {jwt}'
    out = recall.mask_pii(s)
    assert outside not in out and 'k***' + AT + 'gmail.com' in out
    assert company in out and image in out
    assert '1234-5678' not in out and '010-****-****' in out
    assert jwt not in out and '[키 가림]' in out


def test_render_masks_but_cache_untouched(tmp_path, monkeypatch):
    outside = 'someone' + AT + 'naver.com'
    path = write_cache(tmp_path, monkeypatch, boss=[{'at': '2026-10-20 10:00:00', 'w': '탐', 'x': f'메일 주소 정리 규칙 {outside} 메일 주소 정리'}])
    res = recall.query('메일 주소 정리 규칙')
    lines = recall.render(res)
    assert lines and all(outside not in x for x in lines)
    assert outside in path.read_text(encoding='utf-8')


def test_mask_switch_off(monkeypatch):
    monkeypatch.setenv('RECALL_OFF', 'mask')
    outside = 'someone' + AT + 'naver.com'
    assert recall.mask_pii(outside) == outside
