"""slot_audit.py의 순수 부분(front_matter) 단위 시험.

home_posts/draft_dates/sns_items/main()은 저장소 실제 경로
(log_assets/markdown, assets/data/sns_publish_queue.json)를 읽으므로 이
시험에서는 부르지 않는다. front_matter(path)는 주어진 파일 하나만 읽는
순수 파싱 함수라 tmp_path로 격리해 검증할 수 있다.

실행: python -m pytest scripts/test_slot_audit.py
"""
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("slot_audit_under_test", SCRIPTS / "slot_audit.py")
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)


# ---------------------------------------------------------------------------
# front_matter(path)
# ---------------------------------------------------------------------------

def test_front_matter_parses_quoted_and_plain_values(tmp_path):
    f = tmp_path / "a.md"
    f.write_text(
        '---\n'
        'title: "테스트 글"\n'
        'date: 2026-09-19T10:00:00+09:00\n'
        'published: true\n'
        '---\n'
        '본문\n',
        encoding="utf-8",
    )
    meta = sa.front_matter(f)
    assert meta == {
        "title": "테스트 글",
        "date": "2026-09-19T10:00:00+09:00",
        "published": "true",
    }


def test_front_matter_no_block_returns_empty_dict(tmp_path):
    f = tmp_path / "b.md"
    f.write_text("front matter가 전혀 없는 본문만 있는 글\n", encoding="utf-8")
    assert sa.front_matter(f) == {}


def test_front_matter_empty_block_returns_empty_dict(tmp_path):
    f = tmp_path / "c.md"
    f.write_text("---\n---\n본문\n", encoding="utf-8")
    assert sa.front_matter(f) == {}


def test_front_matter_ignores_indented_list_lines(tmp_path):
    # "  - 하나"처럼 들여쓴 목록 줄은 키:값이 아니므로 건너뛴다.
    f = tmp_path / "d.md"
    f.write_text(
        '---\n'
        'title: "목록 테스트"\n'
        'tags:\n'
        '  - 하나\n'
        '  - 둘\n'
        'date: 2026-09-19T10:00:00+09:00\n'
        '---\n본문\n',
        encoding="utf-8",
    )
    meta = sa.front_matter(f)
    assert meta["title"] == "목록 테스트"
    assert meta["date"] == "2026-09-19T10:00:00+09:00"
    assert "하나" not in meta and "둘" not in meta
