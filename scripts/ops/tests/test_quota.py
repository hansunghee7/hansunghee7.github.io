"""quota.py의 순수 함수(parse_reset, blocked_until, summary) 단위 시험.

파일 I/O가 필요한 summary()는 quota.CALLS·quota.STATE를 tmp_path 아래 경로로
monkeypatch해서 완전히 격리한다. 실제 홈 디렉터리나 ops 폴더는 건드리지 않는다.
네트워크 호출 없음.

실행: python -m pytest scripts/ops/tests/test_quota.py -v
"""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("quota_under_test", OPS / "quota.py")
quota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quota)

NOW = datetime(2024, 1, 10, 12, 0, 0)


# ---- parse_reset -----------------------------------------------------------

def test_parse_reset_hours_minutes_seconds():
    got = quota.parse_reset("Resets in 2h30m15s", NOW)
    assert got == NOW + timedelta(hours=2, minutes=30, seconds=15)


def test_parse_reset_minutes_only():
    got = quota.parse_reset("Resets in 45m", NOW)
    assert got == NOW + timedelta(minutes=45)


def test_parse_reset_hours_only():
    got = quota.parse_reset("Resets in 5h", NOW)
    assert got == NOW + timedelta(hours=5)


def test_parse_reset_zero_values_still_matches():
    # 그룹이 모두 "0" 문자열이면 참으로 평가되어 매치로 취급된다(0시간 뒤 = now).
    got = quota.parse_reset("Resets in 0h0m0s", NOW)
    assert got == NOW


def test_parse_reset_embedded_in_longer_message():
    got = quota.parse_reset("rate limited. Resets in 1h2m3s. try later", NOW)
    assert got == NOW + timedelta(hours=1, minutes=2, seconds=3)


def test_parse_reset_no_match_falls_back_to_24h():
    got = quota.parse_reset("무슨 에러인지 모르겠음", NOW)
    assert got == NOW + timedelta(hours=24)


def test_parse_reset_resets_in_without_numbers_falls_back():
    got = quota.parse_reset("Resets in a while", NOW)
    assert got == NOW + timedelta(hours=24)


def test_parse_reset_empty_string_falls_back():
    got = quota.parse_reset("", NOW)
    assert got == NOW + timedelta(hours=24)


def test_parse_reset_none_falls_back():
    got = quota.parse_reset(None, NOW)
    assert got == NOW + timedelta(hours=24)


# ---- blocked_until ----------------------------------------------------------

def test_blocked_until_no_entry_returns_none():
    assert quota.blocked_until({}, "비티", NOW) is None


def test_blocked_until_pool_present_but_no_blocked_key():
    st = {"비티": {}}
    assert quota.blocked_until(st, "비티", NOW) is None


def test_blocked_until_future_returns_datetime():
    future = NOW + timedelta(hours=3)
    st = {"비티": {"blocked_until": future.isoformat(timespec="seconds")}}
    assert quota.blocked_until(st, "비티", NOW) == future


def test_blocked_until_past_returns_none():
    past = NOW - timedelta(hours=3)
    st = {"비티": {"blocked_until": past.isoformat(timespec="seconds")}}
    assert quota.blocked_until(st, "비티", NOW) is None


def test_blocked_until_exact_now_returns_none():
    # ">" 비교이므로 정확히 같은 시각은 막힘으로 치지 않는다(경계값).
    st = {"비티": {"blocked_until": NOW.isoformat(timespec="seconds")}}
    assert quota.blocked_until(st, "비티", NOW) is None


def test_blocked_until_other_pool_unaffected():
    future = NOW + timedelta(hours=1)
    st = {"비티": {"blocked_until": future.isoformat(timespec="seconds")}}
    assert quota.blocked_until(st, "덱스", NOW) is None


# ---- summary ----------------------------------------------------------------

