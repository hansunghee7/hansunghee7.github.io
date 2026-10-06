"""check_claude_md_size.py의 줄 수 판정 함수(check_claude_md, check_role_notes) 단위 시험.

실제 저장소의 CLAUDE.md·docs/역할노트-*.md는 건드리지 않는다. check_claude_md()는
os.path.abspath(__file__) 기준 상대 경로로 CLAUDE.md를 찾으므로, 모듈의 __file__을
tmp_path 아래 가짜 경로로 바꿔치기해서 격리한다. check_role_notes()는 모듈 전역 ROOT를
직접 참조하므로 ROOT만 tmp_path로 바꿔치기한다.

실행: python -m pytest scripts/test_check_claude_md_size.py
"""
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_claude_md_size_under_test", SCRIPTS / "check_claude_md_size.py")
ccms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccms)


def _write_lines(path, n):
    path.write_text("\n".join(f"줄{i}" for i in range(n)) + "\n", encoding="utf-8")


def _isolate_claude_md(monkeypatch, tmp_path, n_lines):
    """check_claude_md()가 읽는 CLAUDE.md를 tmp_path 아래 가짜 파일로 바꿔치기한다."""
    fake_module_dir = tmp_path / "scripts"
    fake_module_dir.mkdir()
    monkeypatch.setattr(ccms, "__file__", str(fake_module_dir / "check_claude_md_size.py"))
    _write_lines(tmp_path / "CLAUDE.md", n_lines)


def test_check_claude_md_under_warn_passes_quietly(monkeypatch, tmp_path, capsys):
    _isolate_claude_md(monkeypatch, tmp_path, 199)
    assert ccms.check_claude_md() == 0
    out = capsys.readouterr().out
    assert "199줄" in out
    assert "::warning" not in out
    assert "::error" not in out


def test_check_claude_md_at_warn_boundary_is_not_warning(monkeypatch, tmp_path, capsys):
    # WARN=200은 "n > WARN"이 아니므로 경고 없이 통과한다.
    _isolate_claude_md(monkeypatch, tmp_path, 200)
    assert ccms.check_claude_md() == 0
    assert "::warning" not in capsys.readouterr().out


def test_check_claude_md_over_warn_under_limit_warns_but_passes(monkeypatch, tmp_path, capsys):
    _isolate_claude_md(monkeypatch, tmp_path, 201)
    assert ccms.check_claude_md() == 0
    out = capsys.readouterr().out
    assert "::warning" in out
    assert "201줄" in out


def test_check_claude_md_at_limit_boundary_warns_but_passes(monkeypatch, tmp_path, capsys):
    # LIMIT=250은 "n > LIMIT"이 아니므로 아직 실패가 아니다(경고만).
    _isolate_claude_md(monkeypatch, tmp_path, 250)
    assert ccms.check_claude_md() == 0
    assert "::warning" in capsys.readouterr().out


def test_check_claude_md_over_limit_fails(monkeypatch, tmp_path, capsys):
    _isolate_claude_md(monkeypatch, tmp_path, 251)
    assert ccms.check_claude_md() == 1
    out = capsys.readouterr().out
    assert "::error" in out
    assert "251줄" in out


def test_check_role_notes_no_files_passes_with_zero_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(ccms, "ROOT", str(tmp_path))
    (tmp_path / "docs").mkdir()
    assert ccms.check_role_notes() == 0


def test_check_role_notes_under_limit_passes(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ccms, "ROOT", str(tmp_path))
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_lines(docs / "역할노트-예시.md", 79)
    assert ccms.check_role_notes() == 0
    assert "::error" not in capsys.readouterr().out


def test_check_role_notes_over_limit_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ccms, "ROOT", str(tmp_path))
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_lines(docs / "역할노트-예시.md", 81)
    assert ccms.check_role_notes() == 1
    out = capsys.readouterr().out
    assert "::error" in out
    assert "81줄" in out


def test_check_role_notes_counts_each_failing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ccms, "ROOT", str(tmp_path))
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_lines(docs / "역할노트-가.md", 90)
    _write_lines(docs / "역할노트-나.md", 10)
    _write_lines(docs / "역할노트-다.md", 100)
    assert ccms.check_role_notes() == 2
