"""
유튜브 숏폼 채널·콘텐츠 성과를 매일 수집해 assets/data/youtube-insight.json에
날짜별로 쌓는다. YouTube Data API v3(공식, 무료 쿼터)를 쓴다 -- 로그인 세션이
필요 없는 공개 데이터라 스크래핑 대신 API로 간다. 외부 라이브러리 없이
표준 라이브러리(urllib)만 쓴다 -- 다른 수집 스크립트와 달리 Playwright가
필요 없어 워크플로가 더 가볍다.

## 왜 채널 단위가 아니라 영상 단위까지 쌓는가
sns-insight.html·book-insight.html은 "채널/책 단위로 하루 한 값"인데,
사장님이 원하는 건 "이 숏츠가 실제로 얼마나 봤는지"까지다(2026-09-01
요청, docs/진행상황.md 참고). 그래서 이 파일은 영상(숏츠)마다 별도
history 배열을 갖는 한 겹 더 깊은 구조다.

## 무엇을 "숏츠"로 보는가
YouTube API에 공식 isShort 필드가 없다. 영상 길이(duration) 61초 이하를
숏츠로 본다 -- 느슨한 기준이라 61초를 살짝 넘는 롱폼 숏츠는 놓칠 수 있지만,
API가 제공하는 값만으로 판별 가능한 가장 신뢰도 높은 근사치다.

## 왜 최근 N개만 추적하는가
채널의 모든 과거 영상을 매일 다시 조회하면 API 쿼터·JSON 크기가 계속
불어난다. 최근 업로드 100개(숏츠 아닌 것 포함해 페이지네이션 기준)만
훑어서, 그중 숏츠만 추적한다 -- 숏츠 성과는 보통 게시 후 며칠 안에
대부분 결정되므로 오래된 영상을 매일 다시 볼 실익이 적다.

## 인증
YOUTUBE_API_KEY 하나만 필요하다(Google Cloud Console에서 YouTube Data
API v3 활성화 후 API 키 발급, 값은 대화로 주고받지 말고 GitHub Secrets
화면에 사장님이 직접 붙여넣을 것). 공개 통계 조회라 OAuth·서비스 계정
불필요 -- IP 제한 없이 API 키만 있으면 되므로 GitHub Actions 러너에서
바로 쓸 수 있다.

## 설계 원칙 (다른 fetch_*.py와 동일)
- 채널 정보·영상 목록 중 하나가 실패해도 나머지는 최대한 진행한다.
- 날짜는 KST 기준(자정 근처 실행이 "어제"로 잘못 잡히는 사고 재발 방지 --
  fetch_book_insight.py에서 실제로 겪었던 버그와 동일한 이유).
- 값을 못 읽으면 그 항목은 건너뛴다 -- 0/null로 덮어쓰지 않는다.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KST = timezone(timedelta(hours=9))
API_KEY = os.environ.get("YOUTUBE_API_KEY")
CHANNEL_HANDLE = "sinkihanapt"  # 신기한 아파트사전. @ 없이.
OUT_PATH = os.path.join("assets", "data", "youtube-insight.json")
MAX_SCANNED_UPLOADS = 100
MAX_SHORT_SECONDS = 61

API_BASE = "https://www.googleapis.com/youtube/v3"


def log(*a):
    print(*a, flush=True)


def api_get(path, params):
    params = dict(params)
    params["key"] = API_KEY
    url = API_BASE + "/" + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YouTube API {e.code}: {body[:300]}") from e


def parse_duration_seconds(iso_duration):
    """ISO 8601 duration(예: 'PT45S', 'PT1M3S')을 초로 변환."""
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso_duration or "")
    if not m:
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def get_channel():
    data = api_get("channels", {
        "part": "id,snippet,statistics,contentDetails",
        "forHandle": CHANNEL_HANDLE,
    })
    items = data.get("items") or []
    if not items:
        raise RuntimeError(f"채널을 찾을 수 없습니다: @{CHANNEL_HANDLE}")
    return items[0]


def list_recent_video_ids(uploads_playlist_id, limit):
    ids = []
    page_token = None
    while len(ids) < limit:
        params = {"part": "contentDetails", "playlistId": uploads_playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = api_get("playlistItems", params)
        for item in data.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                ids.append(vid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids[:limit]


def get_videos_details(video_ids):
    """videos.list는 한 번에 최대 50개 id만 받는다 -- 배치로 나눠 호출."""
    details = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = api_get("videos", {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch),
        })
        for item in data.get("items", []):
            details[item["id"]] = item
    return details


def upsert(history, today, entry):
    """같은 날짜 기록이 이미 있으면 갱신, 없으면 추가 후 날짜순 정렬."""
    for i, e in enumerate(history):
        if e.get("date") == today:
            history[i] = entry
            return
    history.append(entry)
    history.sort(key=lambda e: e.get("date", ""))


def main():
    if not API_KEY:
        log("YOUTUBE_API_KEY가 없습니다. 종료합니다.")
        sys.exit(1)

    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    captured_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    data = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("videos", {})
    data.setdefault("channel", {"handle": "@" + CHANNEL_HANDLE, "history": []})

    try:
        channel = get_channel()
    except Exception as e:
        log(f"채널 정보 수집 실패 — {type(e).__name__}: {e}")
        channel = None

    if channel:
        stats = channel.get("statistics", {})
        data["channel"]["title"] = channel.get("snippet", {}).get("title")
        data["channel"]["id"] = channel.get("id")
        try:
            entry = {
                "date": today,
                "subscribers": int(stats["subscriberCount"]),
                "total_views": int(stats["viewCount"]),
                "video_count": int(stats["videoCount"]),
            }
            upsert(data["channel"]["history"], today, entry)
            log(f"채널: 구독자 {entry['subscribers']:,} / 총 조회수 {entry['total_views']:,}")
        except (KeyError, ValueError) as e:
            log(f"채널 통계 파싱 실패 — {e}")

        uploads_playlist = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        if uploads_playlist:
            try:
                video_ids = list_recent_video_ids(uploads_playlist, MAX_SCANNED_UPLOADS)
                details = get_videos_details(video_ids)
                short_count = 0
                for vid, item in details.items():
                    duration = parse_duration_seconds(item.get("contentDetails", {}).get("duration"))
                    if duration is None or duration > MAX_SHORT_SECONDS:
                        continue  # 숏츠가 아니면 건너뜀(롱폼은 이 페이지 범위 밖)
                    short_count += 1
                    snippet = item.get("snippet", {})
                    vstats = item.get("statistics", {})
                    v = data["videos"].setdefault(vid, {"history": []})
                    v["title"] = snippet.get("title")
                    v["published_at"] = snippet.get("publishedAt")
                    thumbs = snippet.get("thumbnails", {})
                    v["thumbnail"] = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
                    v["duration_seconds"] = duration
                    try:
                        entry = {
                            "date": today,
                            "views": int(vstats.get("viewCount", 0)),
                            "likes": int(vstats["likeCount"]) if "likeCount" in vstats else None,
                            "comments": int(vstats["commentCount"]) if "commentCount" in vstats else None,
                        }
                        upsert(v["history"], today, entry)
                    except ValueError:
                        pass
                log(f"영상: 최근 업로드 {len(video_ids)}개 중 숏츠 {short_count}개 갱신")
            except Exception as e:
                log(f"영상 목록 수집 실패 — {type(e).__name__}: {e}")

    data["updated_at"] = captured_at
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log(f"저장 완료 → {OUT_PATH}")


if __name__ == "__main__":
    main()
