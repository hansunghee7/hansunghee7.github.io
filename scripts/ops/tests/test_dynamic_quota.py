"""dynamic_quota.py 단위 시험. 상태·크레딧·사용 기록 파일은 임시 폴더로 바꾸고, gcp_usage(실제 사용량 API)는 import 자체를 막아 호출하지 않는다.

실행: python -m pytest scripts/ops/tests/test_dynamic_quota.py  (또는 python -m unittest)
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dynamic_quota_under_test", OPS / "dynamic_quota.py")
dq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dq)

TODAY = date(2026, 10, 4)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for name, val in (("OPS", self.dir), ("STATE", self.dir / "dynamic_quota.json"), ("BUDGET", self.dir / "vertex_budget.json")):
            p = mock.patch.object(dq, name, val)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.dict(sys.modules, {"gcp_usage": None})  # None이면 import가 ImportError -> 우리 호출 기록(csv)으로 대체
        p.start()
        self.addCleanup(p.stop)

    def write_budget(self, **kw):
        (self.dir / "vertex_budget.json").write_text(json.dumps(kw), encoding="utf-8")

    def write_usage(self, rows):
        lines = ["time,est_krw"] + [f"{t},{c}" for t, c in rows]
        (self.dir / "vertex_usage.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_calls(self, rows):
        lines = ["time,who"] + [f"{t},{w}" for t, w in rows]
        (self.dir / "agent_calls.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


class Budget(Base):
    def test_defaults_when_missing_or_corrupt(self):
        self.assertEqual(dq.budget(), dq.DEFAULT_BUDGET)
        (self.dir / "vertex_budget.json").write_text("{깨진", encoding="utf-8")
        self.assertEqual(dq.budget(), dq.DEFAULT_BUDGET)

    def test_partial_override_keeps_other_defaults(self):
        self.write_budget(balance=5)
        b = dq.budget()
        self.assertEqual(b["balance"], 5)
        self.assertEqual(b["safety"], dq.DEFAULT_BUDGET["safety"])


class Spent(Base):
    def test_no_file_is_zero(self):
        self.assertEqual(dq.vertex_spent("2026-10-01"), 0.0)

    def test_range_is_start_inclusive_before_exclusive(self):
        self.write_usage([("2026-09-30 10:00:00", 100), ("2026-10-01 10:00:00", 10), ("2026-10-02 09:00:00", 20), ("2026-10-03 09:00:00", 40)])
        self.assertEqual(dq.vertex_spent("2026-10-01"), 70.0)
        self.assertEqual(dq.vertex_spent("2026-10-01", before="2026-10-03"), 30.0)

    def test_blank_cost_counts_as_zero(self):
        self.write_usage([("2026-10-02 09:00:00", "")])
        self.assertEqual(dq.vertex_spent("2026-10-01"), 0.0)


class DayCap(Base):
    def base_budget(self, **kw):
        b = {"balance": 1_000_000, "as_of": "2026-10-01", "expiry": "2026-10-14", "safety": 0.5, "max_day": 10**9,
             "observe_until": "2000-01-01", "floor_remaining": 100_000}
        b.update(kw)
        self.write_budget(**b)

    def test_normal_formula(self):
        self.base_budget()  # (1,000,000 - 0) * 0.5 / 10일
        self.assertEqual(dq.vertex_day_cap(TODAY), 50000.0)

    def test_spending_lowers_cap_and_underspending_raises_it(self):
        self.base_budget()
        self.write_usage([("2026-10-02 09:00:00", 200_000)])  # (800,000 * 0.5) / 10
        self.assertEqual(dq.vertex_day_cap(TODAY), 40000.0)
        self.write_usage([])
        self.assertEqual(dq.vertex_day_cap(TODAY), 50000.0)

    def test_today_spending_is_excluded(self):
        self.base_budget()
        self.write_usage([(f"{TODAY.isoformat()} 09:00:00", 900_000)])
        self.assertEqual(dq.vertex_day_cap(TODAY), 50000.0)

    def test_max_day_ceiling_and_negative_floor_zero(self):
        self.base_budget(max_day=1000)
        self.assertEqual(dq.vertex_day_cap(TODAY), 1000.0)
        self.base_budget()
        self.write_usage([("2026-10-02 09:00:00", 2_000_000)])
        self.assertEqual(dq.vertex_day_cap(TODAY), 0.0)

    def test_days_left_has_minimum_one(self):
        self.base_budget(expiry="2026-10-01")  # 이미 지남
        self.assertEqual(dq.vertex_day_cap(TODAY), 500000.0)

    def test_observe_period_allows_down_to_floor(self):
        self.base_budget(observe_until="2026-10-12")
        self.assertEqual(dq.vertex_day_cap(TODAY), 900000.0)  # 1,000,000 - 0 - 바닥선 100,000
        self.write_usage([("2026-10-02 09:00:00", 850_000)])  # 남은 150,000, 바닥선 위
        self.assertEqual(dq.vertex_day_cap(TODAY), 50000.0)

    def test_observe_period_ends_at_floor_returns_to_normal(self):
        self.base_budget(observe_until="2026-10-12")
        self.write_usage([("2026-10-02 09:00:00", 950_000)])  # 남은 50,000 <= 바닥선 -> 평시 공식
        self.assertEqual(dq.vertex_day_cap(TODAY), 2500.0)  # 50,000 * 0.5 / 10

    def test_observe_period_over_uses_normal(self):
        self.base_budget(observe_until="2026-10-03")
        self.assertEqual(dq.vertex_day_cap(TODAY), 50000.0)

    def test_special_day_overrides_until_its_end(self):
        self.base_budget(special_day=777, special_until="2026-10-04")
        self.assertEqual(dq.vertex_day_cap(TODAY), 777.0)
        self.base_budget(special_day=777, special_until="2026-10-03")
        self.assertEqual(dq.vertex_day_cap(TODAY), 50000.0)

    def test_remaining(self):
        self.base_budget(balance=500_000)
        self.write_usage([("2026-10-02 09:00:00", 120_000), (f"{TODAY.isoformat()} 09:00:00", 50_000)])
        self.assertEqual(dq.remaining(TODAY), 380000.0)  # 오늘 분 제외


class Target(Base):
    def test_target_for(self):
        self.assertEqual(dq.target_for("덱스", 0), 25)
        self.assertEqual(dq.target_for("덱스", 10.4), 35)
        self.assertEqual(dq.target_for("덱스", 999), dq.CEIL["덱스"])  # 천장
        self.assertEqual(dq.target_for("타미", 3), 8)

    def test_used_on_counts_aliases_and_day(self):
        self.assertEqual(dq.used_on("비티", "2026-10-02"), 0)  # 파일 없음
        self.write_calls([("2026-10-02 08:00:00", "비티"), ("2026-10-02 09:00:00", "비티-sonnet"), ("2026-10-02 09:30:00", "비티-라우터"),
                          ("2026-10-02 10:00:00", "덱스"), ("2026-10-03 08:00:00", "비티")])
        self.assertEqual(dq.used_on("비티", "2026-10-02"), 3)
        self.assertEqual(dq.used_on("덱스", "2026-10-02"), 1)
        self.assertEqual(dq.used_on("타미", "2026-10-02"), 0)


class Measure(Base):
    def seed_state(self, last_day="2026-10-01", carry=None):
        s = {"records": {last_day: {}}, "carry": carry or {a: 0 for a in dq.BASE}}
        dq.STATE.write_text(json.dumps(s), encoding="utf-8")

    def test_first_run_does_not_backfill(self):
        s = dq.measure(TODAY)
        self.assertEqual(s["records"], {})
        self.assertEqual(s["today"]["targets"], dict(dq.BASE))
        self.assertEqual(s["today"]["date"], "2026-10-04")
        self.assertTrue(dq.STATE.exists())

    def test_unused_days_accumulate_carry_with_ceiling(self):
        self.seed_state()
        s = dq.measure(TODAY)  # 10/2·10/3 두 날 채점
        self.assertEqual(sorted(s["records"]), ["2026-10-01", "2026-10-02", "2026-10-03"])
        d1, d2 = s["records"]["2026-10-02"]["덱스"], s["records"]["2026-10-03"]["덱스"]
        self.assertEqual((d1["target"], d1["used"], d1["carry_after"]), (25, 0, 25.0))
        self.assertEqual((d2["target"], d2["carry_after"]), (50, 62.5))  # 0.5 * 25 + 부족 50
        self.assertEqual(s["today"]["targets"]["덱스"], dq.CEIL["덱스"])  # 25 + 63 이 천장 60으로 제한

    def test_meeting_target_decays_carry(self):
        self.seed_state(carry={"덱스": 20.0, "비티": 0, "타미": 0})
        self.write_calls([("2026-10-02 10:00:00", "덱스")] * 45 + [("2026-10-02 10:00:00", "비티")] * 10 + [("2026-10-02 10:00:00", "타미")] * 5)
        s = dq.measure(date(2026, 10, 3))  # 채점일은 10/2 하루
        r = s["records"]["2026-10-02"]
        self.assertEqual((r["덱스"]["target"], r["덱스"]["used"], r["덱스"]["carry_after"]), (45, 45, 10.0))  # 부족 0 -> 절반만 남김
        self.assertEqual(r["비티"]["carry_after"], 0.0)
        self.assertEqual(r["타미"]["carry_after"], 0.0)

    def test_partial_shortfall_adds_deficit(self):
        self.seed_state()
        self.write_calls([("2026-10-02 10:00:00", "비티")] * 4)
        s = dq.measure(date(2026, 10, 3))
        self.assertEqual(s["records"]["2026-10-02"]["비티"]["carry_after"], 6.0)  # 목표 10 - 사용 4

    def test_rerun_same_day_is_idempotent(self):
        self.seed_state()
        a = dq.measure(TODAY)
        b = dq.measure(TODAY)
        self.assertEqual(a["records"], b["records"])
        self.assertEqual(a["carry"], b["carry"])
        self.assertEqual(a["today"], b["today"])

    def test_corrupt_state_starts_fresh(self):
        dq.STATE.write_text("{깨진", encoding="utf-8")
        s = dq.measure(TODAY)
        self.assertEqual(s["records"], {})

    def test_today_includes_vertex_day_cap(self):
        self.write_budget(balance=1_000_000, as_of="2026-10-01", expiry="2026-10-14", safety=0.5, max_day=10**9, observe_until="2000-01-01")
        self.assertEqual(dq.measure(TODAY)["today"]["vertex_day_cap"], 50000.0)


class Status(Base):
    def test_status_prints_targets(self):
        state = {"today": {"date": "2026-10-04", "targets": {"덱스": 30, "비티": 12, "타미": 5}, "vertex_day_cap": 1234.5},
                 "carry": {"덱스": 5, "비티": 2, "타미": 0}, "records": {"2026-10-03": {"덱스": {"used": 3, "target": 25}}}}
        buf = io.StringIO()
        with mock.patch.object(dq, "measure", return_value=state), mock.patch.object(dq, "used_on", return_value=7), contextlib.redirect_stdout(buf):
            dq.status()
        out = buf.getvalue()
        self.assertIn("₩1,234.5", out)
        self.assertIn("덱스: 오늘 목표 30회(기본 25+이월 5", out)
        self.assertIn("3/25", out)


if __name__ == "__main__":
    unittest.main()
