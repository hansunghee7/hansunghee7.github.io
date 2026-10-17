#!/usr/bin/env python3
"""check_writing_style.is_excluded / check_exposure_changes.is_site_excluded 시험.

둘 다 git을 호출하지 않는 순수 부분만 다룬다. _config.yml은 실제 저장소
파일이 아니라 tmp_path에 만든 가짜 파일을 쓴다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import check_writing_style
import check_exposure_changes


# ---- check_writing_style.is_excluded ------------------------------------

def test_is_excluded_empty_prefixes_list():
    assert not check_writing_style.is_excluded("docs/foo.md", [])


def test_is_excluded_empty_path():
    assert not check_writing_style.is_excluded("", ["docs/"])


def test_is_excluded_exact_match():
    assert check_writing_style.is_excluded("docs/internal.md", ["docs/internal.md"])


def test_is_excluded_prefix_match():
    assert check_writing_style.is_excluded("docs/internal/sub.md", ["docs/internal/"])


def test_is_excluded_no_match():
    assert not check_writing_style.is_excluded("docs/public.md", ["docs/internal/"])


def test_is_excluded_multiple_prefixes_one_matches():
    assert check_writing_style.is_excluded("a/b.md", ["x/", "a/"])


def test_is_excluded_multiple_prefixes_none_matches():
    assert not check_writing_style.is_excluded("c/d.md", ["x/", "a/"])


def test_is_excluded_prefix_without_trailing_slash_still_matches_startswith():
    # startswith 기준이라 경계 슬래시가 없으면 "비슷한 이름"도 걸린다(기존 동작, 버그 수정 대상 아님).
    assert check_writing_style.is_excluded("docs/internal-extra.md", ["docs/internal"])


# ---- check_exposure_changes.is_site_excluded ----------------------------

def test_is_site_excluded_basic(tmp_path):
    cfg = tmp_path / "_config.yml"
    cfg.write_text(
        "title: Site\n"
        "exclude:\n"
        "  - docs/internal\n"
        "  - secret.md\n"
        "permalink: /:title/\n",
        encoding="utf-8",
    )
    assert check_exposure_changes.is_site_excluded("docs/internal", str(cfg))
    assert check_exposure_changes.is_site_excluded("docs/internal/sub/page.md", str(cfg))
    assert check_exposure_changes.is_site_excluded("secret.md", str(cfg))
    assert not check_exposure_changes.is_site_excluded("public.md", str(cfg))


def test_is_site_excluded_empty_path_with_no_exclude_section(tmp_path):
    cfg = tmp_path / "_config.yml"
    cfg.write_text("title: Site\n", encoding="utf-8")
    assert not check_exposure_changes.is_site_excluded("", str(cfg))


def test_is_site_excluded_missing_config_file(tmp_path):
    missing = tmp_path / "does_not_exist.yml"
    assert not check_exposure_changes.is_site_excluded("anything.md", str(missing))


def test_is_site_excluded_comment_inside_block_does_not_end_it(tmp_path):
    cfg = tmp_path / "_config.yml"
    cfg.write_text(
        "exclude:\n"
        "  - docs/internal\n"
        "  # 주석 줄\n"
        "  - after_comment.md\n"
        "permalink: /:title/\n",
        encoding="utf-8",
    )
    assert check_exposure_changes.is_site_excluded("after_comment.md", str(cfg))


def test_is_site_excluded_blank_line_inside_block_does_not_end_it(tmp_path):
    cfg = tmp_path / "_config.yml"
    cfg.write_text(
        "exclude:\n"
        "  - docs/internal\n"
        "\n"
        "  - after_blank.md\n",
        encoding="utf-8",
    )
    assert check_exposure_changes.is_site_excluded("after_blank.md", str(cfg))


def test_is_site_excluded_ends_at_next_top_level_key(tmp_path):
    cfg = tmp_path / "_config.yml"
    cfg.write_text(
        "exclude:\n"
        "  - docs/internal\n"
        "permalink: /:title/\n"
        "  - not_really_excluded.md\n",
        encoding="utf-8",
    )
    assert not check_exposure_changes.is_site_excluded("not_really_excluded.md", str(cfg))


def test_is_site_excluded_no_exclude_key_at_all(tmp_path):
    cfg = tmp_path / "_config.yml"
    cfg.write_text("title: Site\npermalink: /:title/\n", encoding="utf-8")
    assert not check_exposure_changes.is_site_excluded("docs/internal", str(cfg))


# ---- check_exposure_changes.new_nav_links ---------------------------------

LOGO_OLD = '<a href="/" class="nav-logo"><img src="/a.png" alt="S"></a>'
LOGO_NEW = '<a href="/" class="nav-logo"><img src="/a.webp" alt="S"></a>'


def test_nav_link_image_only_change_is_not_new():
    assert check_exposure_changes.new_nav_links([LOGO_NEW], [LOGO_OLD]) == []


def test_nav_link_brand_new_href_is_flagged():
    new = '<a href="/secret/" class="x">Secret</a>'
    assert check_exposure_changes.new_nav_links([new], []) == [new]


def test_nav_link_changed_href_is_flagged():
    new = '<a href="/other/" class="nav-logo"><img src="/a.png" alt="S"></a>'
    assert check_exposure_changes.new_nav_links([new], [LOGO_OLD]) == [new]


def test_nav_link_duplicate_of_existing_href_is_flagged():
    # 같은 주소 링크가 하나 지워지고 둘이 추가되면 하나는 새 링크다
    assert check_exposure_changes.new_nav_links([LOGO_NEW, LOGO_NEW], [LOGO_OLD]) == [LOGO_NEW]


def test_nav_link_unreadable_href_is_flagged():
    odd = "<a class='x' href=>"
    assert check_exposure_changes.new_nav_links([odd], [LOGO_OLD]) == [odd]


def test_nav_link_single_and_unquoted_href_matched():
    old = "<a class=x href=/p/>t</a>"
    new = "<a class=x href='/p/'>t2</a>"
    assert check_exposure_changes.new_nav_links([new], [old]) == []


def test_nav_non_link_lines_ignored():
    assert check_exposure_changes.new_nav_links(["<img src='/a.webp'>"], []) == []

