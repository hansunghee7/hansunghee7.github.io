#!/usr/bin/env python3
"""collection_check.py 단위시험. 순수 함수 check_history를 검증한다.

실행: python scripts/test_collection_check.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ops"))

from collection_check import check_history, is_velocity_field  # noqa: E402

_fails = []


def check(name, cond):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}")
        _fails.append(name)


def kinds(warnings):
    return sorted(w["kind"] for w in warnings)


# 1) 빈 값 회귀: 직전 non-null → 최신 null 이면 null_regression 경고.
def test_null_regression():
    history = [
        {"date": "2026-01-01", "yes24": {"sales_index": 600, "reviews": 3}},
        {"date": "2026-01-02", "yes24": {"sales_index": None, "reviews": 3}},
    ]
    w = check_history(history)
    check("빈값회귀 감지", "null_regression" in kinds(w) and len(w) == 1)
    check("빈값회귀 필드 식별", w[0]["source"] == "yes24" and w[0]["field"] == "sales_index")


# 2) 급변: 판매지수가 임계(70%) 넘게 변하면 spike 경고.
def test_spike_detected():
    history = [
        {"date": "2026-01-01", "aladin": {"sales_point": 100}},
        {"date": "2026-01-02", "aladin": {"sales_point": 500}},  # +400%
    ]
    w = check_history(history)
    check("급변 감지(sales_point)", kinds(w) == ["spike"])
    # *_rank 계열도 급변 대상.
    h2 = [
        {"date": "2026-01-01", "millie": {"category_rank": 10}},
        {"date": "2026-01-02", "millie": {"category_rank": 90}},  # +800%
    ]
    check("급변 감지(category_rank)", kinds(check_history(h2)) == ["spike"])


# 2-b) 순위 결함(비티·덱스 교차검증): *_rank은 비율이 아니라 절대 순위 차이로 판정.
def test_rank_spike_uses_absolute_jump():
    # ① 최상위권 소폭 변동(1→2)은 비율로는 100%지만 절대차 1계단이라 spike 아님.
    h_top = [
        {"date": "2026-01-01", "yes24": {"category_rank": 1}},
        {"date": "2026-01-02", "yes24": {"category_rank": 2}},
    ]
    check("순위 1→2는 급변 아님(절대차 1계단)", check_history(h_top) == [])
    # 2→4도 비율 100%지만 2계단이라 무경고.
    h_top2 = [
        {"date": "2026-01-01", "yes24": {"category_rank": 2}},
        {"date": "2026-01-02", "yes24": {"category_rank": 4}},
    ]
    check("순위 2→4는 급변 아님(절대차 2계단)", check_history(h_top2) == [])
    # ② 큰 계단(5→300)은 spike, detail에 '계단' 표기.
    h_big = [
        {"date": "2026-01-01", "millie": {"category_rank": 5}},
        {"date": "2026-01-02", "millie": {"category_rank": 300}},
    ]
    w_big = check_history(h_big)
    check("순위 5→300은 급변", kinds(w_big) == ["spike"])
    check("순위 급변 detail에 계단 표기", "계단" in w_big[0]["detail"])
    # --rank-jump 인자로 임계 조정 가능(기본 50 → 400이면 5→300=295계단은 통과).
    check("rank_jump 인자 반영(400이면 무경고)", check_history(h_big, rank_jump=400) == [])


# 2-c) 판매 계열(sales_point)은 여전히 비율로 판정(절대차 임계 영향 안 받음).
def test_sales_still_ratio():
    # 100→500 = +400% > 70% → spike. rank_jump를 크게 줘도 비율이라 여전히 급변.
    h = [
        {"date": "2026-01-01", "aladin": {"sales_point": 100}},
        {"date": "2026-01-02", "aladin": {"sales_point": 500}},
    ]
    check("sales_point 비율 급변", kinds(check_history(h, rank_jump=9999)) == ["spike"])
    check("sales_point detail에 % 표기", "%" in check_history(h)[0]["detail"])
    # 소폭(100→150=+50%)은 무경고.
    h2 = [
        {"date": "2026-01-01", "aladin": {"sales_point": 100}},
        {"date": "2026-01-02", "aladin": {"sales_point": 150}},
    ]
    check("sales_point 소폭 무경고", check_history(h2) == [])


# 3) 소폭 변동은 경고 없음(임계 이하).
def test_small_change_no_spike():
    history = [
        {"date": "2026-01-01", "yes24": {"sales_index": 600}},
        {"date": "2026-01-02", "yes24": {"sales_index": 660}},  # +10%
    ]
    check("소폭 변동 무경고", check_history(history) == [])


# 4) 리뷰·평점은 급변 대상에서 제외.
def test_reviews_rating_excluded():
    history = [
        {"date": "2026-01-01", "yes24": {"reviews": 3, "rating": 10.0}},
        {"date": "2026-01-02", "yes24": {"reviews": 30, "rating": 1.0}},  # 리뷰 10배, 평점 급락
    ]
    check("리뷰·평점 급변 제외", check_history(history) == [])
    check("is_velocity_field: reviews 아님", not is_velocity_field("reviews"))
    check("is_velocity_field: rating 아님", not is_velocity_field("rating"))
    check("is_velocity_field: sales_index 맞음", is_velocity_field("sales_index"))
    check("is_velocity_field: *_rank 맞음", is_velocity_field("category_rank"))


# 5) 0은 실제 값 — null로 취급하지 않고, 직전 0이면 비율 계산 건너뜀(무경고).
def test_zero_is_valid():
    # 직전 0 → 최신 5: 비율 계산 불가(division 회피)로 급변 경고 없음.
    h1 = [
        {"date": "2026-01-01", "ridibooks": {"rating_count": 0}},
        {"date": "2026-01-02", "ridibooks": {"rating_count": 5}},
    ]
    check("직전 0은 급변 계산 제외", check_history(h1) == [])
    # 최신이 0(=실제 값)이고 직전이 non-null이면 null_regression 아님.
    h2 = [
        {"date": "2026-01-01", "millie": {"category_rank": 44}},
        {"date": "2026-01-02", "millie": {"category_rank": 0}},
    ]
    # 44 → 0 은 100% 변동이므로 spike이되 null_regression은 아님.
    w2 = check_history(h2)
    check("최신 0은 빈값회귀 아님", "null_regression" not in kinds(w2))


# 6) 최신 레코드 누락 소스 감지.
def test_missing_source():
    history = [
        {"date": "2026-01-01", "yes24": {"sales_index": 600}, "millie": {"category_rank": 44}},
        {"date": "2026-01-02", "yes24": {"sales_index": 600}},  # millie 빠짐
    ]
    w = check_history(history)
    check("누락 소스 감지", kinds(w) == ["missing_source"])
    check("누락 소스 이름", w[0]["source"] == "millie")


# 7) 경고 없음 = 깨끗.
def test_clean():
    history = [
        {"date": "2026-01-01", "yes24": {"sales_index": 600, "reviews": 3}},
        {"date": "2026-01-02", "yes24": {"sales_index": 610, "reviews": 3}},
    ]
    check("깨끗한 데이터 무경고", check_history(history) == [])


# 8) 빈 history / 단일 레코드 안전.
def test_empty_and_single():
    check("빈 history 안전", check_history([]) == [])
    check("단일 레코드 안전", check_history([{"date": "2026-01-01", "yes24": {"sales_index": 600}}]) == [])
    # 소스가 dict→None(통째로 사라짐)이면 크래시 없이 수집 실패로 보고 누락 경고.
    w = check_history([
        {"date": "2026-01-01", "yes24": {"sales_index": 600}},
        {"date": "2026-01-02", "yes24": None},
    ])
    check("None 소스 값 안전(누락 경고)", kinds(w) == ["missing_source"])


if __name__ == "__main__":
    for fn in [
        test_null_regression,
        test_spike_detected,
        test_rank_spike_uses_absolute_jump,
        test_sales_still_ratio,
        test_small_change_no_spike,
        test_reviews_rating_excluded,
        test_zero_is_valid,
        test_missing_source,
        test_clean,
        test_empty_and_single,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print()
    if _fails:
        print(f"실패 {len(_fails)}건: {_fails}")
        sys.exit(1)
    print("모든 단위시험 통과")
    sys.exit(0)
