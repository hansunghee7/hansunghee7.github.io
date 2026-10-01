"""유튜브 Analytics API 실측(2026-10-01, N103): 저장된 리프레시 토큰으로 유지율·구독 전환이 읽히는지 숫자만 출력한다.
사용: python yt_analytics_probe.py [token.json 경로]   (비밀값은 출력하지 않는다)
"""
import json, sys, urllib.parse, urllib.request
from datetime import date, timedelta
from pathlib import Path

tok = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "C:/work/_ops/yt_oauth/token.json").read_text(encoding="utf-8"))


def post(url, data):
    with urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(data).encode()), timeout=30) as r:
        return json.load(r)


def get(url, access, **p):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(p), headers={"Authorization": "Bearer " + access})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")


acc = post("https://oauth2.googleapis.com/token", {"client_id": tok["client_id"], "client_secret": tok["client_secret"], "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})["access_token"]
print("access token ok")
end = date.today() - timedelta(days=2)  # 정산 지연 2일
start = end - timedelta(days=28)
A = "https://youtubeanalytics.googleapis.com/v2/reports"
s, d = get(A, acc, ids="channel==MINE", startDate=str(start), endDate=str(end), dimensions="video", metrics="views,estimatedMinutesWatched,averageViewPercentage,subscribersGained,subscribersLost", sort="-views", maxResults=10)
print("per-video report status", s, "rows", len(d.get("rows", [])) if s == 200 else d.get("error", {}).get("message"))
rows = d.get("rows", []) if s == 200 else []
for r in rows[:5]:
    print("  video", r[0][:4] + "..", "views", r[1], "avg view %", round(r[3], 1), "subs gained", r[4], "lost", r[5])
if rows:
    s2, d2 = get(A, acc, ids="channel==MINE", startDate=str(start), endDate=str(end), dimensions="elapsedVideoTimeRatio", metrics="audienceWatchRatio,relativeRetentionPerformance", filters="video==" + rows[0][0])
    print("retention curve status", s2, "points", len(d2.get("rows", [])) if s2 == 200 else d2.get("error", {}).get("message"))
    if s2 == 200 and d2.get("rows"):
        pts = d2["rows"]
        print("  retention at 0%, 50%, 100%:", round(pts[0][1], 2), round(pts[len(pts) // 2][1], 2), round(pts[-1][1], 2))
