#!/usr/bin/env python3
"""hwp_extract.html_to_preserved_text 의 표 보존 로직 단위 테스트.

실제 hwp 없이, hwp5html 이 내놓는 모양의 HTML 을 넣어 표가 markdown 표로 보존되는지,
표 없는 문서가 일반 텍스트로 나오는지 확인한다. pyhwp 설치 여부와 무관하게 돈다.

실행:  python -I scripts/ops/test_hwp_extract.py   (전부 통과하면 exit 0)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwp_extract import html_to_preserved_text  # noqa: E402


def test_scoring_table_preserved():
    h = (
        "<html><body><p>평가 배점표</p>"
        "<table>"
        "<tr><th>평가항목</th><th>배점</th></tr>"
        "<tr><td>사업성</td><td>40</td></tr>"
        "<tr><td>기술성</td><td>60</td></tr>"
        "</table></body></html>"
    )
    text, n = html_to_preserved_text(h)
    assert n == 1, n
    lines = [l for l in text.splitlines() if l.startswith("|")]
    assert lines[0] == "| 평가항목 | 배점 |", lines[0]
    assert lines[1] == "| --- | --- |", lines[1]
    assert "| 사업성 | 40 |" in lines
    assert "| 기술성 | 60 |" in lines
    assert "평가 배점표" in text


def test_pipe_in_cell_escaped():
    h = "<table><tr><td>기술성|핵심</td><td>60</td></tr></table>"
    text, n = html_to_preserved_text(h)
    assert n == 1
    assert r"기술성\|핵심" in text, text


def test_ragged_rows_padded():
    # 셀 수가 다른 행도 열 수에 맞춰 패딩되어야 표가 깨지지 않는다.
    h = (
        "<table>"
        "<tr><td>a</td><td>b</td><td>c</td></tr>"
        "<tr><td>x</td></tr>"
        "</table>"
    )
    text, n = html_to_preserved_text(h)
    assert n == 1
    rows = [l for l in text.splitlines() if l.startswith("|")]
    # 헤더 + 구분선 + 1 데이터행
    assert rows[1] == "| --- | --- | --- |", rows
    assert rows[2] == "| x |  |  |", rows[2]


def test_no_table_plain_text():
    h = "<html><body><p>첫 문단</p><p>둘째 문단</p></body></html>"
    text, n = html_to_preserved_text(h)
    assert n == 0
    assert "첫 문단" in text and "둘째 문단" in text
    assert "|" not in text


def test_multi_column_table():
    h = (
        "<table>"
        "<tr><td>구분</td><td>지원금</td><td>과제수</td></tr>"
        "<tr><td>스타트업</td><td>4.8억</td><td>8</td></tr>"
        "</table>"
    )
    text, n = html_to_preserved_text(h)
    assert "| 구분 | 지원금 | 과제수 |" in text
    assert "| 스타트업 | 4.8억 | 8 |" in text


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    main()
