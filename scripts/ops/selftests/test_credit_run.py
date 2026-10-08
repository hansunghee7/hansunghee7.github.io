# -*- coding: utf-8 -*-
# credit_run.py 자체 시험: 가짜 claude 프로그램으로 관문(하루 상한, 키 없음, 정상 호출 기록)을 확인한다. 실제 호출 없음.
import csv, json, os, subprocess, sys, tempfile
from pathlib import Path

here = Path(__file__).resolve().parent
script = here.parent / "credit_run.py" if (here.parent / "credit_run.py").exists() else here / "credit_run.py"
tmp = Path(tempfile.mkdtemp())
stub = tmp / "fakeclaude.py"
stub.write_text("import json,sys\nprint(json.dumps({'result':'OK','total_cost_usd':0.02,'usage':{'input_tokens':3,'output_tokens':2},'is_error':False}))\n", encoding="utf-8")
runner = tmp / "claude.cmd"
runner.write_text('@echo off\n"%s" "%s" %%*\n' % (sys.executable, stub), encoding="utf-8")
q = tmp / "q.md"
q.write_text("hello", encoding="utf-8")
ledger = tmp / "usage.csv"


def run(extra_env, args):
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY_OPS", None)
    env["LOCALAPPDATA"] = str(tmp / "nohermes")
    env["CREDIT_LEDGER"] = str(ledger)
    env["CLAUDE_BIN"] = str(runner)
    env.update(extra_env)
    return subprocess.run([sys.executable, str(script), "--who", "tester", "--prompt-file", str(q)] + args, env=env, capture_output=True, text=True, encoding="utf-8")


fail = []
r = run({}, [])
if r.returncode != 4:
    fail.append("no-key expected 4 got %s" % r.returncode)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, [])
if r.returncode != 0 or "dummy-value" in (r.stdout + r.stderr):
    fail.append("normal call failed or leaked value rc=%s" % r.returncode)
rows = list(csv.DictReader(open(ledger, encoding="utf-8", newline=""))) if ledger.exists() else []
if len(rows) != 1 or rows[0]["status"] != "ok" or abs(float(rows[0]["cost_usd"]) - 0.02) > 1e-9:
    fail.append("ledger row wrong: %s" % rows)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--daily-usd", "0.01"])
if r.returncode != 3:
    fail.append("cap expected 3 got %s" % r.returncode)
rows2 = list(csv.DictReader(open(ledger, encoding="utf-8", newline="")))
if len(rows2) != 1:
    fail.append("capped call must not add ledger rows")
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--dry", "--daily-usd", "5"])
if r.returncode != 0 or not r.stdout.startswith("DRY ok"):
    fail.append("dry run wrong rc=%s out=%s" % (r.returncode, r.stdout[:40]))
print("TEST PASS" if not fail else "TEST FAIL(%s)" % "; ".join(fail))
