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


def test_direct_link_allowed_without_cta():
    # 사장님 10/17: 독자가 보고 싶은 곳(팀 페이지 등)으로 바로 거는 링크는 로그 CTA 없이 통과(공정 마야-SNS게시 #8)
    t = GOOD.replace("https://www.simplifier.co.kr/logs/230/", "https://carvit.ai/ko/team/").replace(pg.CTA, "아래 링크에서 만나 보세요")
    assert pg.text_problems(t) == []


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


LI = ("숫자로 일하는 팀의 첫 달\n\n본문 한 단락입니다.\n\n"
      "같은 이야기를 홈페이지에 더 길게 썼습니다.\n"
      "https://www.simplifier.co.kr/logs/230/")


def test_linkedin_passes_without_cta():
    assert pg.text_problems(LI, "숫자로 일하는 팀의 첫 달", "linkedin") == []


def test_linkedin_blocks_cta_and_conclusion_first():
    assert any("상투구" in p for p in pg.text_problems(GOOD, None, "linkedin"))
    assert any("결론부터" in p for p in pg.text_problems(LI + "\n결론부터 말하면 이렇습니다.", None, "링크드인"))


def test_other_channels_still_need_cta():
    assert any("CTA" in p for p in pg.text_problems(LI, None, "facebook"))


def test_three_direct_links_allowed_and_four_blocked():
    # 사장님 10/19 크레딧 글: 신청 링크 3개를 바로 건다(공정 마야-SNS게시 #8)
    base = "제목\n\n본문\n\nhttps://a.example/1\nhttps://b.example/2\nhttps://c.example/3"
    assert pg.text_problems(base) == []
    assert pg.text_problems(base + "\nhttps://d.example/4") != []


def test_instagram_body_without_link_allowed():
    # 인스타·스레드는 링크를 첫 댓글·답글로 단다(공정 마야-SNS게시 #9)
    assert pg.text_problems("제목\n\n본문만 있습니다", channel="instagram") == []
    assert pg.text_problems("제목\n\n본문만 있습니다", channel="facebook") != []
