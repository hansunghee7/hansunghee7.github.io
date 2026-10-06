"""check_n_collisions.py의 순수 함수(rows, similar) 단위 시험.

main()은 실제 docs/탐_업무대장.md·docs/클라우드탐_업무대장.md를 읽으므로 이 시험에서는
부르지 않는다. rows()는 임시 파일 경로를 받아 그 파일만 읽으므로 tmp_path로 격리된다.

실행: python -m pytest scripts/test_check_n_collisions.py
"""
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_n_collisions_under_test", SCRIPTS / "check_n_collisions.py")
cnc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cnc)


# ---------------------------------------------------------------------------
# rows(path)
# ---------------------------------------------------------------------------

def test_rows_missing_file_returns_empty(tmp_path):
    assert cnc.rows(str(tmp_path / "없음.md")) == []


def test_rows_empty_file_returns_empty(tmp_path):
    f = tmp_path / "ledger.md"
    f.write_text("", encoding="utf-8")
    assert cnc.rows(str(f)) == []


def test_rows_parses_table_row(tmp_path):
    f = tmp_path / "ledger.md"
    f.write_text("| N12 | 예시 안건 설명 | 진행중 |\n", encoding="utf-8")
    found = cnc.rows(str(f))
    assert found == [(12, 1, "예시 안건 설명")]


def test_rows_parses_heading_row_with_status_prefix(tmp_path):
    f = tmp_path / "ledger.md"
    f.write_text("### [완료] N34: 예시 헤딩 안건\n", encoding="utf-8")
    found = cnc.rows(str(f))
    assert found == [(34, 1, "예시 헤딩 안건")]


def test_rows_parses_heading_row_without_status_prefix(tmp_path):
    f = tmp_path / "ledger.md"
    f.write_text("## N7: 상태 없는 헤딩\n", encoding="utf-8")
    found = cnc.rows(str(f))
    assert found == [(7, 1, "상태 없는 헤딩")]


def test_rows_ignores_inline_mentions_in_prose(tmp_path):
    # "N42 끝났으니"처럼 본문 중 번호 언급은 항목 정의가 아니므로 세지 않는다.
    f = tmp_path / "ledger.md"
    f.write_text("이번에 N42 끝났으니 다음 안건으로 넘어간다.\n", encoding="utf-8")
    assert cnc.rows(str(f)) == []


def test_rows_tracks_correct_line_numbers_across_multiple_entries(tmp_path):
    f = tmp_path / "ledger.md"
    f.write_text(
        "머리말\n"
        "| N1 | 첫 안건 | 열림 |\n"
        "그냥 본문 줄\n"
        "### N2: 둘째 안건\n",
        encoding="utf-8",
    )
    found = cnc.rows(str(f))
    assert found == [(1, 2, "첫 안건"), (2, 4, "둘째 안건")]


# ---------------------------------------------------------------------------
# similar(text_a, text_b)
# ---------------------------------------------------------------------------

def test_similar_identical_text_is_similar():
    assert cnc.similar("브라우저 임대 정책 정리", "브라우저 임대 정책 정리") is True


def test_similar_overlapping_tokens_is_similar():
    assert cnc.similar("브라우저 임대 정책 정리", "브라우저 임대 정책 2차 수정") is True


def test_similar_unrelated_text_is_not_similar():
    assert cnc.similar("브라우저 임대 정책 정리", "숏폼 음성 파이프라인 교체") is False


def test_similar_empty_strings_are_not_similar():
    assert cnc.similar("", "") is False
    assert cnc.similar("무언가 있는 텍스트", "") is False
    assert cnc.similar("", "무언가 있는 텍스트") is False
