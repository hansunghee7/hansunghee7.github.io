#!/usr/bin/env python3
"""교신방 README 관문(교신 규약 7번). 링크를 외부 사람에게 전달하기 전에 로컬 README 파일을 검사한다.

사용: python room_readme_gate.py <README 경로>
검사: ① 첫 40줄 안에 '하실 일' 제목 ② 그 아래 '분'과 단계 번호 ③ 에이전트에게 붙여 넣을 코드 블록
출력: 통과/실패 한 줄. 종료 코드 0 통과, 2 실패(파일 없음·읽기 불가 포함). 외부 호출 없음.
"""
import re
import sys

HEAD_LINES = 40


def check(text):
    """실패 사유 목록을 돌려준다(빈 목록이면 통과)."""
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines[:HEAD_LINES]) if l.lstrip().startswith("#") and "하실 일" in l), None)
    if idx is None:
        return [f"첫 {HEAD_LINES}줄 안에 '하실 일' 제목 없음"]
    rest = "\n".join(lines[idx + 1:])
    problems = []
    if not re.search(r"\d+\s*분", rest):
        problems.append("'하실 일' 아래에 소요 시간(예: 5분) 없음")
    if not re.search(r"(?m)^\s*(\d+[.)]|[1-9]단계|\d+\s*단계)", rest):
        problems.append("'하실 일' 아래에 단계 번호 없음")
    if not re.search(r"```[^\n]*\n\s*\S[\s\S]*?```", rest):
        problems.append("에이전트에게 붙여 넣을 문장 코드 블록 없음")
    return problems


def main(argv):
    if len(argv) != 2:
        print("실패: 사용법 room_readme_gate.py <README 경로>")
        return 2
    try:
        with open(argv[1], encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"실패: README 읽기 불가 ({e})")
        return 2
    problems = check(text)
    if problems:
        print("실패: " + "; ".join(problems) + " -> 링크 전달 전에 멈춘다(교신 규약 7번)")
        return 2
    print("통과: README 맨 위 '하실 일'(시간, 단계, 붙여 넣을 문장) 확인")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
