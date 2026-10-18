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
def t_recurring_template_not_dup():
    # 날짜·회차만 다른 반복 업무 템플릿은 중복으로 보지 않는다.
    items = [
        {'no': 'N40', 'title': '[정기] 10월 1주차 수집', 'owner': '마야'},
        {'no': 'N41', 'title': '[정기] 10월 2주차 수집', 'owner': '마야'},
    ]
    assert cs.find_duplicate_groups(items, threshold=0.85) == []
    # is_recurring_variant 자체도 True.
    assert cs.is_recurring_variant('[정기] 10월 1주차 수집', '[정기] 10월 2주차 수집') is True


@test
def t_similar_non_numeric_diff_still_dup():
    # 숫자를 빼도 서로 다른 진짜 유사 제목(차이가 숫자가 아님)은 여전히 중복.
    items = [
        {'no': 'N50', 'title': '2026 유튜브 등록 설정 작업', 'owner': '핏'},
        {'no': 'N51', 'title': '2026 유튜브 등록 설정 정리', 'owner': '지투'},
    ]
    groups = cs.find_duplicate_groups(items, threshold=0.85)
    assert len(groups) == 1, groups
    assert {m['no'] for m in groups[0]} == {'N50', 'N51'}, groups
    # 숫자(2026)가 공통이어도 뼈대가 달라 반복 템플릿이 아니다.
    assert cs.is_recurring_variant('2026 유튜브 등록 설정 작업', '2026 유튜브 등록 설정 정리') is False


@test
def t_recurring_variant_identical_is_genuine_dup():
    # 숫자까지 완전히 같은 제목은 반복 변형이 아니라 진짜 복제 → is_recurring_variant False.
    assert cs.is_recurring_variant('롱폼 3관문 운영', '롱폼 3관문 운영') is False


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
def t_build_report_has_no_stale():
    # 정체 지표는 뺐다 — 보고에 stale 키가 없고 중복·미배정만 남는다.
    rows = [
        {'no': 'N1', 'title': '주인 없는 일', 'owner': '', 'status': '진행'},
        {'no': 'N2', 'title': '담당 있는 일', 'owner': '탐', 'status': '진행'},
    ]
    rep = cs.build_report(rows, TODAY)
    assert 'stale' not in rep and 'stale_days' not in rep, rep
    assert set(rep.keys()) >= {'duplicates', 'unassigned', 'open_task_count', 'date'}, rep
    assert len(rep['unassigned']) == 1 and rep['unassigned'][0]['no'] == 'N1', rep


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
