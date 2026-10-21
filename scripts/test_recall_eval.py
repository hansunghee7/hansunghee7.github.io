#!/usr/bin/env python3
"""recall_eval.py 채점 로직 단위시험(외부 접속 없음: 가짜 recall 결과·가짜 표시로만).

키처럼 보이는 문자열은 런타임에 조각을 이어 붙여 만든다(공개 저장소 유출 검사 오탐 방지).
"""
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, 'ops')):
    if p not in sys.path:
        sys.path.insert(0, p)

import recall_eval as ev  # noqa: E402

FLAGS = {'ok': True, 'hidden_cards': {'핏#4'}, 'superseded_boss': {'2026-10-14 10:47:31'}, 'note': ''}


def fake_res():
    return {
        'eps': [],
        'grants': [{'no': 'G18', 't': '구글 프로그램', 'st': '탈락', 'memo': '', 'next': ''}],
        'cards': [{'p': '핏', 'no': '4', 't': '쇼츠 자막 위치', 'd': '', 'b': ''},
                  {'p': '핏-영상생성', 'no': '40', 't': '[대체됨 10/10 지시] 크레딧 없음 휴식', 'd': '', 'b': ''},
                  {'p': '핏-조립', 'no': '36', 't': '자막 60% 롤백', 'd': '', 'b': ''}],
        'boss': [{'at': '2026-10-14 10:47:31', 'w': '핏', 'x': '옛 결정'}],
        'docs': [{'f': 'docs/슈퍼색인관리.md', 'h': '찾는 순서', 'd': '1차 2차'}],
        'logs': [], 'q': ['자막'],
    }


class FakeRecall:
    def __init__(self, res, kb=None):
        self.res, self.kb, self.kb_calls = res, kb or [], 0

    def query(self, text, history=False):
        return self.res

    def kb_layer(self, text):
        self.kb_calls += 1
        return self.kb


def test_rank_order_follows_render():
    items = ev.rank_items(fake_res(), [{'src': 'fact', 'ref_id': 'r1', 'title': 't', 'content': 'c', 'fact_state': 'current'}])
    assert [i['id'] for i in items] == ['지원현황#G18', '핏#4', '핏-영상생성#40', '핏-조립#36', '사장님말#2026-10-14 10:47:31',
                                        'docs/슈퍼색인관리.md', 'kb:fact:r1']


def test_rank_items_handles_none():
    assert ev.rank_items(None, None) == []


def test_flags_hidden_bracket_superseded_kb_mustnot():
    items = ev.rank_items(fake_res(), [{'src': 'fact', 'ref_id': 'old', 'title': '', 'content': '', 'fact_state': 'stale'}])
    by = {i['id']: ev.item_flags(i, FLAGS, {'docs/슈퍼색인관리.md'}) for i in items}
    assert by['핏#4'] == ['카드 상태 숨김']
    assert by['핏-영상생성#40'] and '제목 앞 표시' in by['핏-영상생성#40'][0]
    assert by['핏-조립#36'] == []
    assert by['사장님말#2026-10-14 10:47:31'] == ['결정 superseded_by']
    assert by['kb:fact:old'] == ['지식DB fact_state=stale']
    assert by['docs/슈퍼색인관리.md'] == ['질문 지정 대체 항목(must_not)']
    assert by['지원현황#G18'] == []


def test_bracket_without_stale_word_not_flagged():
    it = {'kind': 'card', 'id': 'x#1', 'text': '[정본 개정 10/14] 바로 생산'}
    assert ev.item_flags(it, FLAGS) == []
    it2 = {'kind': 'card', 'id': 'x#2', 'text': '관련 동영상 유도 폐기'}  # 제목 앞 [..]이 아니면 현행 결정일 수 있다
    assert ev.item_flags(it2, FLAGS) == []


def test_score_hit_within_top3():
    items = ev.rank_items(fake_res(), [])
    r = ev.score_question({'id': 'Q', 'category': 'c', 'question': 'q', 'expected': ['핏-조립#36']}, items, FLAGS)
    assert r['rank'] == 4 and r['hit_top3'] is False and r['passed'] is False
    assert len(r['mixed_top5']) == 3  # 숨김 카드, 대체됨 제목, superseded 결정
    r2 = ev.score_question({'id': 'Q', 'category': 'c', 'question': 'q', 'expected': ['핏#4', '지원현황#G18']}, items, FLAGS)
    assert r2['rank'] == 1 and r2['hit_top3'] and r2['passed']


