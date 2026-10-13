"""링크드인 12시간 전용 읽기 시험: 가짜 게시 시각·가짜 스냅샷만 쓴다(링크드인·구PC 접속 없음).
(a) 12시간 창 계산 (b) 하루 2회 상한·차단 중지·연속 실패 휴식 (c) 보간과 표기 (d) maya_measure_due 판정 회귀 (e) 흔들기 범위."""
import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
import linkedin_12h as L  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, OPS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


due = _load("maya_measure_due")
entry = _load("linkedin_12h_read")
K = L.KST


def dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=K)


def post(pid, pub, **kw):
    return {"post": pid, "title": f"테스트글{pid}제목입니다", "planned": pub[:10], "published_at": pub + "+09:00", **kw}


# (a) 창 계산
def test_window_is_12h_to_13h_after_publish():
    p = post("1", "2026-10-14T10:00:00")
    at = L.scheduled_read_time(p)
    assert dt("2026-10-14T22:00:00") <= at <= dt("2026-10-14T23:00:00")
    sched = L.read_schedule([p, post("2", "2026-10-14T09:00:00", status="cancelled"),
                             post("3", "2026-10-14T09:00:00", snaps={"12h": {"likes": 1}})])
    assert [s[0] for s in sched] == ["1"]


def test_planned_fallback_is_9am():
    p = {"post": "9", "planned": "2026-10-14"}
    assert L.published_at(p) == dt("2026-10-14T09:00:00")


def test_regular_overlap_flagged():
    p = post("1", "2026-10-14T09:00:00")  # 12h = 21:00, 창 안에 21:05
    assert L.read_schedule([p])[0][3] is True
    assert L.decide(dt("2026-10-14T21:20:00"), [p], {})[0] is None


# (e) 흔들기 범위
def test_jitter_range_and_stable():
    vals = [L.jitter_minutes(str(i), "20261014") for i in range(300)]
    assert all(-15 <= v <= 15 for v in vals)
    assert max(vals) - min(vals) > 20
    assert L.jitter_minutes("5", "x") == L.jitter_minutes("5", "x")


# (b) 상한·차단·휴식
def test_decide_reads_inside_window_only():
    p = post("1", "2026-10-14T10:00:00")
    at = L.scheduled_read_time(p)
    assert L.decide(at - timedelta(minutes=1), [p], {})[0] is None
    assert L.decide(at, [p], {})[0] == "1"
    assert L.decide(dt("2026-10-14T23:30:00"), [p], {})[0] is None  # 창 지남


def test_daily_cap_two():
    p = post("1", "2026-10-14T10:00:00")
    now = L.scheduled_read_time(p)
    s = {"reads": {now.strftime("%Y-%m-%d"): ["a", "b"]}}
    assert L.decide(now, [p], s) == (None, "하루 상한")


def test_block_stops_day_no_retry_and_pause_after_two_days():
    p = post("1", "2026-10-14T10:00:00")
    now = L.scheduled_read_time(p)
    s = {}
    assert L.record_result(s, now, "1", ok=False, blocked=True) is False
    assert L.decide(now + timedelta(minutes=5), [p], s)[1].startswith("오늘 차단")
    n2 = now + timedelta(days=1)
    assert L.record_result(s, n2, "1", ok=False, blocked=False) is True  # 연속 2일 -> 휴식
    assert L.decide(n2 + timedelta(days=2), [p], s)[1] == "쉬는 중(연속 실패)"
    assert abs(datetime.fromisoformat(s["pause_until"]) - n2 - timedelta(days=3)) < timedelta(minutes=1)


def test_noncontinuous_failures_do_not_pause():
    s = {}
    L.record_result(s, dt("2026-10-14T22:00:00"), "1", False, False)
    assert L.record_result(s, dt("2026-10-16T22:00:00"), "1", False, False) is False


def test_block_text_markers():
    assert L.is_block_text('{"error": "링크드인 로그인 풀림"}')
    assert L.is_block_text("authwall")
    assert not L.is_block_text('{"ok": true}')


def test_entry_main_with_fake_reader(tmp_path):
    led = tmp_path / "led.json"
    p = post("1", "2026-10-14T10:00:00")
    led.write_text(json.dumps({"posts": [p]}), encoding="utf-8")
    now = L.scheduled_read_time(p)
    calls = []
    kw = dict(now=now, ledger=led, state_path=tmp_path / "st.json", snaps_path=tmp_path / "s.jsonl")
    assert entry.main([], reader=lambda: calls.append(1) or (False, True, "login"), **kw) == 1
    assert entry.main([], reader=lambda: calls.append(1) or (True, False, ""), **kw) == 0  # 같은 날 재시도 금지
    assert len(calls) == 1
    st = json.loads((tmp_path / "st.json").read_text(encoding="utf-8"))
    assert st["blocked_date"] == now.strftime("%Y-%m-%d")


