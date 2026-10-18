#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""human_touch_reclassify의 순수 분류 함수 단위시험.

실행: python scripts/test_human_touch_reclassify.py
표준 라이브러리만 사용. 실패 시 exit code 1.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ops"))

from human_touch_reclassify import (  # noqa: E402
    JUDGMENT_LABEL,
    RELAY_LABEL,
    UNSURE_LABEL,
    classify,
    filter_days,
    summarize,
)

CASES = []


def check(name, got, want):
    CASES.append((name, got == want, f"{name}: got={got!r} want={want!r}"))


# 1) 판단 카테고리는 '실제 판단'
check("제품결정→판단", classify("제품 결정", "v8을 올릴까요?")[0], JUDGMENT_LABEL)
check("방향결정→판단", classify("방향 결정", "")[0], JUDGMENT_LABEL)
check("비가역→판단", classify("비가역", "")[0], JUDGMENT_LABEL)
check("돈→판단", classify("돈", "")[0], JUDGMENT_LABEL)

# 2) 전달 카테고리는 '분류·전달만' (자동화 후보)
check("자격증명→전달", classify("자격증명", "")[0], RELAY_LABEL)
check("외부발신→전달", classify("외부 발신", "")[0], RELAY_LABEL)
check("계정생성→전달", classify("계정 생성", "")[0], RELAY_LABEL)

# 3) 모호한 '규칙상 금지'는 키워드 없으면 '미분류'
check("규칙상금지_무키워드→미분류", classify("규칙상 금지", "")[0], UNSURE_LABEL)
# 3b) 본문에 전달 키워드 있으면 '분류·전달만'로 이동
check(
    "규칙상금지_발신키워드→전달",
    classify("규칙상 금지", "메일을 외부로 전송해야 합니다")[0],
    RELAY_LABEL,
)
# 3c) 본문에 판단 키워드 있으면 '실제 판단'로 이동
check(
    "규칙상금지_승인키워드→판단",
    classify("규칙상 금지", "이대로 승인하시겠어요?")[0],
    JUDGMENT_LABEL,
)

# 4) 알 수 없는 사유 + 빈 본문은 안전하게 '미분류'
check("미지사유→미분류", classify("처음보는사유", "")[0], UNSURE_LABEL)
check("빈사유→미분류", classify("", "")[0], UNSURE_LABEL)
check("None안전", classify(None, None)[0], UNSURE_LABEL)

# 5) 빈 입력 안전: summarize/filter_days가 크래시하지 않음
empty = summarize([])
check("빈입력_total0", empty["total"], 0)
check("빈입력_카테고리없음", empty["by_category"], {})
check("filter_days_빈", filter_days([], 7), [])

# 6) 집계가 카테고리별로 올바로 분배되는지
sample = [
    {"t": "2026-10-18 00:00:00", "reason": "제품 결정", "line": "a"},
    {"t": "2026-10-18 00:00:00", "reason": "자격증명", "line": "b"},
    {"t": "2026-10-18 00:00:00", "reason": "자격증명", "line": "c"},
    {"t": "2026-10-18 00:00:00", "reason": "규칙상 금지", "line": ""},
]
s = summarize(sample)
check("집계_total4", s["total"], 4)
check("집계_판단1", s["by_category"].get(JUDGMENT_LABEL), 1)
check("집계_전달2", s["by_category"].get(RELAY_LABEL), 2)
check("집계_미분류1", s["by_category"].get(UNSURE_LABEL), 1)
check("집계_전달버킷_자격증명2", s["relay_buckets"]["자격증명"], 2)


def run():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    failed = [msg for _, ok, msg in CASES if not ok]
    passed = sum(1 for _, ok, _ in CASES if ok)
    for name, ok, msg in CASES:
        print(("PASS " if ok else "FAIL ") + name)
    print(f"\n{passed}/{len(CASES)} passed")
    if failed:
        print("\n".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
