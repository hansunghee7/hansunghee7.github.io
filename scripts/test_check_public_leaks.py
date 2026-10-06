#!/usr/bin/env python3
"""check_public_leaks.py의 순수 판정 함수/정규식 시험 (git 호출 없음).

여기서 쓰는 "키처럼 보이는 문자열"은 전부 런타임에 조각을 이어 붙여 만든다.
실제 서비스의 진짜 키 형식을 그대로 베끼지 않고, 정규식이 요구하는 길이·
문자 구성만 재현한다. 이메일도 example.com/example.org 같은 명백한 가짜만
쓴다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import check_public_leaks as leaks


# ---- email_allowed -----------------------------------------------------

def test_email_allowed_exact_listed_address():
    assert leaks.email_allowed("hansunghee7@gmail.com")


def test_email_allowed_domain_and_subdomain():
    assert leaks.email_allowed("someone@simplifier.co.kr")
    assert leaks.email_allowed("someone@sub.simplifier.co.kr")


def test_email_allowed_example_domain():
    assert leaks.email_allowed("test@example.com")
    assert leaks.email_allowed("test@example.org")


def test_email_allowed_case_insensitive():
    assert leaks.email_allowed("Someone@EXAMPLE.COM")


def test_email_not_allowed_outside_list():
    addr = "customer" + "@" + "othercompany.example-business.net"
    assert not leaks.email_allowed(addr)


def test_email_not_allowed_lookalike_domain_suffix():
    # 진짜 허용 도메인의 "뒤에 뭔가 더 붙은" 가짜 도메인은 허용되면 안 된다.
    addr = "x" + "@" + "simplifier.co.kr.evil.example"
    assert not leaks.email_allowed(addr)


# ---- 이미지 파일명 제외 --------------------------------------------------

def test_email_regex_catches_image_at_filename_shape():
    # logo@2x.png 처럼 '@'가 들어간 이미지 파일명은 EMAIL 정규식에 걸리지만
    text = '<img src="logo@2x.png">'
    matches = leaks.EMAIL.findall(text)
    assert matches == ["logo@2x.png"]
    # IMAGE_EXT가 이미지 확장자를 보고 이메일이 아니라고 걸러낸다.
    assert leaks.IMAGE_EXT.search(matches[0])


def test_image_ext_does_not_match_real_email():
    assert not leaks.IMAGE_EXT.search("user@example.com")


def test_image_ext_matches_several_extensions():
    for name in ("a@2x.png", "b@3x.jpg", "c@2x.jpeg", "d.webp", "e.svg", "f.gif", "g.avif"):
        assert leaks.IMAGE_EXT.search(name), name


# ---- 빈 줄 ---------------------------------------------------------------

def test_empty_line_has_no_email_or_key_matches():
    assert leaks.EMAIL.findall("") == []
    for rx in leaks.KEYS.values():
        assert rx.search("") is None


# ---- 키 패턴 8종: 패턴만 재현한 조립 문자열로 매칭 확인 --------------------

def test_google_api_key_pattern_matches():
    fake = "AIza" + "A" * 35
    assert leaks.KEYS["구글 API 키"].search(fake)


def test_google_api_key_pattern_rejects_too_short():
    fake = "AIza" + "A" * 10  # 35자 미만이라 매칭되면 안 된다
    assert leaks.KEYS["구글 API 키"].search(fake) is None


def test_github_token_pattern_matches_short_form():
    fake = "ghp_" + "a" * 36
    assert leaks.KEYS["깃허브 토큰"].search(fake)


def test_github_token_pattern_matches_fine_grained_form():
    fake = "github_pat_" + "a" * 60
    assert leaks.KEYS["깃허브 토큰"].search(fake)


def test_github_token_pattern_rejects_too_short():
    fake = "ghp_" + "a" * 10
    assert leaks.KEYS["깃허브 토큰"].search(fake) is None


def test_telegram_token_pattern_matches():
    digits = "1" * 9
    fake = digits + ":AA" + "B" * 33
    assert leaks.KEYS["텔레그램 봇 토큰"].search(f" {fake} ")


def test_telegram_token_pattern_rejects_too_few_digits():
    digits = "1" * 5  # 8자 미만
    fake = digits + ":AA" + "B" * 33
    assert leaks.KEYS["텔레그램 봇 토큰"].search(f" {fake} ") is None


def test_openai_anthropic_key_pattern_matches():
    fake = "sk-" + "x" * 48
    assert leaks.KEYS["OpenAI·Anthropic 키"].search(fake)


def test_openai_anthropic_key_pattern_matches_ant_prefix():
    fake = "sk-ant-" + "x" * 48
    assert leaks.KEYS["OpenAI·Anthropic 키"].search(fake)


def test_openai_anthropic_key_pattern_rejects_too_short():
    fake = "sk-" + "x" * 10  # 32자 미만
    assert leaks.KEYS["OpenAI·Anthropic 키"].search(fake) is None


def test_groq_key_pattern_matches():
    fake = "gsk_" + "a" * 40
    assert leaks.KEYS["Groq 키"].search(fake)


def test_groq_key_pattern_rejects_too_short():
    fake = "gsk_" + "a" * 5
    assert leaks.KEYS["Groq 키"].search(fake) is None


def test_nvidia_key_pattern_matches():
    fake = "nvapi-" + "a" * 40
    assert leaks.KEYS["NVIDIA 키"].search(fake)


def test_nvidia_key_pattern_rejects_too_short():
    fake = "nvapi-" + "a" * 5
    assert leaks.KEYS["NVIDIA 키"].search(fake) is None


def test_slack_token_pattern_matches():
    fake = "xoxb-" + "a" * 20
    assert leaks.KEYS["슬랙 토큰"].search(fake)


def test_slack_token_pattern_rejects_too_short():
    fake = "xoxb-" + "a" * 5  # 20자 미만
    assert leaks.KEYS["슬랙 토큰"].search(fake) is None


def test_private_key_block_pattern_matches():
    header = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
    assert leaks.KEYS["개인 키 블록"].search(header)


def test_private_key_block_pattern_requires_private_key_suffix():
    header = "-----BEGIN " + "RSA PUBLIC KEY" + "-----"
    assert leaks.KEYS["개인 키 블록"].search(header) is None


def test_all_eight_key_patterns_present():
    # 문서 주석이 말하는 "8종"이 코드에서도 그대로 유지되는지 확인한다.
    assert len(leaks.KEYS) == 8


# ---- leak-check: allow 표식 ----------------------------------------------

def test_allow_mark_constant_value():
    assert leaks.ALLOW_MARK == "leak-check: allow"


def test_allow_mark_present_in_line():
    addr = "customer" + "@" + "othercompany.example-business.net"
    line = addr + "  # " + leaks.ALLOW_MARK
    assert leaks.ALLOW_MARK in line


def test_allow_mark_absent_in_line():
    addr = "customer" + "@" + "othercompany.example-business.net"
    assert leaks.ALLOW_MARK not in addr


# ---- mask ------------------------------------------------------------

def test_mask_keeps_first_four_chars_and_length():
    masked = leaks.mask("abcdefgh")
    assert masked == "abcd…(8자)"


def test_mask_on_short_string():
    masked = leaks.mask("ab")
    assert masked == "ab…(2자)"