# (c) 보간
def _snap(at, likes, imp, title="테스트글1제목입니다"):
    return {"at": at + "+09:00", "title": title, "likes": likes, "impressions": imp}


def test_interpolation_marked():
    target = dt("2026-10-14T22:00:00")
    snaps = [_snap("2026-10-14T20:00:00", 10, 100), _snap("2026-10-15T02:00:00", 40, 400)]
    r = L.interpolate_at(snaps, "테스트글1제목입니다", target)
    assert r["interpolated"] is True and "보간" in r["note"]
    assert (r["likes"], r["impressions"]) == (20, 200)  # 2/6 지점


def test_measured_inside_window_not_interpolated():
    target = dt("2026-10-14T22:00:00")
    r = L.interpolate_at([_snap("2026-10-14T22:30:00", 17, 170)], "테스트글1제목입니다", target)
    assert r["interpolated"] is False and r["likes"] == 17


def test_no_neighbors_returns_none():
    target = dt("2026-10-14T22:00:00")
    assert L.interpolate_at([_snap("2026-10-14T20:00:00", 1, 1)], "테스트글1제목입니다", target) is None
    assert L.interpolate_at([], "테스트글1제목입니다", target) is None


def test_snapshot_roundtrip(tmp_path):
    rec = {"fetched_at_kst": "2026-10-14 22:10", "posts": [{"head": "테스트글1제목입니다", "reactions": 3, "impressions": 30, "age": "12시간", "tail": "x"}]}
    path = tmp_path / "s.jsonl"
    L.append_snapshots(path, L.snapshot_lines(rec, "12h-read"))
    L.append_snapshots(path, L.snapshot_lines(rec, "12h-read"))
    got = L.load_snapshots(path)
    assert len(got) == 2 and got[0]["tail"] == "x" and got[0]["source"] == "12h-read"


# (d) maya_measure_due 회귀
def _ledger(tmp_path, monkeypatch, posts, daily=None, snaps=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    led = tmp_path / "led.json"
    led.write_text(json.dumps({"posts": posts}), encoding="utf-8")
    d = tmp_path / "daily"
    d.mkdir()
    for name, rec in (daily or {}).items():
        (d / name).write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(due, "PATH", led)
    monkeypatch.setattr(due, "DAILY", str(d / "*.json"))
    monkeypatch.setattr(due, "SNAPS", str(tmp_path / "snaps.jsonl"))
    if snaps:
        L.append_snapshots(tmp_path / "snaps.jsonl", snaps)
    return led


def test_due_regression_daily_wait_late(tmp_path, monkeypatch):
    p = post("1", "2026-10-14T09:00:00")
    _ledger(tmp_path, monkeypatch, [p], daily={"a.json": {"collected": "2026-10-14T21:05+09:00",
                                                          "posts": [{"title": "테스트글1제목입니다", "likes": 5, "impressions": 50}]}})
    assert due.status(now=dt("2026-10-14T22:00:00"))[0][3] == "일일 읽기로 측정(apply 필요)"
    _ledger(tmp_path / "x", monkeypatch, [p])
    assert due.status(now=dt("2026-10-14T20:00:00"))[0][3] == "대기"
    assert due.status(now=dt("2026-10-15T08:00:00"))[0][3] == "기한 지남"  # 스냅샷 없으면 기존 판정 그대로


def test_due_uses_interpolation_only_without_daily(tmp_path, monkeypatch):
    p = post("1", "2026-09-20T09:00:00")  # 기한 21:00
    sn = [_snap("2026-09-20T19:00:00", 10, 100), _snap("2026-09-21T09:00:00", 24, 240)]
    led = _ledger(tmp_path, monkeypatch, [p], snaps=sn)
    assert due.status(now=dt("2026-09-21T08:00:00"))[0][3] == "보간값으로 측정(apply 필요)"
    assert due.status(now=dt("2026-09-20T20:00:00"))[0][3] == "대기"
    due.main.__globals__["sys"].argv = ["x", "apply"]
    assert due.main() == 0
    s12 = json.loads(led.read_text(encoding="utf-8"))["posts"][0]["snaps"]["12h"]
    assert s12["interpolated"] is True and (s12["likes"], s12["impressions"]) == (12, 120)
