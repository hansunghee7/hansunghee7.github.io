"""archive_progress.py의 순수 함수 단위 시험
(split_lines, norm_persona, base_of, parse, tokens, overlap, find_reply).

main()은 실제 docs/진행상황.md를 읽고 쓰므로 이 시험에서는 부르지 않는다.
네트워크·파일 쓰기·git 호출 없이 메모리 상의 문자열만으로 검증한다.

실행: python -m pytest scripts/test_archive_progress.py
"""
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("archive_progress_under_test", SCRIPTS / "archive_progress.py")
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)


# ---------------------------------------------------------------------------
# split_lines(text)
# ---------------------------------------------------------------------------

def test_split_lines_normal_text():
    assert ap.split_lines("첫줄\n둘째줄\n") == ["첫줄\n", "둘째줄\n"]


def test_split_lines_empty_string():
    assert ap.split_lines("") == []


def test_split_lines_no_trailing_newline_keeps_last_line():
    assert ap.split_lines("a\nb") == ["a\n", "b"]


# ---------------------------------------------------------------------------
# norm_persona(raw)
# ---------------------------------------------------------------------------

def test_norm_persona_plain_name():
    assert ap.norm_persona("탐 인수인계 10/7") == "탐"


def test_norm_persona_variant_alias():
    # "클핏(클라우드)" 는 별칭 테이블을 거쳐 "핏(클라우드)"로 정규화된다.
    assert ap.norm_persona("클핏(클라우드) 상태") == "핏(클라우드)"


def test_norm_persona_none_input_returns_none():
    assert ap.norm_persona(None) is None


def test_norm_persona_empty_string_returns_none():
    assert ap.norm_persona("") is None


def test_norm_persona_no_match_returns_none():
    # "사장님"은 페르소나 목록에 없다.
    assert ap.norm_persona("사장님 공지") is None


# ---------------------------------------------------------------------------
# base_of(name)
# ---------------------------------------------------------------------------

def test_base_of_strips_variant_suffix():
    assert ap.base_of("핏(클라우드)") == "핏"


def test_base_of_plain_name_unchanged():
    assert ap.base_of("탐") == "탐"


def test_base_of_none_returns_none():
    assert ap.base_of(None) is None


def test_base_of_empty_string_returns_none():
    # ""는 falsy라 None을 돌려준다(빈 문자열 그대로가 아님).
    assert ap.base_of("") is None


# ---------------------------------------------------------------------------
# parse(text)
# ---------------------------------------------------------------------------

def test_parse_normal_text_splits_preamble_and_sections():
    text = "머리말\n## 제목1\n본문1\n## 제목2\n본문2\n"
    preamble, sections = ap.parse(text)
    assert preamble == ["머리말\n"]
    assert [s.title for s in sections] == ["제목1", "제목2"]
    assert sections[0].body == "본문1\n"
    assert sections[0].start_line == 2
    assert sections[1].start_line == 4


def test_parse_empty_text_returns_nothing():
    preamble, sections = ap.parse("")
    assert preamble == []
    assert sections == []


def test_parse_ignores_heading_markers_inside_code_fence():
    text = "## 제목\n```\n## 코드 안의 가짜 헤딩\n```\n본문 끝\n"
    preamble, sections = ap.parse(text)
    assert len(sections) == 1
    assert sections[0].title == "제목"
    assert "코드 안의 가짜 헤딩" in sections[0].body


# ---------------------------------------------------------------------------
# tokens(title)
# ---------------------------------------------------------------------------

def test_tokens_extracts_meaningful_words():
    found = ap.tokens("📢 2026-09-19 브라우저 임대 정책 N42")
    assert found == {"브라우저", "임대", "정책", "n42"}


def test_tokens_empty_string_returns_empty_set():
    assert ap.tokens("") == set()


def test_tokens_drops_stopwords_and_persona_names():
    # "탐"(페르소나), "완료"(불용어)는 제외되고 의미 있는 토큰만 남는다.
    found = ap.tokens("탐 작업 완료 보고")
    assert "탐" not in found
    assert "완료" not in found


# ---------------------------------------------------------------------------
# overlap(a, b)
# ---------------------------------------------------------------------------

def test_overlap_partial_token_match():
    assert ap.overlap({"브라우저", "임대"}, {"브라우저", "정책"}) == 1


def test_overlap_version_token_exact_match_scores_two():
    assert ap.overlap({"v10"}, {"v10"}) == 2


def test_overlap_empty_sets_is_zero():
    assert ap.overlap(set(), set()) == 0


def test_overlap_no_common_tokens_is_zero():
    assert ap.overlap({"브라우저"}, {"숏폼"}) == 0


# ---------------------------------------------------------------------------
# find_reply(req, sections)
# ---------------------------------------------------------------------------

def test_find_reply_matches_later_reply_from_target_persona():
    text = (
        "## 📥 탐→노트: 브라우저 임대 정책 확정 요청 2026-09-19\n"
        "질문 내용\n"
        "## 📤 노트→탐: 브라우저 임대 정책 확정 완료 2026-09-20\n"
        "답변 내용\n"
    )
    _, sections = ap.parse(text)
    req, reply = sections
    assert ap.find_reply(req, sections) is reply


def test_find_reply_no_matching_section_returns_none():
    text = "## 📥 탐→노트: 전혀 다른 안건 요청 2026-09-19\n질문\n"
    _, sections = ap.parse(text)
    req = sections[0]
    assert ap.find_reply(req, sections) is None


def test_find_reply_undated_request_returns_none():
    text = "## 📥 탐→노트: 날짜 없는 요청\n질문\n"
    _, sections = ap.parse(text)
    req = sections[0]
    assert req.date is None
    assert ap.find_reply(req, sections) is None
