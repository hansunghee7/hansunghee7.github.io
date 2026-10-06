import csv
import json

from router_daily_metrics import compute, main


USAGE_FIELDS = ["time", "who", "model", "search", "in_tok", "out_tok",
                "search_q", "est_krw", "sec", "rc", "project"]
FAIL_FIELDS = ["time", "who", "reason", "model", "ok"]


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_compute_daily_metrics_and_project_classification():
    usage = [
        {"time": "2026-10-05 10:00", "rc": "0", "est_krw": "15.35", "project": "company-prod"},
        {"time": "2026-10-05 11:00", "rc": "2", "est_krw": "1.10", "project": "simplifier"},
        {"time": "2026-10-06 11:00", "rc": "0", "est_krw": "3.00", "project": "personal"},
    ]
    failovers = [
        {"time": "2026-10-05 12:00", "ok": "1"},
        {"time": "2026-10-05 13:00", "ok": "0"},
    ]
    days = compute(usage, failovers)
    assert [item["date"] for item in days] == ["2026-10-05", "2026-10-06"]
    assert days[0] == {
        "date": "2026-10-05", "total_calls": 4, "fallbacks": 2,
        "final_failures": 2, "final_failure_rate": 0.5,
        "company_calls": 2, "personal_calls": 0, "company_share": 1.0,
        "est_krw_sum": 16.45,
    }
    assert days[1]["company_calls"] == 0
    assert days[1]["company_share"] == 0.0


def test_project_column_absent_is_unknown():
    result = compute([{"time": "2026-10-05", "rc": "0", "est_krw": "0"}], [])[0]
    assert result["company_calls"] is None
    assert result["personal_calls"] is None
    assert result["company_share"] is None


def test_missing_files_and_empty_csv(tmp_path):
    assert main(["--csv-dir", str(tmp_path), "--out", str(tmp_path / "out.json")]) == 0
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == {"days": []}
    write_csv(tmp_path / "vertex_usage.csv", USAGE_FIELDS, [])
    write_csv(tmp_path / "vertex_failover.csv", FAIL_FIELDS, [])
    assert main(["--csv-dir", str(tmp_path), "--out", str(tmp_path / "empty.json")]) == 0
    assert json.loads((tmp_path / "empty.json").read_text(encoding="utf-8")) == {"days": []}


def test_date_filter_and_unknown_share_display(tmp_path, capsys):
    write_csv(tmp_path / "vertex_usage.csv", USAGE_FIELDS[:-1], [
        {"time": "2026-10-05 10:00", "rc": "0", "est_krw": "2"},
        {"time": "2026-10-06 10:00", "rc": "0", "est_krw": "3"},
    ])
    out = tmp_path / "filtered.json"
    main(["--csv-dir", str(tmp_path), "--out", str(out), "--date", "2026-10-06"])
    assert [d["date"] for d in json.loads(out.read_text(encoding="utf-8"))["days"]] == ["2026-10-06"]
    assert "미기록" in capsys.readouterr().out
