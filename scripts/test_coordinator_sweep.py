# -*- coding: utf-8 -*-
"""coordinator_sweep 순수 함수 단위시험. 실행: python scripts/test_coordinator_sweep.py

DB에 붙지 않는다(순수 함수만). 통과하면 'ALL PASS N tests', 실패하면 AssertionError."""
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'ops'))
import coordinator_sweep as cs  # noqa: E402

TODAY = _dt.date(2026, 10, 18)
_tests = []


def test(fn):
    _tests.append(fn)
    return fn


@test
def t_dup_exact_different_no():
    # 같은 제목, 번호가 다른 두 작업 → 중복 1묶음.
    items = [
        {'no': 'N10', 'title': '**롱폼 3관문 운영**(사장님 10/5)', 'owner': '핏'},
        {'no': 'N20', 'title': '롱폼 3관문 운영 (지투 10/6: 다른 주석)', 'owner': '지투'},
        {'no': 'N30', 'title': '전혀 다른 숏폼 추출 실험', 'owner': '마야'},
    ]
    groups = cs.find_duplicate_groups(items, threshold=0.85)
    assert len(groups) == 1, groups
    assert {m['no'] for m in groups[0]} == {'N10', 'N20'}, groups


@test
def t_dup_same_no_not_grouped():
    # 같은 번호(no)는 같은 작업이므로 중복으로 묶지 않는다.
    items = [
        {'no': 'N10', 'title': '롱폼 3관문 운영', 'owner': '핏'},
        {'no': 'N10', 'title': '롱폼 3관문 운영', 'owner': '핏'},
    ]
    assert cs.find_duplicate_groups(items, threshold=0.85) == []


@test
def t_dup_distinct_titles_none():
    items = [
        {'no': 'N1', 'title': '유튜브 등록 설정 리서치', 'owner': '핏'},
        {'no': 'N2', 'title': '인스타 광고 수익 구조 리서치', 'owner': '마야'},
        {'no': 'N3', 'title': '카빗 패스 PIN 폐지 구현', 'owner': '탐'},
    ]
    assert cs.find_duplicate_groups(items, threshold=0.85) == []


@test
def t_unassigned():
    assert cs.is_unassigned('') is True
    assert cs.is_unassigned(None) is True
    assert cs.is_unassigned('미정') is True
    assert cs.is_unassigned('미상') is True
    assert cs.is_unassigned(' 탐 ') is False
    assert cs.is_unassigned('핏') is False


@test
def t_resolved_status():
    assert cs.is_resolved_status('완료') is True
    assert cs.is_resolved_status('완료(대체 경로)') is True
    assert cs.is_resolved_status('병합→N116') is True
    assert cs.is_resolved_status('이관') is True
    assert cs.is_resolved_status('진행') is False
    assert cs.is_resolved_status('대기') is False
    assert cs.is_resolved_status('사장님') is False


@test
def t_stale_boundary():
    # 경계값: 정확히 3일 → 정체(True), 2일 → 아님.
    assert cs.is_stale(_dt.date(2026, 10, 15), TODAY, days=3) is True   # 3일
    assert cs.is_stale(_dt.date(2026, 10, 16), TODAY, days=3) is False  # 2일
    assert cs.is_stale(_dt.date(2026, 10, 14), TODAY, days=3) is True   # 4일
    assert cs.is_stale(None, TODAY, days=3) is False
    assert cs.is_stale(_dt.date(2026, 10, 18), TODAY, days=3) is False  # 오늘


@test
def t_extract_latest_date():
    # source_date 'M/D'에서 날짜를 뽑고, 여러 개면 가장 최근 과거를 고른다.
    assert cs.extract_latest_date(['사장님 10/3'], TODAY) == _dt.date(2026, 10, 3)
    assert cs.extract_latest_date(['사장님 10/3', '핏 10/12'], TODAY) == _dt.date(2026, 10, 12)
    # YYYY-MM-DD 혼재.
    assert cs.extract_latest_date(['상태 2026-10-10', '사장님 9/30'], TODAY) == _dt.date(2026, 10, 10)
    # 오늘보다 미래인 12/25는 작년으로 돌려 과거가 된다.
    assert cs.extract_latest_date(['12/25'], TODAY) == _dt.date(2025, 12, 25)
    # 날짜 없음.
    assert cs.extract_latest_date(['안건 설명만 있음', None], TODAY) is None


@test
def t_stale_integration_via_extract():
    # 10/3이 마지막이면 오늘(10/18) 기준 정체.
    last = cs.extract_latest_date(['사장님 10/3'], TODAY)
    assert cs.is_stale(last, TODAY, days=3) is True
    # 10/17이 마지막이면 1일 전 → 정체 아님.
    last2 = cs.extract_latest_date(['핏 10/17'], TODAY)
    assert cs.is_stale(last2, TODAY, days=3) is False


def run():
    passed = 0
    for fn in _tests:
        fn()
        passed += 1
        print('PASS', fn.__name__)
    print('ALL PASS %d tests' % passed)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    run()
