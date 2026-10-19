"""login_state.py 시험: 만료 판정·저장본 목록·저장본 없음 처리(Playwright 없이 도는 부분)와, 로컬 서버로 만든 가짜 로그인 앱에 대한 헤드리스 check 실측."""
import http.server
import importlib.util
import json
import threading
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("login_state", Path(__file__).resolve().parents[1] / "login_state.py")
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)


def test_login_redirect_means_expired():
    assert ls.looks_like_login("https://app.example.com/login?next=/home", "아무 글")
    assert ls.looks_like_login("https://accounts.google.com/o/oauth2/auth", "")
    assert not ls.looks_like_login("https://app.example.com/home", "대시보드")


def test_expect_text_and_url_both_count():
    assert ls.looks_like_login("https://app.example.com/home", "로그인하세요", expect="대시보드")
    # 리뷰 반영: 로그인 주소면 본문에 기대 글자가 우연히 있어도 만료다
    assert ls.looks_like_login("https://app.example.com/login", "대시보드 보임", expect="대시보드")
    assert not ls.looks_like_login("https://app.example.com/home", "대시보드 보임", expect="대시보드")
    # 경로 마디가 login이 아닌 정상 화면(auth 설정 등)은 만료로 오판하지 않는다
    assert not ls.looks_like_login("https://app.example.com/auth/settings", "설정", expect="설정")


def test_name_must_be_safe(tmp_path):
    for bad in ("../x", "a/b", "a\\b", "", "A", "x" * 41):
        with pytest.raises(ValueError):
            ls.state_path(bad, tmp_path)
    assert ls.state_path("carvit-check", tmp_path).name == "carvit-check.json"


def test_status_lists_state_files(tmp_path, capsys):
    (tmp_path / "carvit-check.json").write_text("{}", encoding="utf-8")
    assert ls.cmd_status(tmp_path) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["name"] == "carvit-check" and rows[0]["age_days"] is not None


def test_check_without_state_exits_2(tmp_path):
    assert ls.cmd_check("nope", "http://127.0.0.1:1/", base=tmp_path) == 2


class App(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        authed = "sid=ok" in (self.headers.get("Cookie") or "")
        if self.path.startswith("/home"):
            if authed:
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
                self.wfile.write("<html><body>대시보드</body></html>".encode("utf-8"))
            else:
                self.send_response(302); self.send_header("Location", "/login"); self.end_headers()
        else:
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<html><body>로그인</body></html>".encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), App)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_headless_check_live_and_expired(tmp_path, server):
    pytest.importorskip("playwright")
    good = {"cookies": [{"name": "sid", "value": "ok", "domain": "127.0.0.1", "path": "/", "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"}], "origins": []}
    bad = {"cookies": [], "origins": []}
    (tmp_path / "good.json").write_text(json.dumps(good), encoding="utf-8")
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    assert ls.cmd_check("good", server + "/home", base=tmp_path) == 0
    assert ls.cmd_check("bad", server + "/home", base=tmp_path) == 3