def write_calls(path: Path, rows):
    lines = ["time,who,user,rc"] + [f"{t},{w},{u},{rc}" for t, w, u, rc in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_summary_no_files_all_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CALLS", tmp_path / "agent_calls.csv")
    monkeypatch.setattr(quota, "STATE", tmp_path / "quota_state.json")
    worst, lines = quota.summary(NOW)
    assert worst == 0
    assert any(l.startswith("비티: 최근 7일 0회(성공 0) / 예산 10") for l in lines)
    assert any(l.startswith("덱스: 최근 7일 0회(성공 0)") for l in lines)


def test_summary_excludes_calls_older_than_a_week(tmp_path, monkeypatch):
    calls = tmp_path / "agent_calls.csv"
    monkeypatch.setattr(quota, "CALLS", calls)
    monkeypatch.setattr(quota, "STATE", tmp_path / "quota_state.json")
    old = (NOW - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    recent = (NOW - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    write_calls(calls, [(old, "비티", "탐", "0"), (recent, "비티", "탐", "0")])
    worst, lines = quota.summary(NOW)
    assert any("비티: 최근 7일 1회(성공 1)" in l for l in lines)


def test_summary_ignores_unknown_who(tmp_path, monkeypatch):
    calls = tmp_path / "agent_calls.csv"
    monkeypatch.setattr(quota, "CALLS", calls)
    monkeypatch.setattr(quota, "STATE", tmp_path / "quota_state.json")
    t = (NOW - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    write_calls(calls, [(t, "알수없음", "탐", "0")])
    worst, lines = quota.summary(NOW)
    assert any(l.startswith("비티: 최근 7일 0회(성공 0)") for l in lines)


def test_summary_budget_near_limit_raises_worst(tmp_path, monkeypatch):
    calls = tmp_path / "agent_calls.csv"
    monkeypatch.setattr(quota, "CALLS", calls)
    monkeypatch.setattr(quota, "STATE", tmp_path / "quota_state.json")
    t = (NOW - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    rows = [(t, "비티", "탐", "0")] * 8  # 예산 10의 80% = 8
    write_calls(calls, rows)
    worst, lines = quota.summary(NOW)
    assert worst == 1
    assert any("비티: 최근 7일 8회(성공 8) / 예산 10" in l for l in lines)


def test_summary_under_budget_threshold_keeps_worst_zero(tmp_path, monkeypatch):
    calls = tmp_path / "agent_calls.csv"
    monkeypatch.setattr(quota, "CALLS", calls)
    monkeypatch.setattr(quota, "STATE", tmp_path / "quota_state.json")
    t = (NOW - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    rows = [(t, "비티", "탐", "0")] * 7  # 80% 미달
    write_calls(calls, rows)
    worst, _ = quota.summary(NOW)
    assert worst == 0


def test_summary_blocked_pool_shows_time_and_raises_worst(tmp_path, monkeypatch):
    state_path = tmp_path / "quota_state.json"
    monkeypatch.setattr(quota, "CALLS", tmp_path / "agent_calls.csv")
    monkeypatch.setattr(quota, "STATE", state_path)
    future = NOW + timedelta(hours=5)
    state_path.write_text(
        json.dumps({"비티": {"blocked_until": future.isoformat(timespec="seconds")}}),
        encoding="utf-8",
    )
    worst, lines = quota.summary(NOW)
    assert worst == 1
    assert any("막힘" in l and f"{future:%m-%d %H:%M}" in l for l in lines)


def test_summary_corrupt_state_is_treated_as_empty(tmp_path, monkeypatch):
    state_path = tmp_path / "quota_state.json"
    monkeypatch.setattr(quota, "CALLS", tmp_path / "agent_calls.csv")
    monkeypatch.setattr(quota, "STATE", state_path)
    state_path.write_text("{이상한 내용", encoding="utf-8")
    worst, lines = quota.summary(NOW)
    assert worst == 0
    assert all("막힘" not in l for l in lines)


def test_summary_malformed_time_rows_are_skipped(tmp_path, monkeypatch):
    calls = tmp_path / "agent_calls.csv"
    monkeypatch.setattr(quota, "CALLS", calls)
    monkeypatch.setattr(quota, "STATE", tmp_path / "quota_state.json")
    calls.write_text(
        "time,who,user,rc\n날짜아님,비티,탐,0\n,비티,탐,0\n",
        encoding="utf-8",
    )
    worst, lines = quota.summary(NOW)
    assert worst == 0
    assert any(l.startswith("비티: 최근 7일 0회(성공 0)") for l in lines)
