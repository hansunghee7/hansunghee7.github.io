"""run_log.py 단위시험(파일 임시 경로, 네트워크 없음).

실행: python scripts/test_run_log.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ops"))
from run_log import append, build_entry, _read_entries, _rotate_if_needed  # noqa: E402


def test_build_entry_has_required_fields():
    e = build_entry("hermes:x", "todo 감지", "script", status="ok", result="3건", at="2026-10-18T10:00:00+09:00")
    assert e["who"] == "hermes:x" and e["task"] == "todo 감지"
    assert e["tool"] == "script" and e["status"] == "ok" and e["result"] == "3건"
    assert e["ts"] == "2026-10-18T10:00:00+09:00"


def test_bad_status_falls_back_to_ok():
    e = build_entry("w", "t", "script", status="망함")
    assert e["status"] == "ok"


def test_extra_does_not_clobber_reserved():
    e = build_entry("w", "t", "script", extra={"who": "덮어쓰기시도", "run_id": "r1"})
    assert e["who"] == "w"          # 예약 키 보호
    assert e["run_id"] == "r1"      # 새 키는 추가됨


def test_append_writes_one_jsonl_line():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "run_log.jsonl")
        assert append("w", "t", "script", result="r", path=p) is True
        lines = Path(p).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["who"] == "w" and obj["result"] == "r"


def test_append_appends_not_overwrites():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "run_log.jsonl")
        append("a", "t1", "script", path=p)
        append("b", "t2", "script", path=p)
        assert len(_read_entries(p)) == 2


def test_append_never_raises_on_bad_path():
    # 존재할 수 없는 드라이브로 써도 예외 없이 False 만 반환.
    assert append("w", "t", "script", path="Z:\\nope\\x\\run_log.jsonl") is False


def test_rotation_moves_to_backup():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "run_log.jsonl")
        # 작은 상한으로 회전 강제.
        for _ in range(50):
            append("w", "t", "script", result="x" * 100, path=p, rotate_bytes=500)
        # 회전이 일어나 백업 파일이 생겼고 현재 파일도 존재.
        assert os.path.exists(p + ".1")
        assert os.path.exists(p)


def test_read_entries_missing_file_is_empty():
    assert _read_entries("Z:\\nope\\missing.jsonl") == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("단위 시험 통과.")
