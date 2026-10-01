"""유튜브 Analytics 읽기 전용 OAuth 동의를 1회 받아 리프레시 토큰을 파일로 저장한다 (2026-10-01, N103).

사용: python yt_oauth_once.py <client_secret_*.json> [--out C:/work/_ops/yt_oauth/token.json]
흐름: 로컬 127.0.0.1 임시 서버를 열고 동의 주소(auth_url.txt)를 만든다. 채널 주인이 브라우저에서 허용하면
구글이 임시 서버로 코드를 돌려주고, 이 스크립트가 코드를 토큰으로 바꿔 파일에 저장한다.
- 비밀값(클라이언트 비밀번호·토큰)은 화면과 로그에 출력하지 않는다. 저장 파일은 저장소 밖(_ops)에만 둔다.
- 범위는 읽기 전용 yt-analytics.readonly 하나(최소 권한).
"""
import base64, hashlib, http.server, json, os, secrets, sys, threading, urllib.parse, urllib.request
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
PORT = 0  # 0이면 빈 포트를 운영체제가 골라 준다(8765는 다른 프로그램이 이미 쓰고 있었다, 10/1)


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path("C:/work/_ops/yt_oauth/token.json")
    cfg = json.loads(src.read_text(encoding="utf-8"))["installed"]
    result = {}
    state = secrets.token_urlsafe(16)
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            p = urllib.parse.urlparse(self.path); qs = urllib.parse.parse_qs(p.query)
            if "code" in qs and qs.get("state", [""])[0] == state:
                result["code"] = qs["code"][0]
                body = "OK. You can close this tab.".encode()
            else:
                result["error"] = qs.get("error", ["no-code-or-state-mismatch"])[0]
                body = "Failed. Check the terminal.".encode()
            self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers(); self.wfile.write(body)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
    redirect = "http://127.0.0.1:%d/" % srv.server_address[1]
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    q = {"client_id": cfg["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
         "access_type": "offline", "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "auth_url.txt").write_text(cfg["auth_uri"] + "?" + urllib.parse.urlencode(q), encoding="utf-8")
    (out.parent / "waiting").write_text("waiting for consent\n")
    srv.serve_forever()
    (out.parent / "waiting").unlink(missing_ok=True)
    if "code" not in result:
        print("failed:", result.get("error")); return 1
    data = urllib.parse.urlencode({"code": result["code"], "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                                   "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier}).encode()
    with urllib.request.urlopen(urllib.request.Request(cfg["token_uri"], data=data), timeout=30) as r:
        tok = json.load(r)
    if "refresh_token" not in tok:
        print("failed: no refresh_token (scope=%s)" % tok.get("scope")); return 1
    out.write_text(json.dumps({"client_id": cfg["client_id"], "client_secret": cfg["client_secret"], "refresh_token": tok["refresh_token"], "scope": tok.get("scope")}), encoding="utf-8")
    print("ok: refresh token saved to", out, "scope:", tok.get("scope"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
