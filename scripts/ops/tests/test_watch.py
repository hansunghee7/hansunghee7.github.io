"""watch.py의 순수 함수(소스 코드가 "---------- 순수 함수(시험 대상) ----------"로
직접 표시한 구간: parse_iso, parse_hermes_cron, hermes_fail_reason, infer_period_min,
is_stale, load_jobs, is_due, find_by_name)와 merge_state 단위 시험.

실제 서브프로세스(hermes·git)·네트워크·GUI는 부르지 않는다. hermes_fail_reason은
watch.run을, load_jobs는 watch.REPO/HERE/JOBS_FILE을 monkeypatch해서 외부 호출
경로 자체를 피한다(REPO를 .git이 없는 임시 경로로 돌리면 load_jobs가 git 분기를
타지 않고 바로 로컬 toml만 읽는다).

실행: python -m pytest scripts/ops/tests/test_watch.py -v
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("watch_under_test", OPS / "watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# parse_iso(s)
# ---------------------------------------------------------------------------

def test_parse_iso_valid_string():
    got = watch.parse_iso("2026-09-19T10:00:00+09:00")
    assert got == datetime(2026, 9, 19, 10, 0, tzinfo=KST)


def test_parse_iso_empty_string_returns_none():
    assert watch.parse_iso("") is None


def test_parse_iso_none_returns_none():
    assert watch.parse_iso(None) is None


# ---------------------------------------------------------------------------
# parse_hermes_cron(text)
# ---------------------------------------------------------------------------

def test_parse_hermes_cron_normal_block():
    text = (
        "  abcdef01 [cron]\n"
        "  Name: 테스트-크론\n"
        "  Last run: 2026-09-19T10:00:00+09:00 ok\n"
        "  Next run: 2026-09-20T10:00:00+09:00\n"
    )
    jobs = watch.parse_hermes_cron(text)
    assert set(jobs) == {"테스트-크론"}
    rec = jobs["테스트-크론"]
    assert rec["id"] == "abcdef01"
    assert rec["last"] == datetime(2026, 9, 19, 10, 0, tzinfo=KST)
    assert rec["last_status"] == "ok"
    assert rec["next"] == datetime(2026, 9, 20, 10, 0, tzinfo=KST)


def test_parse_hermes_cron_empty_text_returns_empty_dict():
    assert watch.parse_hermes_cron("") == {}


def test_parse_hermes_cron_strips_ansi_codes_around_korean_name():
    text = (
        "  \x1b[32mfedcba98\x1b[0m [cron]\n"
        "  Name: \x1b[1m한글 이름 크론\x1b[0m\n"
        "  Last run: 2026-09-19T10:00:00+09:00\n"
    )
    jobs = watch.parse_hermes_cron(text)
    assert "한글 이름 크론" in jobs
    assert jobs["한글 이름 크론"]["id"] == "fedcba98"


# ---------------------------------------------------------------------------
# hermes_fail_reason(hermes, cron_id, max_lines=3)  -- watch.run을 monkeypatch
# ---------------------------------------------------------------------------

def test_hermes_fail_reason_extracts_latest_failed_block(monkeypatch):
    out = (
        "abcdef0123456789abcdef0123456789 success job=foo\n"
        "line not important\n"
        "1111111111111111111111111111111111111111 failed job=bar\n"
        "FAIL disk-C:-space free=14.6% < 15%\n"
        "FAIL something else\n"
        "normal line not fail\n"
        "2222222222222222222222222222222222222222 failed job=baz\n"
        "FAIL old one, should not appear\n"
    )
    monkeypatch.setattr(watch, "run", lambda *a, **k: (0, out))
    got = watch.hermes_fail_reason("hermes", "1111111111111111111111111111111111111111")
    assert got == "FAIL disk-C:-space free=14.6% < 15%; FAIL something else"


def test_hermes_fail_reason_empty_cron_id_short_circuits(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("cron_id가 빈 값이면 run()을 부르면 안 된다")
    monkeypatch.setattr(watch, "run", boom)
    assert watch.hermes_fail_reason("hermes", "") == ""


def test_hermes_fail_reason_run_raises_is_swallowed(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("hermes 없음")
    monkeypatch.setattr(watch, "run", boom)
    assert watch.hermes_fail_reason("hermes", "abc") == ""


# ---------------------------------------------------------------------------
# infer_period_min(run_times, default=1440)
# ---------------------------------------------------------------------------

def test_infer_period_min_median_of_gaps():
    ts = [datetime(2026, 9, 1, 0, 0, tzinfo=KST), datetime(2026, 9, 1, 1, 0, tzinfo=KST), datetime(2026, 9, 1, 2, 0, tzinfo=KST)]
    assert watch.infer_period_min(ts) == 60.0


def test_infer_period_min_fewer_than_three_uses_default():
    ts = [datetime(2026, 9, 1, 0, 0, tzinfo=KST), datetime(2026, 9, 1, 1, 0, tzinfo=KST)]
    assert watch.infer_period_min(ts) == 1440


def test_infer_period_min_empty_list_uses_default():
    assert watch.infer_period_min([]) == 1440


def test_infer_period_min_ignores_duplicate_timestamps():
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=KST)
    t1 = datetime(2026, 9, 1, 1, 0, tzinfo=KST)
    t2 = datetime(2026, 9, 1, 2, 0, tzinfo=KST)
    # 중복 시각(gap=0)은 b>a 조건에서 제외되고 남은 간격의 중앙값만 쓰인다.
    assert watch.infer_period_min([t0, t0, t1, t1, t2]) == 60.0


# ---------------------------------------------------------------------------
# is_stale(last, period_min, at, grace_min=60)
# ---------------------------------------------------------------------------

def test_is_stale_true_when_past_threshold():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    assert watch.is_stale(datetime(2026, 9, 1, 0, 0, tzinfo=KST), 60, at) is True


def test_is_stale_false_just_under_threshold():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    assert watch.is_stale(datetime(2026, 9, 1, 4, 50, tzinfo=KST), 60, at) is False


# ---------------------------------------------------------------------------
# load_jobs()  -- watch.REPO/HERE/JOBS_FILE을 monkeypatch해 git 분기를 피한다
# ---------------------------------------------------------------------------

def test_load_jobs_reads_local_toml_when_no_git_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "REPO", str(tmp_path / "no-such-repo"))
    monkeypatch.setattr(watch, "HERE", str(tmp_path))
    monkeypatch.setattr(watch, "JOBS_FILE", "jobs_test.toml")
    (tmp_path / "jobs_test.toml").write_text('[[job]]\nid = "a"\nname = "Test"\nkind = "cmd"\n', encoding="utf-8")
    assert watch.load_jobs() == [{"id": "a", "name": "Test", "kind": "cmd"}]


def test_load_jobs_empty_job_list(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "REPO", str(tmp_path / "no-such-repo"))
    monkeypatch.setattr(watch, "HERE", str(tmp_path))
    monkeypatch.setattr(watch, "JOBS_FILE", "jobs_test.toml")
    (tmp_path / "jobs_test.toml").write_text("job = []\n", encoding="utf-8")
    assert watch.load_jobs() == []


# ---------------------------------------------------------------------------
# is_due(prev_entry, every_min, at)
# ---------------------------------------------------------------------------

def test_is_due_true_when_no_prior_entry():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    assert watch.is_due(None, 30, at) is True


def test_is_due_false_when_recently_checked():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    assert watch.is_due({"checked": at.isoformat()}, 30, at) is False


def test_is_due_malformed_checked_timestamp_is_treated_as_due():
    # parse_iso가 못 읽는 값(한글 문구)이면 last가 None이 되어 무조건 due로 본다.
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    assert watch.is_due({"checked": "이상한 값"}, 30, at) is True


# ---------------------------------------------------------------------------
# find_by_name(table, name)
# ---------------------------------------------------------------------------

def test_find_by_name_exact_match():
    assert watch.find_by_name({"a": 1, "ab": 2}, "a") == 1


def test_find_by_name_prefix_fallback():
    assert watch.find_by_name({"ab-xyz": 2}, "ab") == 2


def test_find_by_name_empty_table_returns_none():
    assert watch.find_by_name({}, "x") is None


# ---------------------------------------------------------------------------
# merge_state(prev, results, at)
# ---------------------------------------------------------------------------

def test_merge_state_first_run_has_no_alerts_even_if_failing():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    results = [{"id": "x", "name": "X", "status": "fail", "detail": "d", "owner": "탐", "note": "", "direct": False, "fail_after": 2}]
    new, alerts = watch.merge_state({}, results, at)
    assert alerts == []
    assert new["x"]["fails"] == 1


def test_merge_state_down_alert_fires_at_fail_after_threshold():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    prev = {"x": {"id": "x", "name": "X", "status": "fail", "detail": "d", "fails": 1, "since": "s", "checked": "c",
                  "owner": "탐", "note": "", "direct": False, "fail_after": 2}}
    results = [{"id": "x", "name": "X", "status": "fail", "detail": "d", "owner": "탐", "note": "", "direct": False, "fail_after": 2}]
    new, alerts = watch.merge_state(prev, results, at)
    assert [kind for kind, _ in alerts] == ["down"]
    assert new["x"]["fails"] == 2


def test_merge_state_reused_entry_passthrough_without_recompute():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    prev = {"x": {"id": "x", "name": "X", "status": "fail", "fails": 1}}
    results = [{"id": "x", "name": "X", "status": "fail", "reused": True}]
    new, alerts = watch.merge_state(prev, results, at)
    assert new["x"] == {"id": "x", "name": "X", "status": "fail"}  # reused 키만 빠지고 그대로
    assert alerts == []


def test_merge_state_empty_results_is_empty():
    at = datetime(2026, 9, 1, 5, 0, tzinfo=KST)
    new, alerts = watch.merge_state({}, [], at)
    assert new == {} and alerts == []
