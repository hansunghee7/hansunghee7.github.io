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
# 가격표: 오퍼스 1000*5 + 500*25 = 17500 -> 0.0175, 페이블 35000 -> 0.035
for m, want in (("claude-opus-5-5", 0.0175), ("claude-fable-5", 0.035)):
    r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--model", m])
    rows = list(csv.DictReader(open(ledger, encoding="utf-8", newline="")))
    if r.returncode != 0 or abs(float(rows[-1]["cost_usd"]) - want) > 1e-9 or rows[-1]["status"] != "ok":
        fail.append("%s cost wrong: %s" % (m, rows[-1]))
# 모르는 모델: 0원이 아니라 최고 단가(페이블)로, '가격미확인' 표시
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--model", "claude-unknown-9"])
rows = list(csv.DictReader(open(ledger, encoding="utf-8", newline="")))
if r.returncode != 0 or abs(float(rows[-1]["cost_usd"]) - 0.035) > 1e-9 or "가격미확인" not in rows[-1]["status"]:
    fail.append("unknown model wrong: %s" % rows[-1])
# 기본 경보선 100: 이미 쓴 금액이 경보선을 넘어도 멈추지 않고(0), 경보 로그가 남는다
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--daily-usd", "0.001"])
if r.returncode != 0 or "DAILY-ALERT" not in r.stderr or not (tmp / "api_run_alerts.log").exists():
    fail.append("alert-only expected 0 got %s" % r.returncode)
# --hard-stop 이면 옛 동작(3)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--daily-usd", "0.001", "--hard-stop"])
if r.returncode != 3:
    fail.append("hard-stop expected 3 got %s" % r.returncode)
# 기본 경보선이 100 인지(--dry 출력)
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--dry"])
if "cap=100.00" not in r.stdout:
    fail.append("default cap not 100: %s" % r.stdout)
# 타임아웃 인자 허용
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--timeout", "30"])
if r.returncode != 0:
    fail.append("timeout arg failed")
r = run({"ANTHROPIC_API_KEY_OPS": "dummy-value"}, ["--dry"])
if r.returncode != 0 or not r.stdout.startswith("DRY ok"):
    fail.append("dry wrong")
print("TEST PASS" if not fail else "TEST FAIL(%s)" % "; ".join(fail))
