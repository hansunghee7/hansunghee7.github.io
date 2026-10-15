# -*- coding: utf-8 -*-
"""행동 시점 기억 주입 시험(2026-10-15 탐). 지도·캐시를 임시 파일로 바꿔 네트워크 없이 확인한다."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jit_context as j  # noqa: E402


def test_rel_maps_worktree_and_main_paths():
    assert j.rel(r"C:\work\hansunghee7.github.io\scripts\ops\recall.py") == "scripts/ops/recall.py"
    assert j.rel("C:/work/tam-x/.claude/hooks/save-gate.py") == ".claude/hooks/save-gate.py"


def test_lookup_reports_used_by_and_cards(tmp_path, monkeypatch):
    g = tmp_path / "g.json"
    g.write_text(json.dumps({"edges": {"docs/a.md": ["scripts/ops/x_tool.py"], "scripts/ops/x_tool.py": ["CLAUDE#4e7b"]}}), encoding="utf-8")
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"cards": [{"p": "탐", "no": 1, "t": "x_tool 사용 규칙", "d": "", "b": "사장님 말"}]}), encoding="utf-8")
    monkeypatch.setattr(j, "GRAPH", g)
    monkeypatch.setattr(j, "CACHE", c)
    r, out = j.lookup("C:/work/hansunghee7.github.io/scripts/ops/x_tool.py")
    assert r == "scripts/ops/x_tool.py"
    assert any("docs/a.md" in o for o in out)
    assert any("CLAUDE#4e7b" in o for o in out)
    assert any("탐#1" in o for o in out)


def test_lookup_unrelated_file_is_quiet(tmp_path, monkeypatch):
    g = tmp_path / "g.json"
    g.write_text(json.dumps({"edges": {}}), encoding="utf-8")
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"cards": []}), encoding="utf-8")
    monkeypatch.setattr(j, "GRAPH", g)
    monkeypatch.setattr(j, "CACHE", c)
    assert j.lookup("C:/tmp/zzz.txt")[1] == []
