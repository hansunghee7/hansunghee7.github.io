# -*- coding: utf-8 -*-
# api_run.py 자체 시험: 임시 HTTP 서버를 가짜 API로 쓴다. 실제 호출 없음.
import csv, json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

here = Path(__file__).resolve().parent
script = here.parent / "api_run.py" if (here.parent / "api_run.py").exists() else here / "api_run.py"
seen = {}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        seen["body"] = json.loads(self.rfile.read(n))
        seen["key_header"] = self.headers.get("x-api-key")
        out = json.dumps({"content": [{"type": "text", "text": "OK"}], "usage": {"input_tokens": 1000, "output_tokens": 500}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp())
q = tmp / "q.md"
q.write_text("hello", encoding="utf-8")
ledger = tmp / "usage.csv"


def run(extra_env, args):
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY_OPS", None)
    env["LOCALAPPDATA"] = str(tmp / "nohermes")
    env["CREDIT_LEDGER"] = str(ledger)
    env["ANTHROPIC_API_BASE"] = "http://127.0.0.1:%d" % srv.server_address[1]
    env.update(extra_env)
    return subprocess.run([sys.executable, str(script), "--who", "tester", "--prompt-file", str(q)] + args, env=env, capture_output=True, text=True, encoding="utf-8")


fail = []
r = run({}, [])
if r.returncode != 4:
    fail.append("no-key expected 4 got %s" % r.returncode)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--model", "claude-haiku-5-5"])
if r.returncode != 0 or "dummy-value" in (r.stdout + r.stderr):
    fail.append("normal call failed or leaked value rc=%s" % r.returncode)
if seen.get("key_header") != "dummy-value" or seen.get("body", {}).get("model") != "claude-haiku-5-5":
    fail.append("request wrong: %s" % seen)
rows = list(csv.DictReader(open(ledger, encoding="utf-8", newline=""))) if ledger.exists() else []
# haiku: 1000*0.10 + 500*0.50 = 350 per million -> 0.00035
if len(rows) != 1 or rows[0]["status"] != "ok" or abs(float(rows[0]["cost_usd"]) - 0.00035) > 1e-9 or not rows[0]["model"].endswith("@api"):
    fail.append("ledger row wrong: %s" % rows)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--model", "claude-sonnet-5-5"])
rows = list(csv.DictReader(open(ledger, encoding="utf-8", newline="")))
# sonnet: 1000*2 + 500*10 = 7000 per million -> 0.007
if abs(float(rows[-1]["cost_usd"]) - 0.007) > 1e-9:
    fail.append("sonnet cost wrong: %s" % rows[-1])
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--daily-usd", "0.001"])
if r.returncode != 3:
    fail.append("cap expected 3 got %s" % r.returncode)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--dry"])
if r.returncode != 0 or not r.stdout.startswith("DRY ok"):
    fail.append("dry wrong")
print("TEST PASS" if not fail else "TEST FAIL(%s)" % "; ".join(fail))
