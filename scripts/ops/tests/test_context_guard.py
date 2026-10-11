"""context-guard.py 시험: 비율 계산, 5% 단계 중복 방지, 상태 파일 깨짐, usage 없음, 직접 손일 판정."""
import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "context-guard.py"
spec = importlib.util.spec_from_file_location("context_guard", HOOK)
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)


def asst(tokens=None, tools=()):
    m = {"content": [{"type": "tool_use", "name": n, "input": i} for n, i in tools]}
    if tokens is not None:
        m["usage"] = {"input_tokens": 10, "cache_read_input_tokens": tokens - 15, "cache_creation_input_tokens": 5}
    return json.dumps({"type": "assistant", "message": m})


def make(tmp_path, lines):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def env(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTEXT_GUARD_STATE_DIR", str(tmp_path / "st"))
    monkeypatch.setenv("CONTEXT_WINDOW_TOKENS", "1000000")


def test_ratio_below_threshold_is_silent(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    p = make(tmp_path, [asst(490000)])
    assert cg.evaluate({"transcript_path": p, "session_id": "s"}) == []


def test_ratio_at_50_warns_with_guidance(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    p = make(tmp_path, [asst(500000)])
    out = cg.evaluate({"transcript_path": p, "session_id": "s"})
    assert len(out) == 1 and "50%" in out[0] and "새 일은 시작하지 않음" in out[0]


def test_same_step_only_once_then_next_step(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    d = {"session_id": "s"}
    d["transcript_path"] = make(tmp_path, [asst(520000)])
    assert cg.evaluate(d)
    assert cg.evaluate(d) == []  # 같은 50% 단계 중복 없음
    d["transcript_path"] = make(tmp_path, [asst(560000)])
    assert cg.evaluate(d)  # 55% 단계
    d["session_id"] = "other"
    assert cg.evaluate(d)  # 세션별 독립


def test_broken_state_file_is_tolerated(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    (tmp_path / "st").mkdir()
    (tmp_path / "st" / "s.json").write_text("{깨진", encoding="utf-8")
    p = make(tmp_path, [asst(700000)])
    assert cg.evaluate({"transcript_path": p, "session_id": "s"})
    assert json.loads((tmp_path / "st" / "s.json").read_text(encoding="utf-8"))["level"] == 70


def test_no_usage_or_garbage_is_silent(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    p = make(tmp_path, [asst(None, [("Bash", {})]), "not json"])
    assert cg.evaluate({"transcript_path": p, "session_id": "s"}) == []
    assert cg.evaluate({"transcript_path": str(tmp_path / "none.jsonl")}) == []
    assert cg.evaluate({}) == []


def test_hand_heavy_message(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    tools = [("Bash", {"command": "ls"})] * 26 + [("Read", {})] * 4
    p = make(tmp_path, [asst(None, tools), asst(650000)])
    out = cg.evaluate({"transcript_path": p, "session_id": "s"})
    assert len(out) == 2 and "위임으로 돌려라" in out[1]


def test_delegation_in_window_suppresses_hand_line(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    tools = [("Bash", {"command": "ls"})] * 29 + [("Agent", {})]
    p = make(tmp_path, [asst(None, tools), asst(650000)])
    assert len(cg.evaluate({"transcript_path": p, "session_id": "s"})) == 1
    assert not cg.hand_heavy([("Bash", False)] * 24 + [("Read", False)] * 6)
    assert not cg.hand_heavy([("Bash", True)] * 30)
    assert not cg.hand_heavy([("Bash", False)] * 10)  # 30회 미만


def test_tail_read_limits_bytes_and_skips_cut_line(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    old = asst(900000)  # 앞부분의 큰 usage는 꼬리 밖이라 무시돼야 한다
    pad = [json.dumps({"type": "user", "message": {"content": "x" * 200}})] * 50
    p = make(tmp_path, [old] + pad + [asst(100000)])
    monkeypatch.setenv("CONTEXT_GUARD_TAIL_BYTES", "3000")
    usage, _ = cg.scan(p)
    assert usage == 100000  # 잘린 첫 줄이 있어도 예외 없이 마지막 usage
    assert cg.evaluate({"transcript_path": p, "session_id": "s"}) == []


def test_state_is_per_session_file_no_tmp_left(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    p = make(tmp_path, [asst(650000)])
    cg.evaluate({"transcript_path": p, "session_id": "a/b"})
    names = [x.name for x in (tmp_path / "st").iterdir()]
    assert names == ["a_b.json"]


def test_command_words_do_not_count_as_delegation():
    assert not cg.is_delegation("Bash", {"command": "nohup x; claude -p y; cat run_in_background.txt"})
    assert cg.is_delegation("Bash", {"command": "ls", "run_in_background": True})
    assert cg.is_delegation("Agent", {}) and cg.is_delegation("SendMessage", {})
    assert not cg.is_delegation("Monitor", {})


def test_boundary_49_percent_is_silent(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    p = make(tmp_path, [asst(490000)])
    assert cg.evaluate({"transcript_path": p, "session_id": "s"}) == []


def test_boundary_50_percent_warns(tmp_path, monkeypatch):
    env(monkeypatch, tmp_path)
    p = make(tmp_path, [asst(500000)])
    out = cg.evaluate({"transcript_path": p, "session_id": "s"})
    assert len(out) == 1 and "50%" in out[0]
