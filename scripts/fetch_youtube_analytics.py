"""
유튜브 채널의 시청 지속률·유입 경로 같은 "공개 API에 없는" 분석 수치를 YouTube Analytics API로
가져와 assets/data/youtube-analytics.json에 날짜별 스냅샷으로 쌓는다(2026-09-21, 사장님 지시).

## 왜 fetch_youtube.py와 따로인가
fetch_youtube.py는 로그인 없이 API 키 하나로 읽는 공개 통계(조회수, 좋아요, 댓글)다.
지속률·시청 시간·유입 경로는 채널 주인의 동의(OAuth)가 있어야 읽히는 비공개 분석이라
인증 방식이 달라 스크립트를 나눴다. Studio 화면을 로그인 세션으로 긁는 대신 공식 API를 쓴다.

## 인증
저장소 Secret 3개(YT_ANALYTICS_CLIENT_ID, YT_ANALYTICS_CLIENT_SECRET, YT_ANALYTICS_REFRESH_TOKEN).
값은 scripts/youtube_analytics_auth.py가 동의 화면 통과 직후 gh로 직접 저장한다(사람도 AI도 값을 못 본다).
범위는 읽기 전용 yt-analytics.readonly 하나뿐이다(수익 범위는 요청하지 않는다).
동의 화면이 "테스트" 상태면 갱신 토큰이 7일 만에 죽는다. 반드시 "프로덕션(게시)"으로 둘 것.

## API가 못 주는 것
Studio의 "노출수, 노출 클릭률"은 API에 없다(문서 확인 2026-09-21). 그 둘은 화면 읽기(파일럿)로만 얻는다.
채널 분석 데이터는 2~3일 늦게 확정된다. 그래서 종료일은 어제로 잡고, 최근 이틀 값은 다음 실행에서 바뀔 수 있다.

## 설계 원칙 (다른 fetch_*.py와 동일)
- 보고서 하나가 실패해도 나머지는 진행한다. 실패한 보고서는 0/null로 덮지 않고 건너뛴다.
- 날짜는 KST 기준.
- 지표 조합을 API가 거절하면(400) 핵심 지표만으로 한 번 더 시도한다(지원 조합은 실측으로 확인).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KST = timezone(timedelta(hours=9))
OUT_PATH = os.environ.get("YT_ANALYTICS_OUT", os.path.join("assets", "data", "youtube-analytics.json"))
TOKEN_URL = "https://oauth2.googleapis.com/token"
REPORT_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
WINDOW_DAYS = 28
KEEP_SNAPSHOTS = 90

VIDEO_METRICS = ["views", "engagedViews", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
                 "likes", "comments", "shares", "subscribersGained"]
VIDEO_METRICS_CORE = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage"]
DAILY_METRICS = ["views", "engagedViews", "estimatedMinutesWatched", "averageViewPercentage", "subscribersGained"]
DAILY_METRICS_CORE = ["views", "estimatedMinutesWatched", "averageViewPercentage"]


def post_json(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_access_token(env=os.environ):
    return post_json(TOKEN_URL, {
        "client_id": env["YT_ANALYTICS_CLIENT_ID"],
        "client_secret": env["YT_ANALYTICS_CLIENT_SECRET"],
        "refresh_token": env["YT_ANALYTICS_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })["access_token"]


def query(token, params):
    url = REPORT_URL + "?" + urllib.parse.urlencode({"ids": "channel==MINE", **params})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rows_to_dicts(resp):
    """columnHeaders 순서대로 각 행을 {이름: 값} 사전으로 바꾼다. 행이 없으면 빈 목록."""
    names = [h["name"] for h in resp.get("columnHeaders", [])]
    return [dict(zip(names, row)) for row in resp.get("rows", [])]


def run_report(token, params, metric_sets, label):
    """지표 조합을 앞에서부터 시도한다. 400이면 다음(더 작은) 조합으로. 성공하면 (행 목록, 쓴 지표)."""
    for metrics in metric_sets:
        try:
            return rows_to_dicts(query(token, {**params, "metrics": ",".join(metrics)})), metrics
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            print(f"[{label}] HTTP {e.code} (지표 {len(metrics)}개): {body}")
            if e.code != 400:
                break
        except Exception as e:  # 토큰이 든 URL이 문구에 섞이지 않도록 종류만
            print(f"[{label}] 실패: {type(e).__name__}")
            break
    return None, None


def collect(token, today):
    end = today - timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    base = {"startDate": start.isoformat(), "endDate": end.isoformat()}
    snap = {"window": base, "reports": {}}

    videos, used = run_report(token, {**base, "dimensions": "video", "sort": "-views", "maxResults": 200},
                              [VIDEO_METRICS, VIDEO_METRICS_CORE], "영상별")
    if videos is not None:
        snap["reports"]["videos"] = videos
        snap["video_metrics"] = used
    traffic, _ = run_report(token, {**base, "dimensions": "insightTrafficSourceType", "sort": "-views"},
                            [["views", "estimatedMinutesWatched"], ["views"]], "유입 경로")
    if traffic is not None:
        snap["reports"]["traffic"] = traffic
    daily, used = run_report(token, {**base, "dimensions": "day", "sort": "day"},
                             [DAILY_METRICS, DAILY_METRICS_CORE], "일별")
    if daily is not None:
        snap["reports"]["daily"] = daily
        snap["daily_metrics"] = used
    return snap


def merge_snapshot(existing, date_key, snap, now_iso):
    """같은 날짜 스냅샷은 덮어쓰되, 이번에 못 가져온 보고서는 이전 값을 유지한다(0/null로 덮지 않는다)."""
    out = dict(existing) if existing else {}
    snaps = dict(out.get("snapshots", {}))
    prev = snaps.get(date_key, {})
    merged_reports = {**prev.get("reports", {}), **snap["reports"]}
    snaps[date_key] = {**prev, **snap, "reports": merged_reports}
    for old in sorted(snaps)[:-KEEP_SNAPSHOTS]:
        del snaps[old]
    out["snapshots"] = snaps
    out["updated"] = now_iso
    out["note"] = "YouTube Analytics API(OAuth, 읽기 전용). 노출수·노출 클릭률은 API에 없음. 최근 2~3일 값은 다음 수집에서 바뀔 수 있음."
    return out


def main():
    missing = [k for k in ("YT_ANALYTICS_CLIENT_ID", "YT_ANALYTICS_CLIENT_SECRET", "YT_ANALYTICS_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        print("[ERROR] Secret 누락:", ", ".join(missing))
        return 1
    try:
        token = get_access_token()
    except urllib.error.HTTPError as e:
        print(f"[ERROR] 토큰 갱신 실패 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        print("갱신 토큰이 만료·폐기됐을 수 있다(동의 화면이 테스트 상태면 7일). youtube_analytics_auth.py를 다시 실행할 것.")
        return 1
    now = datetime.now(KST)
    snap = collect(token, now.date())
    if not snap["reports"]:
        print("[ERROR] 보고서를 하나도 못 가져옴")
        return 1
    existing = {}
    if os.path.exists(OUT_PATH):
        try:
            existing = json.load(open(OUT_PATH, encoding="utf-8"))
        except (OSError, ValueError):
            print("[WARN] 기존 파일을 못 읽어 새로 시작")
    out = merge_snapshot(existing, now.date().isoformat(), snap, now.isoformat(timespec="seconds"))
    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    r = snap["reports"]
    print(f"OK 영상 {len(r.get('videos', []))}개, 유입 경로 {len(r.get('traffic', []))}종, 일별 {len(r.get('daily', []))}일 -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
