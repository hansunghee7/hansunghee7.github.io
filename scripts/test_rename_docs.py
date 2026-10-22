import importlib.util
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "rename_docs", Path(__file__).resolve().parent / "ops" / "rename_docs.py"
)
rd = importlib.util.module_from_spec(SPEC)
sys.modules["rename_docs"] = rd
SPEC.loader.exec_module(rd)


def write(p, text):
    p.write_text(text, encoding="utf-8")
    return p


def test_word_boundary_matches_plain_mentions():
    assert rd.WORD.search("saegim 브랜드를 바꾼다")
    assert rd.WORD.search("예전엔 새김이라고 불렀다")
    assert rd.WORD.search("(Saegim)")


def test_word_boundary_skips_compound_identifiers():
    assert rd.WORD.search("saegim-pass") is None
    assert rd.WORD.search("simplifier-saegim") is None
    assert rd.WORD.search("saegim_courier.py") is None
    assert rd.WORD.search("mcp__saegim__agents") is None


def test_scan_line_classifies_system_id_vs_replace():
    hits = rd.scan_line("saegim-mcp 서버와 saegim 브랜드가 함께 보인다")
    cats = [c for c, _ in hits]
    assert "skip" in cats  # saegim-mcp
    assert "replace" in cats  # 단독 saegim


def test_apply_case_preserves_capitalisation():
    assert rd.apply_case("carvit", "saegim") == "carvit"
    assert rd.apply_case("carvit", "Saegim") == "Carvit"
    assert rd.apply_case("carvit", "SAEGIM") == "CARVIT"


def test_history_file_untouched(tmp_path):
    root = tmp_path / "docs" / "지시서"
    root.mkdir(parents=True)
    f = write(root / "2026-09-15_로컬탐_작업.md", "saegim 서버를 점검했다\n")
    repo_root = tmp_path
    rd.REPO_ROOT = repo_root
    report = rd.process_file(f, {}, apply_changes=False)
    assert report["counts"]["history"] == 1
    assert report["counts"]["replace"] == 0
    assert f.read_text(encoding="utf-8") == "saegim 서버를 점검했다\n"


def test_explain_file_untouched(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = write(docs / "이름_정책.md", "saegim 이라는 옛 이름을 carvit 으로 바꾼다\n")
    rd.REPO_ROOT = tmp_path
    report = rd.process_file(f, {}, apply_changes=False)
    assert report["counts"]["explain"] == 1
    assert report["counts"]["replace"] == 0


def test_escape_marker_line_skipped(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = write(docs / "아무문서.md", "일반 설명 [옛이름 허용: 인용 목적] saegim 그대로 둔다\n일반 saegim 교체\n")
    rd.REPO_ROOT = tmp_path
    report = rd.process_file(f, {}, apply_changes=False)
    assert report["counts"]["explain"] == 1
    assert report["counts"]["replace"] == 1


def test_dry_run_does_not_write(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = write(docs / "아무문서.md", "saegim 소개 문구\n")
    rd.REPO_ROOT = tmp_path
    rd.process_file(f, {}, apply_changes=False)
    assert "saegim" in f.read_text(encoding="utf-8")


def test_apply_replaces_plain_word(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = write(docs / "아무문서.md", "Saegim 소개 문구, 새김도 함께 쓴다\n")
    rd.REPO_ROOT = tmp_path
    report = rd.process_file(f, {}, apply_changes=True)
    text = f.read_text(encoding="utf-8")
    assert "Carvit 소개 문구, 카빗도 함께 쓴다" in text
    assert report["counts"]["replace"] == 2


def test_apply_skips_compound_identifier(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = write(docs / "아무문서.md", "saegim-mcp 설정과 saegim 단어\n")
    rd.REPO_ROOT = tmp_path
    report = rd.process_file(f, {}, apply_changes=True)
    text = f.read_text(encoding="utf-8")
    assert "saegim-mcp" in text  # 시스템 ID는 그대로
    assert "carvit 단어" in text  # 단독 낱말만 치환
    assert report["counts"]["skip"] == 1
    assert report["counts"]["replace"] == 1


def test_heading_link_break_is_blocked_in_apply(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    target = write(docs / "대상.md", "# saegim 설명\n본문 saegim 단어\n")
    other = write(docs / "다른문서.md", "[참고](대상.md#saegim-설명)\n")
    rd.REPO_ROOT = tmp_path
    link_index = rd.build_link_index([target, other])
    report = rd.process_file(target, link_index, apply_changes=True)
    text = target.read_text(encoding="utf-8")
    assert "# saegim 설명" in text  # 헤딩 줄은 링크 위험으로 보존
    assert "본문 carvit 단어" in text  # 본문 줄은 그대로 치환
    assert len(report["blocked"]) == 1


def test_heading_without_incoming_link_is_replaced(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    target = write(docs / "대상.md", "# saegim 설명\n")
    rd.REPO_ROOT = tmp_path
    link_index = rd.build_link_index([target])
    report = rd.process_file(target, link_index, apply_changes=True)
    text = target.read_text(encoding="utf-8")
    assert "# carvit 설명" in text
    assert report["blocked"] == []


def test_find_md_files_excludes_git_and_cache(tmp_path):
    docs = tmp_path / "docs"
    (docs / ".git").mkdir(parents=True)
    write(docs / ".git" / "x.md", "saegim\n")
    write(docs / "ok.md", "saegim\n")
    files = rd.find_md_files(docs)
    names = {p.name for p in files}
    assert "ok.md" in names
    assert "x.md" not in names


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
