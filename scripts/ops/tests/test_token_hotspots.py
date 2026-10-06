"""token_hotspots.py의 순수 함수(rlen, norm) 단위 시험.

파일 I/O·네트워크를 쓰지 않는 순수 문자열/길이 계산 함수만 다룬다.

실행: python -m pytest scripts/ops/tests/test_token_hotspots.py -v
"""
import importlib.util
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("token_hotspots_under_test", OPS / "token_hotspots.py")
th = importlib.util.module_from_spec(spec)
spec.loader.exec_module(th)


# ---- rlen -------------------------------------------------------------------

def test_rlen_string():
    assert th.rlen("hello") == 5


def test_rlen_empty_string():
    assert th.rlen("") == 0


def test_rlen_list_of_dicts_with_text():
    assert th.rlen([{"text": "ab"}, {"text": "cde"}]) == 5


def test_rlen_list_dict_missing_text_key_counts_zero():
    assert th.rlen([{"foo": "bar"}]) == 0


def test_rlen_list_of_non_dict_items_uses_str_len():
    assert th.rlen([123, "abc"]) == len(str(123)) + len(str("abc"))


def test_rlen_empty_list():
    assert th.rlen([]) == 0


def test_rlen_none_returns_zero():
    assert th.rlen(None) == 0


def test_rlen_int_returns_zero():
    assert th.rlen(42) == 0


def test_rlen_dict_returns_zero():
    # dict은 str도 list도 아니므로 0 (list 안의 dict만 text를 읽는다)
    assert th.rlen({"text": "ab"}) == 0


def test_rlen_mixed_list_dict_with_and_without_text():
    assert th.rlen([{"text": "ab"}, {"other": 1}, "cd"]) == 2 + 0 + 2


# ---- norm -------------------------------------------------------------------

def test_norm_collapses_internal_whitespace():
    assert th.norm("  a   b\tc  ") == "a b c"


def test_norm_replaces_long_digit_runs_with_n():
    assert th.norm("rm file123456") == "rm fileN"


def test_norm_keeps_short_digit_runs():
    assert th.norm("v2 test12") == "v2 test12"


def test_norm_replaces_exactly_three_digits():
    assert th.norm("a123b") == "aNb"


def test_norm_keeps_exactly_two_digits():
    assert th.norm("a12b") == "a12b"


def test_norm_truncates_to_90_chars():
    long_cmd = "echo " + ("x" * 200)
    got = th.norm(long_cmd)
    assert len(got) == 90
    assert got == long_cmd[:90]


def test_norm_empty_string():
    assert th.norm("") == ""


def test_norm_multiple_digit_runs_all_replaced():
    assert th.norm("cp file1000.txt file2000.txt") == "cp fileN.txt fileN.txt"
