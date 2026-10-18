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
    append, build_entry, read_entries, _day_stamp, _day_path, FILE_PREFIX,
)


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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("단위 시험 통과.")
