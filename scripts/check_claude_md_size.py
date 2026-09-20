#!/usr/bin/env python3
"""CLAUDE.md 줄 수 검사. 사장님 결정(2026-09-20): 상한 250줄(초과 PR은 병합 차단), 목표는 200줄 이하.

목표 200줄은 이 검사가 아니라 **격주 폴리싱**(docs/폴리싱_기록.md)으로 지킨다. 그 폴리싱이 실제로 도는지는 감시(scripts/ops)가
14일 주기로 확인한다. 이 검사가 있는 이유: 200줄 목표가 문서에만 있을 때 CLAUDE.md는 3.5주 만에 45줄에서 604줄이 됐다.
한계: 사장님 본인의 직접 커밋과 자동화는 병합 규칙을 우회하므로 이 검사가 못 잡는다(그 경우는 감시가 줄 수로 잡는다).
"""
import os
import sys

WARN, LIMIT = 200, 250


def main():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "CLAUDE.md")
    n = len(open(path, encoding="utf-8").read().splitlines())
    if n > LIMIT:
        print(f"::error file=CLAUDE.md::CLAUDE.md가 {n}줄로 상한 {LIMIT}줄을 넘었습니다. 넣으려면 같은 PR에서 스킬, rule, docs로 옮겨 줄이세요(절차: docs/폴리싱_기록.md).")
        return 1
    if n > WARN:
        print(f"::warning file=CLAUDE.md::CLAUDE.md가 {n}줄로 목표 {WARN}줄을 넘었습니다(상한 {LIMIT}줄). 격주 폴리싱 때 줄이세요.")
    else:
        print(f"CLAUDE.md {n}줄(목표 {WARN}, 상한 {LIMIT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
