#!/usr/bin/env python3
"""탐_업무대장.md·클라우드탐_업무대장.md가 공유하는 다음 N번호를 알려준다.

이 스크립트는 origin/main의 최신 상태를 직접 읽는다(로컬 체크아웃이
낡았을 수 있어서). 두 문서 다 확인하지 않고 한쪽만 보고 번호를 매겨
2026-09-27에 두 번 충돌(N50, N54)이 났던 게 이 스크립트가 막으려는
사고다.

한계: 이 스크립트를 돌린 뒤 실제로 그 번호를 커밋·push하기 전까지는
여전히 짧은 race window가 있다(진짜 동시 실행이면 같은 번호를 받을 수
있음). 그 최종 방어선은 scripts/check_n_collisions.py(build-check에서
자동 실행) -- 번호가 겹치면 병합 전에 잡힌다.

사용법: python scripts/ops/next_n.py
"""
import re
import subprocess
import sys

LEDGERS = ["docs/탐_업무대장.md", "docs/클라우드탐_업무대장.md"]


def latest_ledger_text(path):
    return subprocess.run(
        ["git", "show", f"origin/main:{path}"],
        capture_output=True, text=True, check=True,
    ).stdout


def main():
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], check=True)

    max_n = 0
    for path in LEDGERS:
        text = latest_ledger_text(path)
        for m in re.finditer(r"\bN(\d+)\b", text):
            max_n = max(max_n, int(m.group(1)))

    next_n = max_n + 1
    print(f"N{next_n}")
    print(
        f"(origin/main 기준 최댓값 N{max_n}, 스캔: {', '.join(LEDGERS)}. "
        "행을 넣은 뒤 바로 커밋·push할 것 -- 오래 들고 있을수록 충돌 위험 커짐)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
