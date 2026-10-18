"""run_log.py 단위시험(임시 디렉터리, 네트워크 없음).

실행: python scripts/test_run_log.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ops"))
from run_log import (  # noqa: E402
    append, build_entry, read_entries, filter_by_date, _day_stamp, _day_path, FILE_PREFIX,
    summarize_runs,
)


def test_summary_who_counts_and_status_distribution():
    rows = [
        {"who": "a", "status": "ok", "ts": "2026-10-18T10:00:00"},
        {"who": "a", "status": "fail", "ts": "2026-10-18T11:00:00"},
        {"who": "b", "status": "skip", "ts": "2026-10-19T10:00:00"},
    ]
    result = summarize_runs(rows)
    assert result["who"]["a"]["total"] == 2
    assert result["who"]["a"]["ok"] == 1 and result["who"]["a"]["fail"] == 1
    assert result["who"]["b"]["skip"] == 1


def test_summary_success_rate_uses_all_rows():
    result = summarize_runs([{"who": "a", "status": "ok"}, {"who": "a", "status": "fail"}])
    assert result["who"]["a"]["success_rate"] == 50.0


def test_summary_daily_total_and_fail_counts():
    result = summarize_runs([
        {"ts": "2026-10-18T10:00", "status": "fail"},
        {"ts": "2026-10-18T11:00", "status": "ok"},
        {"ts": "2026-10-19T10:00", "status": "fail"},
    ])
    assert result["by_day"]["2026-10-18"] == {"total": 2, "fail": 1}


def test_summary_recent_failures_top_n():
    rows = [{"ts": f"2026-10-18T{hour:02}:00", "status": "fail", "who": "a",
             "task": str(hour), "result": "bad"} for hour in range(1, 5)]
    assert [r["task"] for r in summarize_runs(rows, top=2)["recent_failures"]] == ["4", "3"]


def test_summary_empty_and_missing_status_are_safe():
    assert summarize_runs([]) == {"who": {}, "by_day": {}, "recent_failures": []}
    result = summarize_runs([{"ts": "2026-10-18T10:00"}])
    assert result["who"]["(unknown)"]["total"] == 1
    assert result["who"]["(unknown)"]["ok"] == 0


def test_filter_by_date_inclusive():
    rows = [{"ts": "2026-10-17T23:00"}, {"ts": "2026-10-18T01:00"},
            {"ts": "2026-10-19T01:00"}]
    assert filter_by_date(rows, since="2026-10-18", until="2026-10-18") == [rows[1]]


def test_build_entry_has_required_fields():
    e = build_entry("hermes:x", "todo 감지", "script", status="ok", result="3건",
                    at="2026-10-18T10:00:00+09:00")
    assert e["who"] == "hermes:x" and e["task"] == "todo 감지"
    assert e["tool"] == "script" and e["status"] == "ok" and e["result"] == "3건"
    assert e["ts"] == "2026-10-18T10:00:00+09:00"


def test_bad_status_falls_back_to_ok():
    assert build_entry("w", "t", "script", status="망함")["status"] == "ok"


def test_extra_does_not_clobber_reserved():
    e = build_entry("w", "t", "script", extra={"who": "덮어쓰기시도", "run_id": "r1"})
    assert e["who"] == "w"          # 예약 키 보호
    assert e["run_id"] == "r1"      # 새 키는 추가됨


def test_day_stamp_uses_kst_date():
    # +09:00 자정 직후는 그날, UTC로는 전날이어도 KST 날짜로 찍힌다.
    assert _day_stamp("2026-10-18T00:30:00+09:00") == "20261018"
    # UTC 23:30(=KST 다음날 08:30)은 KST 기준 다음날.
    assert _day_stamp("2026-10-18T23:30:00+00:00") == "20261019"


def test_append_writes_to_day_file():
    with tempfile.TemporaryDirectory() as d:
        assert append("w", "t", "script", result="r", day_dir=d,
                      at="2026-10-18T10:00:00+09:00") is True
        expected = _day_path(d, "2026-10-18T10:00:00+09:00")
        assert os.path.basename(expected) == FILE_PREFIX + "20261018.jsonl"
        obj = json.loads(Path(expected).read_text(encoding="utf-8").strip())
        assert obj["who"] == "w" and obj["result"] == "r"


def test_append_appends_not_overwrites():
    with tempfile.TemporaryDirectory() as d:
        at = "2026-10-18T10:00:00+09:00"
        append("a", "t1", "script", day_dir=d, at=at)
        append("b", "t2", "script", day_dir=d, at=at)
        assert len(read_entries(day_dir=d)) == 2


def test_read_entries_merges_multiple_days_sorted():
    with tempfile.TemporaryDirectory() as d:
        append("b", "day2", "script", day_dir=d, at="2026-10-19T09:00:00+09:00")
        append("a", "day1", "script", day_dir=d, at="2026-10-18T09:00:00+09:00")
        rows = read_entries(day_dir=d)
        # 두 날짜 파일이 생기고, ts 순으로 합쳐진다(앞이 18일).
        assert [r["task"] for r in rows] == ["day1", "day2"]
        files = sorted(os.path.basename(p) for p in Path(d).glob(FILE_PREFIX + "*.jsonl"))
        assert files == ["run_log_20261018.jsonl", "run_log_20261019.jsonl"]


def test_append_never_raises_on_bad_path():
    # 존재할 수 없는 드라이브로 써도 예외 없이 False.
    assert append("w", "t", "script", path="Z:\\nope\\x\\run_log.jsonl") is False


def test_read_entries_missing_dir_is_empty():
    with tempfile.TemporaryDirectory() as d:
        assert read_entries(day_dir=os.path.join(d, "nope")) == []


def _date_rows():
    return [
        {"ts": "2026-10-17T23:59:59+09:00", "task": "before"},
        {"ts": "2026-10-18T00:00:00+09:00", "task": "start"},
        {"ts": "2026-10-19T12:00:00+09:00", "task": "end"},
        {"ts": "2026-10-20T00:00:00+09:00", "task": "after"},
    ]


def test_filter_since_includes_boundary_and_later():
    rows = filter_by_date(_date_rows(), since="2026-10-18")
    assert [row["task"] for row in rows] == ["start", "end", "after"]


def test_filter_until_includes_boundary_and_earlier():
    rows = filter_by_date(_date_rows(), until="2026-10-19")
    assert [row["task"] for row in rows] == ["before", "start", "end"]


def test_filter_since_until_inclusive_range():
    rows = filter_by_date(_date_rows(), since="2026-10-18", until="2026-10-19")
    assert [row["task"] for row in rows] == ["start", "end"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("단위 시험 통과.")
