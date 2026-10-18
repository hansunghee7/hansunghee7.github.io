"""actions_budget_watch: gh 호출 실패 집계와 호스트 라벨 점검 단위 시험(gh를 가짜로 대체)."""
import base64
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import actions_budget_watch as w  # noqa: E402


def fake_run_factory(fail_all=False, wf_text="jobs:\n  a:\n    runs-on: ubuntu-latest\n"):
    def fake(cmd, **kw):
        a = " ".join(cmd)
        if fail_all:
            return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 403: rate limit exceeded")
        if a.endswith("--jq .private"):
            return SimpleNamespace(returncode=0, stdout="true\n", stderr="")
        if "contents/.github/workflows/" in a:
            return SimpleNamespace(returncode=0, stdout=base64.b64encode(wf_text.encode()).decode(), stderr="")
        if "contents/.github/workflows" in a:
            return SimpleNamespace(returncode=0, stdout="ci.yml\n", stderr="")
        if cmd[1:3] == ["run", "list"]:
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")
    return fake


def test_failure_exit_code_2(monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", fake_run_factory(fail_all=True))
    assert w.main() == 2
    out = capsys.readouterr().out
    assert "측정 불완전: 호출 실패" in out and "하한값" in out


def test_ok_reports_pinned_and_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", fake_run_factory())
    assert w.main() == 0
    out = capsys.readouterr().out
    assert f"호스트 직접 지정 워크플로: {len(w.REPOS)}개" in out and "ci.yml" in out
    assert "측정 불완전" not in out


def test_self_hosted_not_flagged(monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", fake_run_factory(wf_text="runs-on: [self-hosted, saegim-test]\n"))
    assert w.main() == 0
    assert "호스트 직접 지정 워크플로: 0개" in capsys.readouterr().out