def test_score_kb_partial_match_and_missing():
    items = ev.rank_items({}, [{'src': 'doc', 'ref_id': 'docs/a.md#3', 'title': '', 'content': ''}])
    r = ev.score_question({'id': 'Q', 'expected': ['docs/a.md']}, items, FLAGS)
    assert r['rank'] == 1 and r['hit_top3']
    r2 = ev.score_question({'id': 'Q', 'expected': ['docs/b.md']}, items, FLAGS)
    assert r2['rank'] is None and not r2['passed']


def test_privacy_question_passes_without_leak_and_fails_with_leak():
    clean = ev.rank_items({'cards': [{'p': '탐', 'no': '1', 't': '연락처는 비공개 저장소에', 'd': '', 'b': ''}]}, [])
    assert ev.score_question({'id': 'E', 'expected': []}, clean, FLAGS)['passed'] is True
    phone = '010' + '-1234-' + '5678'
    leaky = ev.rank_items({'cards': [{'p': '탐', 'no': '2', 't': f'담당 {phone}', 'd': '', 'b': ''}]}, [])
    r = ev.score_question({'id': 'E', 'expected': []}, leaky, FLAGS)
    assert r['passed'] is False and r['leaks_top5'][0]['kinds'] == ['휴대전화']
    assert phone not in json.dumps(r, ensure_ascii=False)  # 결과 파일에 값이 남지 않는다


def test_leak_hits_email_allowlist_and_key():
    assert ev.leak_hits('문의 someone@simplifier.co.kr') == []
    assert ev.leak_hits('문의 person@customer-example.net') == ['이메일']
    fake_key = 'sb_' + 'secret_' + 'A' * 24
    assert '수파베이스 비밀키' in ev.leak_hits(f'키 {fake_key}')
    assert fake_key not in ev.mask_text(f'키 {fake_key}')


def test_collect_uses_recall_path_and_kb_toggle():
    fr = FakeRecall(fake_res(), [{'src': 'f', 'ref_id': '1', 'title': '', 'content': ''}])
    items, timing, err = ev.collect('질문', use_kb=True, recall_mod=fr)
    assert err == '' and items[-1]['id'] == 'kb:f:1' and fr.kb_calls == 1
    assert set(timing) == {'query_ms', 'kb_ms', 'total_ms'}
    items2, _, _ = ev.collect('질문', use_kb=False, recall_mod=fr)
    assert fr.kb_calls == 1 and items2[-1]['kind'] == 'doc'
    _, _, err3 = ev.collect('질문', use_kb=False, recall_mod=FakeRecall(None))
    assert '캐시 없음' in err3


def test_summarize_counts():
    items = ev.rank_items(fake_res(), [])
    rs = [ev.score_question({'id': 'A', 'category': '가', 'expected': ['지원현황#G18']}, items, FLAGS),
          ev.score_question({'id': 'B', 'category': '가', 'expected': ['없는#1']}, items, FLAGS),
          ev.score_question({'id': 'C', 'category': '나', 'expected': []}, [], FLAGS)]
    for r, ms in zip(rs, (10, 30, 20)):
        r['timing'] = {'total_ms': ms}
    s = ev.summarize(rs)
    assert (s['n'], s['passed'], s['hit_top3'], s['n_with_expected'], s['found_anywhere']) == (3, 2, 1, 2, 1)
    assert s['mixed_items'] == 6 and s['mixed_questions'] == 2 and s['median_ms'] == 20 and s['max_ms'] == 30
    assert s['by_category'] == {'가': {'n': 2, 'passed': 1}, '나': {'n': 1, 'passed': 1}}


def test_annotate_writes_reasons(tmp_path):
    items = ev.rank_items(fake_res(), [])
    r = ev.score_question({'id': 'B', 'category': '가', 'question': 'q', 'expected': ['없는#1']}, items, FLAGS)
    r['timing'] = {'total_ms': 1}
    meta = {'label': 't', 'date': 'd', 'questions': 'q.json', 'cache_at': 'x', 'use_kb': False, 'flags_note': ''}
    p = tmp_path / 'd_t.json'
    p.write_text(json.dumps({'meta': meta, 'summary': ev.summarize([r]), 'results': [r]}, ensure_ascii=False), encoding='utf-8')
    rp = tmp_path / 'reasons.json'
    rp.write_text(json.dumps({'B': '키워드 불일치'}, ensure_ascii=False), encoding='utf-8')
    ev.annotate(p, rp)
    assert '실패 원인: 키워드 불일치' in Path(p.with_suffix('.md')).read_text(encoding='utf-8')
