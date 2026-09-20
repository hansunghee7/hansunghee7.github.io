"""
YouTube Analytics 읽기 권한을 한 번 받아 GitHub Secret 3개로 저장하는 로컬 1회용 도구(2026-09-21).

사용: python scripts/youtube_analytics_auth.py <구글에서 받은 client_secret JSON 경로>
동작: 브라우저에서 구글 동의 화면을 띄움 -> 사장님이 채널 계정으로 로그인해 "허용" -> 이 컴퓨터의
      127.0.0.1 임시 주소로 코드가 돌아옴 -> 갱신 토큰으로 바꿈 -> 시험 조회 1회 -> gh로 Secret 저장.
값(클라이언트 비밀, 갱신 토큰)은 화면·로그에 출력하지 않는다. 사람도 AI도 값을 보지 않는 것이 이 도구의 목적이다.
범위: yt-analytics.readonly 하나(읽기 전용, 수익 범위 없음).
"""
import http.server
import json
import secrets
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, timedelta

REPO = "hansunghee7/hansunghee7.github.io"
SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def load_client(path):
    d = json.load(open(path, encoding="utf-8"))
    c = d.get("installed") or d.get("web")
    if not c or "client_id" not in c or "client_secret" not in c:
        sys.exit("[ERROR] client_secret JSON 형식이 아님. OAuth 클라이언트 유형 '데스크톱 앱'으로 만든 JSON인지 확인")
    return c["client_id"], c["client_secret"]


def wait_for_code(port_holder, state):
    result = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                result["code"] = q["code"][0]
                msg = "완료되었습니다. 이 창을 닫고 터미널로 돌아가세요."
            else:
                result["error"] = q.get("error", ["state 불일치"])[0]
                msg = "실패했습니다. 터미널을 확인하세요."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    port_holder.append(srv.server_address[1])
    t = threading.Thread(target=srv.handle_request)
    t.start()
    return srv, t, result


def gh_set(name, value):
    r = subprocess.run(["gh", "secret", "set", name, "--repo", REPO], input=value, text=True, capture_output=True)
    if r.returncode != 0:
        sys.exit(f"[ERROR] {name} 저장 실패: {r.stderr.strip()[:200]}")
    print(f"저장됨: {name}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    client_id, client_secret = load_client(sys.argv[1])
    state = secrets.token_urlsafe(16)
    port = []
    srv, t, result = wait_for_code(port, state)
    redirect = f"http://127.0.0.1:{port[0]}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent", "state": state})
    print("브라우저가 열립니다. 채널 주인 계정으로 로그인해 '허용'을 누르세요. 안 열리면 아래 주소를 복사해 여세요:")
    print(url)
    webbrowser.open(url)
    t.join(timeout=300)
    srv.server_close()
    if "code" not in result:
        sys.exit(f"[ERROR] 코드를 못 받음: {result.get('error', '시간 초과')}")

    data = urllib.parse.urlencode({"code": result["code"], "client_id": client_id, "client_secret": client_secret,
                                   "redirect_uri": redirect, "grant_type": "authorization_code"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as r:
        tok = json.load(r)
    if "refresh_token" not in tok:
        sys.exit("[ERROR] 갱신 토큰이 안 옴. 구글 계정 > 보안 > 서드파티 앱 접근에서 이 앱을 제거한 뒤 다시 실행")

    end = date.today() - timedelta(days=1)
    q = urllib.parse.urlencode({"ids": "channel==MINE", "startDate": (end - timedelta(days=27)).isoformat(),
                                "endDate": end.isoformat(), "metrics": "views,estimatedMinutesWatched"})
    req = urllib.request.Request("https://youtubeanalytics.googleapis.com/v2/reports?" + q,
                                 headers={"Authorization": f"Bearer {tok['access_token']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r).get("rows", [[0, 0]])
    print(f"시험 조회 성공: 최근 28일 조회수 {rows[0][0]}, 시청 분 {rows[0][1]}")

    gh_set("YT_ANALYTICS_CLIENT_ID", client_id)
    gh_set("YT_ANALYTICS_CLIENT_SECRET", client_secret)
    gh_set("YT_ANALYTICS_REFRESH_TOKEN", tok["refresh_token"])
    print("끝. 값은 출력하지 않았습니다. client_secret JSON 파일은 지워도 됩니다.")


if __name__ == "__main__":
    main()
