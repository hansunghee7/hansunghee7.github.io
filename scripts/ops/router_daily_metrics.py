"""Daily summaries for Vertex usage and router failover CSV exports."""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


DEFAULT_CSV_DIR = "C:/work/_ops"
DEFAULT_OUT = "C:/work/_ops/n174/bl/out/router_daily.json"


def compute(usage_rows, failover_rows):
    """Return per-day metrics from iterable CSV row mappings."""
    usage_by_day = defaultdict(list)
    failover_by_day = defaultdict(list)
    for row in usage_rows:
        usage_by_day[(row.get("time") or "")[:10]].append(row)
    for row in failover_rows:
        failover_by_day[(row.get("time") or "")[:10]].append(row)

    results = []
    for day in sorted(set(usage_by_day) | set(failover_by_day)):
        usage = usage_by_day[day]
        failovers = failover_by_day[day]
        total = len(usage) + len(failovers)
        failures = sum(1 for row in usage if (row.get("rc") or "") != "0")
        failures += sum(1 for row in failovers if (row.get("ok") or "") != "1")
        estimated = sum(float(row.get("est_krw") or 0) for row in usage)
        project_recorded = any("project" in row for row in usage)
        if project_recorded:
            company = sum(
                1 for row in usage
                if any(term in (row.get("project") or "").lower()
                       for term in ("company", "simplifier"))
            )
            personal = len(usage) - company
            share = company / len(usage) if usage else 0.0
        else:
            company = personal = share = None
        results.append({
            "date": day,
            "total_calls": total,
            "fallbacks": len(failovers),
            "final_failures": failures,
            "final_failure_rate": round(failures / total, 4) if total else 0.0,
            "company_calls": company,
            "personal_calls": personal,
            "company_share": round(share, 4) if share is not None else None,
            "est_krw_sum": round(estimated, 2),
        })
    return results


def _read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize daily Vertex/router metrics")
    parser.add_argument("--csv-dir", default=DEFAULT_CSV_DIR)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--date")
    args = parser.parse_args(argv)

    csv_dir = Path(args.csv_dir)
    days = compute(
        _read_csv(csv_dir / "vertex_usage.csv"),
        _read_csv(csv_dir / "vertex_failover.csv"),
    )
    if args.date:
        days = [row for row in days if row["date"] == args.date]

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        json.dump({"days": days}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("date       total fallbacks final_fail fail_rate company_share est_krw")
    for row in days:
        share = "미기록" if row["company_share"] is None else f'{row["company_share"]:.4f}'
        print(f'{row["date"]} {row["total_calls"]:5d} {row["fallbacks"]:9d} '
              f'{row["final_failures"]:10d} {row["final_failure_rate"]:.4f} '
              f'{share:>13} {row["est_krw_sum"]:.2f}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
