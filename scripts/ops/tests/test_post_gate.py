# -*- coding: utf-8 -*-
"""SNS 게시 전 공용 관문(scripts/sns/post_gate.py) 시험. 모든 게시 경로가 같은 규칙을 쓰는지 본다."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("post_gate", ROOT / "scripts" / "sns" / "post_gate.py")
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)

GOOD = ("숫자로 일하는 팀의 첫 달\n\n본문 한 단락입니다.\n\n"
        "혹시 숫자로 일하는 방식이 더 궁금하시다면 심플리파이어 로그를 함께 봐 주세요.\n"
        "'측정이 바꾼 회의' https://www.simplifier.co.kr/logs/230/")


def test_good_post_passes_with_title():
    assert pg.text_problems(GOOD, "숫자로 일하는 팀의 첫 달") == []


def test_first_line_must_be_title():
    assert any("첫 줄" in p for p in pg.text_problems(GOOD, "다른 제목"))


def test_two_links_blocked():
    assert any("2개" in p for p in pg.text_problems(GOOD + "\nhttps://example.com/x"))


def test_link_must_be_related_log():
    t = GOOD.replace("https://www.simplifier.co.kr/logs/230/", "https://example.com/post")
    assert any("관련 글" in p for p in pg.text_problems(t))


def test_cta_required():
    t = GOOD.replace("심플리파이어 로그를 함께 봐 주세요", "링크를 보세요")
    assert any("CTA" in p for p in pg.text_problems(t))


def test_source_line_blocked():
    assert any("원문 링크 줄" in p for p in pg.text_problems(GOOD + "\n전문: 블로그"))
    assert any("원문 링크 줄" in p for p in pg.text_problems(GOOD + "\nfrom 홈페이지"))


def test_cli_exit_codes(tmp_path):
    f = tmp_path / "b.txt"
    f.write_text(GOOD, encoding="utf-8")
    assert pg.main(["--file", str(f), "--title", "숫자로 일하는 팀의 첫 달"]) == 0
    assert pg.main(["--file", str(f), "--title", "틀린 제목"]) == 1
