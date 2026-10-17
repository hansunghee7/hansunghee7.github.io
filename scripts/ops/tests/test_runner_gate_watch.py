"""runner_gate_watch.parse_gate_log 시험. 네트워크·ssh 없음."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner_gate_watch import parse_gate_log  # noqa: E402

NOW = datetime(2026, 10, 17, 18, 10, 0)


def test_empty_log_is_none():
    r = parse_gate_log([], NOW)
    assert r == {"last_outcome": "없음", "last_time": None, "giveup_6h": 0}


def test_pass_only():
    r = parse_gate_log(["2026-10-17 18:06:28 통과 avail=4197MB"], NOW)
    assert r["last_outcome"] == "통과"
    assert r["last_time"] == "2026-10-17 18:06:28"
    assert r["giveup_6h"] == 0


def test_giveup_counted_within_6h():
    lines = [
        "2026-10-17 18:00:25 대기 avail=2905MB window=y",
        "2026-10-17 18:05:25 30분 대기 뒤 포기",
        "2026-10-17 12:30:00 30분 대기 뒤 포기",
        "2026-10-17 18:06:28 통과 avail=4197MB",
    ]
    r = parse_gate_log(lines, NOW)
    assert r["giveup_6h"] == 2
    assert r["last_outcome"] == "통과"


def test_giveup_outside_6h_excluded():
    lines = ["2026-10-17 11:00:00 30분 대기 뒤 포기"]
    r = parse_gate_log(lines, NOW)
    assert r["giveup_6h"] == 0
    assert r["last_outcome"] == "포기"


def test_waiting_only_when_recent():
    recent = parse_gate_log(["2026-10-17 18:09:00 대기 avail=2905MB window=y"], NOW)
    assert recent["last_outcome"] == "대기중"
    stale = parse_gate_log(["2026-10-17 18:00:25 대기 avail=2905MB window=y"], NOW)
    assert stale["last_outcome"] == "없음"


def test_garbage_lines_ignored():
    r = parse_gate_log(["깨진 줄", "", "2026-10-17 18:06:28 통과 avail=1MB"], NOW)
    assert r["last_outcome"] == "통과"
