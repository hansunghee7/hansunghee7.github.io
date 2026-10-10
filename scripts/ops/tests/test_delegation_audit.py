"""delegation_audit.py 단위 시험. 가짜 전사 폴더와 임시 ops 폴더만 쓴다(실제 전사·대장은 건드리지 않는다).

실행: python -m unittest scripts/ops/tests/test_delegation_audit.py
"""
import csv
import importlib.util
import json
import os
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("delegation_audit_under_test", OPS / "delegation_audit.py")
da = importlib.util.module_from_spec(spec)
spec.loader.exec_module(da)


def tool(name, **inp):
    return {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def stop(hook):
    return {"message": {"role": "user", "content": f"Stop hook feedback: [{hook}] blocked"}}


def make_root(tmp, ts=None):
    root = Path(tmp) / "projects"
    d = root / "C--work-hansunghee7-github-io"
    d.mkdir(parents=True)
    recs = [tool("Read"), tool("Agent"), tool("Bash", command="bash ask_dex.sh x"), tool("Bash", command="ls"),
            tool("Bash", command="sleep 1", run_in_background=True), stop("stuck-process-gate"), stop("stuck-process-gate"),
            stop("commit-gate"), stop("check-tone"), stop("weird-hook")]
    if ts:
        for r in recs:
            r["timestamp"] = ts
    (d / "s1.jsonl").write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    other = root / "C--work-other"
    other.mkdir()
    (other / "x.jsonl").write_text(json.dumps(tool("Agent")), encoding="utf-8")
    return str(root)


def rows_of(ops):
    with open(os.path.join(ops, "history.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class T(unittest.TestCase):
    def test_collect_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = da.collect(root=make_root(tmp), days=3)
            self.assertEqual((v["sessions"], v["calls"], v["deleg"]), (1, 5, 3))
            self.assertEqual((v["stop"], v["stuck"], v["commit"], v["tone"], v["other"]), (5, 2, 1, 1, 1))
            self.assertEqual(da.ratio(v), 60.0)

    def test_baseline_preserved_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, ops = make_root(tmp), os.path.join(tmp, "ops")
            for _ in range(2):
                da.run(root=root, ops_dir=ops, today=date(2026, 10, 11))
            rows = rows_of(ops)
            self.assertEqual([r["label"] for r in rows], ["baseline", "run"])
            self.assertEqual((rows[0]["calls"], rows[0]["stuck"], rows[0]["ratio_pct"]), ("2108", "163", "13.6"))
            self.assertEqual(rows[1]["calls"], "5")
            da.run(root=root, ops_dir=ops, today=date(2026, 10, 12))
            self.assertEqual(len(rows_of(ops)), 3)

    def test_decision_before_and_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = os.path.join(tmp, "ops")
            ts = datetime(2026, 10, 14, 9, 0).astimezone().isoformat()
            root = make_root(tmp, ts=ts)
            t14 = datetime(2026, 10, 14, 9, 0).timestamp()
            os.utime(os.path.join(root, "C--work-hansunghee7-github-io", "s1.jsonl"), (t14, t14))
            _, st = da.run(root=root, ops_dir=ops, today=date(2026, 10, 17))
            self.assertFalse(st["decision_due"])
            self.assertFalse(os.path.exists(os.path.join(ops, "decision_1018.md")))
            code, msg = da.watch(root=root, ops_dir=ops, today=date(2026, 10, 17))
            self.assertEqual(code, 0)
            code, msg = da.watch(root=root, ops_dir=ops, today=date(2026, 10, 18))
            self.assertEqual(code, 1)
            self.assertIn("판정 대기", msg)
            with open(os.path.join(ops, "decision_1018.md"), encoding="utf-8") as f:
                md = f.read()
            self.assertIn("13.6%", md)
            self.assertIn("기준선 163건 -> 2건", md)
            sp = os.path.join(ops, "state.json")
            with open(sp, encoding="utf-8") as f:
                st = json.load(f)
            self.assertTrue(st["decision_due"])
            st["decided"] = "차단 전환 보류"
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(st, f)
            code, _ = da.watch(root=root, ops_dir=ops, today=date(2026, 10, 19))
            self.assertEqual(code, 0)

    def test_stale_over_36h_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, ops = make_root(tmp), os.path.join(tmp, "ops")
            t0 = time.time()
            da.run(root=root, ops_dir=ops, today=date(2026, 10, 11), now=t0)
            code, _ = da.watch(root=root, ops_dir=ops, today=date(2026, 10, 11), now=t0 + 20 * 3600)
            self.assertEqual(code, 0)
            code, msg = da.watch(root=root, ops_dir=ops, today=date(2026, 10, 13), now=t0 + 70 * 3600)
            self.assertEqual(code, 1)
            self.assertIn("36시간", msg)


if __name__ == "__main__":
    unittest.main()
