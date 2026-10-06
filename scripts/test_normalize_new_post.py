"""normalize_new_post.py의 순수 함수 단위 시험
(guess_image_ext, format_date_string, next_available_id).

process_one()/process()는 실제 파일 읽기·쓰기·이미지 다운로드(네트워크)를
하므로 이 시험에서는 부르지 않는다. 세 함수 모두 입력값만으로 결정되는
순수 함수라 네트워크·파일 접근 없이 바로 검증할 수 있다.

실행: python -m pytest scripts/test_normalize_new_post.py
"""
import importlib.util
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("normalize_new_post_under_test", SCRIPTS / "normalize_new_post.py")
nnp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nnp)


# ---------------------------------------------------------------------------
# guess_image_ext(url)
# ---------------------------------------------------------------------------

def test_guess_image_ext_from_fname_query_param():
    url = "http://cdn.kakao.com/img?fname=http://x.com/abc.PNG"
    assert nnp.guess_image_ext(url) == "png"


def test_guess_image_ext_from_path_when_no_fname():
    url = "http://cdn.kakao.com/path/xyz.gif"
    assert nnp.guess_image_ext(url) == "gif"


def test_guess_image_ext_empty_string_defaults_to_jpg():
    assert nnp.guess_image_ext("") == "jpg"


def test_guess_image_ext_no_recognizable_extension_defaults_to_jpg():
    assert nnp.guess_image_ext("http://cdn.kakao.com/noext") == "jpg"


# ---------------------------------------------------------------------------
# format_date_string(date_val)
# ---------------------------------------------------------------------------

def test_format_date_string_from_date_object():
    assert nnp.format_date_string(date(2026, 8, 12)) == "Aug 12. 2026"


def test_format_date_string_from_iso_datetime_string():
    assert nnp.format_date_string("2026-08-12T09:00:00+09:00") == "Aug 12. 2026"


def test_format_date_string_none_returns_none():
    assert nnp.format_date_string(None) is None


def test_format_date_string_unparseable_string_returns_none():
    assert nnp.format_date_string("날짜 아님") is None


def test_format_date_string_non_date_type_returns_none():
    assert nnp.format_date_string(12345) is None


# ---------------------------------------------------------------------------
# next_available_id(used_ids)
# ---------------------------------------------------------------------------

def test_next_available_id_picks_max_plus_one():
    used = {1, 2, 5}
    assert nnp.next_available_id(used) == 6
    assert 6 in used  # 호출한 번호를 즉시 사용 중 집합에 반영(연속 호출 중복 방지)


def test_next_available_id_empty_set_starts_at_one():
    used = set()
    assert nnp.next_available_id(used) == 1
    assert used == {1}


def test_next_available_id_sequential_calls_do_not_collide():
    used = {3}
    first = nnp.next_available_id(used)
    second = nnp.next_available_id(used)
    assert first != second
    assert {first, second} == {4, 5}
