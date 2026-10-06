import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import saegim_usage_fetch as f  # noqa: E402


def _save(d, name, ca):
    (d / name).write_text(json.dumps({"collected_at": ca}), encoding="utf-8")


def test_first_of_day_keeps_plain_name(tmp_path):
    assert f.pick_dest(tmp_path, {"collected_at": "2026-10-06T02:11:00Z"}).name == "2026-10-06.json"


def test_same_collected_at_skipped(tmp_path):
    _save(tmp_path, "2026-10-06.json", "2026-10-06T02:11:00Z")
    assert f.pick_dest(tmp_path, {"collected_at": "2026-10-06T02:11:00Z"}) is None


def test_later_run_same_day_gets_time_suffix(tmp_path):
    _save(tmp_path, "2026-10-06.json", "2026-10-06T02:11:00Z")
    p = f.pick_dest(tmp_path, {"collected_at": "2026-10-06T06:30:05Z"})
    assert p.name == "2026-10-06-063005.json"
    assert p.name[:10] == "2026-10-06"


def test_name_collision_gets_counter(tmp_path):
    _save(tmp_path, "2026-10-06.json", "2026-10-06T02:11:00Z")
    (tmp_path / "2026-10-06-063005.json").write_text("{}", encoding="utf-8")
    p = f.pick_dest(tmp_path, {"collected_at": "2026-10-06T06:30:05Z"})
    assert p.name == "2026-10-06-063005-2.json"
