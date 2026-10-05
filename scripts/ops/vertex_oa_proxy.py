# -*- coding: utf-8 -*-
"""Vertex(GCP 크레딧) OpenAI 호환 로컬 프록시(N167, 2026-10-05 탐, 사장님 "타미에게 GCP 크레딧으로 유료모델을 붙일 수 있는지"):
헤르메스 같은 OpenAI 호환 클라이언트는 고정된 API 키가 필요한데, Vertex는 한 시간짜리 gcloud 토큰을 쓴다. 이 프록시가 127.0.0.1에서 받아
gcloud 토큰(hansunghee7, 키 파일 없음)을 매번 새로 붙여 Vertex의 OpenAI 호환 주소로 그대로 넘긴다. 클라이언트 쪽 키는 아무 값이나 된다(비밀 아님).
모델 이름은 `google/gemini-3.8-flash`, `google/gemini-3.1-pro-preview`(Pro급, 10/5 시험 200), `google/gemini-2.5-pro`처럼 쓴다. 파트너 모델(Claude 등)은 이 프로젝트에서 열려 있지 않다(10/5 시험 404).
안전: 로컬(127.0.0.1)만 듣는다. 지출은 구글 측 사용량(gcp_usage.py)으로 본다. 필요할 때만 켜고 끈다.
사용: python scripts/ops/vertex_oa_proxy.py [포트=4021]    →   클라이언트 base_url = http://127.0.0.1:4021/v1"""
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT = "project-e59cbc25-e96a-44f5-ac6"
ACCOUNT = "hansunghee7@gmail.com"
UP = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/endpoints/openapi"
_tok = {"v": "", "at": 0.0}
_lock = threading.Lock()


def token():
    with _lock:
        if time.time() - _tok["at"] > 2700:  # 45분마다 갱신(토큰 수명 1시간)
            exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
            _tok["v"] = subprocess.run([exe, "auth", "print-access-token", f"--account={ACCOUNT}"], capture_output=True, text=True,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60).stdout.strip()
            _tok["at"] = time.time()
        return _tok["v"]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            ids = ["google/gemini-3.8-flash", "google/gemini-3.6-flash", "google/gemini-3.1-pro-preview", "google/gemini-2.5-pro"]
            return self._send(200, {"object": "list", "data": [{"id": i, "object": "model"} for i in ids]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        req = urllib.request.Request(UP + "/chat/completions", data=body, headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"}, method="POST")
        try:
            r = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            return self._send(e.code, e.read())
        except Exception as e:  # noqa: BLE001
            return self._send(502, {"error": {"message": f"프록시 업스트림 오류 {type(e).__name__}"}})
        ctype = r.headers.get("Content-Type", "application/json")
        if "event-stream" in ctype:  # 스트리밍은 조각 그대로 넘긴다
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            while True:
                chunk = r.read(1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            return
        self._send(r.status, r.read(), ctype)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4021
    print(f"Vertex OpenAI 프록시 http://127.0.0.1:{port}/v1 (127.0.0.1만)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
