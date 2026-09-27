#!/usr/bin/env python3
"""탐_업무대장.md·클라우드탐_업무대장.md가 공유하는 N번호가 중복 사용됐는지 검사한다.

왜 이 검사가 있나
-----------------
두 문서 다 "새 번호를 매기기 전에 양쪽 표의 마지막 번호를 확인하라"고
문서에 적어뒀는데도 2026-09-27 하루에 N50, N54 두 번이나 서로 다른
세션이 같은 번호를 독립적으로 썼다. 문서로 적어둔 규칙은 세션이 매번
새로 시작하는 구조에서 반복해서 안 지켜진다 -- CLAUDE.md "반복 업무
규칙은 문서보다 도구 관문에" 원칙을 이 사고에 그대로 적용한다.

무엇을 잡나
-----------
각 표의 "| N<번호> | <안건> | ..." 형태 행(열린 항목·닫힌 항목 구분 없이)을
전부 모아, 같은 번호가 두 문서 어느 쪽에서든 두 번 이상 나오면 살펴본다.
본문 중 "N42 끝났으니"처럼 다른 문장 안에서 번호를 언급하는 것은 행 정의가
아니라 세지 않는다.

이관(로컬탐 ↔ 클라우드탐)된 같은 안건은 양쪽 표에 같은 번호로 각자
기록하는 게 정상이다(예: N59 방치 PR 이관) -- 이건 충돌이 아니다. "안건"
칸 텍스트가 겹치는 단어가 거의 없을 때만(전혀 다른 안건) 진짜 충돌로
본다.

사용법: python scripts/check_n_collisions.py
"""
import re
import sys

# Windows 콘솔(cp949 등)에서 직접 실행하면 이모지·줄표(—) 출력이
# UnicodeEncodeError로 죽는다(2026-09-27 N66 실측 중 발견). CI(Ubuntu,
# LANG=C.UTF-8)는 원래 문제없었지만, 로컬에서도 결과를 볼 수 있게
# stdout을 UTF-8로 강제한다(표시 안 되는 글자는 깨진 문자로 대체할 뿐
# 죽지 않는다).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGERS = ["docs/탐_업무대장.md", "docs/클라우드탐_업무대장.md"]
ROW = re.compile(r"^\|\s*N(\d+)\s*\|\s*([^|]*)\|")
TOKEN = re.compile(r"[#]?[0-9A-Za-z가-힣]{2,}")
SIMILARITY_THRESHOLD = 0.12


def rows(path):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return []
    found = []
    for line_no, line in enumerate(text.splitlines(), 1):
        m = ROW.match(line)
        if m:
            found.append((int(m.group(1)), line_no, m.group(2).strip()))
    return found


def similar(text_a, text_b):
    a, b = set(TOKEN.findall(text_a.lower())), set(TOKEN.findall(text_b.lower()))
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= SIMILARITY_THRESHOLD


def main():
    seen = {}  # 번호 -> [(파일, 줄번호, 안건), ...]
    for path in LEDGERS:
        for n, line_no, title in rows(path):
            seen.setdefault(n, []).append((path, line_no, title))

    duplicated = {n: locs for n, locs in seen.items() if len(locs) > 1}
    collisions, mirrors = {}, {}
    for n, locs in duplicated.items():
        titles = [t for _, _, t in locs]
        is_mirror = all(similar(titles[0], t) for t in titles[1:])
        (mirrors if is_mirror else collisions)[n] = locs

    if mirrors:
        print(f"같은 안건을 양쪽에 기록한 정상 이관 {len(mirrors)}건 (충돌 아님): "
              f"{', '.join(f'N{n}' for n in sorted(mirrors))}")

    if not collisions:
        print(f"N번호 충돌 없음 ({sum(len(v) for v in seen.values())}행 검사).")
        return 0

    print(f"\nN번호 충돌을 발견했습니다 ({len(collisions)}건, 서로 다른 안건이 같은 번호를 씀):\n")
    for n in sorted(collisions):
        print(f"  N{n}:")
        for path, line_no, title in collisions[n]:
            print(f"    {path}:{line_no}  {title[:60]}")

    print(
        "\n"
        "탐_업무대장.md·클라우드탐_업무대장.md는 N번호를 공유합니다.\n"
        "새 번호는 python scripts/ops/next_n.py로 발급받아 쓰세요\n"
        "(둘 중 하나를 재번호해서 겹치지 않게 고친 뒤 다시 push)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
