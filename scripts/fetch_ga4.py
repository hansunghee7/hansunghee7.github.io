"""
GA4 Data API에서 최근 30일 방문 지표를 가져와 assets/data/analytics.json으로
저장하는 스크립트. 비공개 대시보드(insight-7b3e9f2c/)가 이 파일을 그대로
읽어서 화면에 그린다 -- posts.json과 같은 패턴 (수집은 여기서, 화면은 정적
JS가 fetch해서 그린다).

KPI가 "리드 가능성 높은 예비고객의 최초·재방문"이라, 여기서 뽑는 지표도
그 기준에 맞춘다:
  - 전체 세션/사용자, 신규 vs 재방문 (재방문 = KPI 그 자체)
  - 트래픽 소스 상위 목록과, 그중 AI 엔진(ChatGPT/Perplexity/Gemini 등)에서
    온 세션만 따로 -- GEO/AEO가 실제로 유입을 만드는지 보는 지표
  - _includes/site-analytics.html에 이미 심어둔 관여 신호 이벤트
    (section_view_*, faq_open, read_complete) 발생 횟수

인증 정보(서비스 계정 키)는 절대 이 저장소나 대화에 남기지 않는다 -- GitHub
Actions Secrets에서 환경변수로만 주입받는다. 로컬에서 테스트할 때도 같은
환경변수를 셸에 export해서 쓰고, 파일로 저장해두지 말 것.
"""
import json
import os
import sys
from datetime import datetime, timezone

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

OUT_PATH = "assets/data/analytics.json"

# GA4 sessionSource로 잡히는 값 기준. 정확한 매칭이 아니라 부분 포함으로
# 검사한다 -- 플랫폼마다 리퍼러 형식이 조금씩 다르기 때문 (예: 'chatgpt.com',
# 'chat.openai.com' 둘 다 씀).
AI_SOURCE_MARKERS = [
    "chatgpt.com", "chat.openai.com", "openai.com",
    "perplexity.ai", "gemini.google.com", "bard.google.com",
    "copilot.microsoft.com", "claude.ai", "you.com", "phind.com",
]

ENGAGEMENT_EVENTS = [
    "section_view_proven", "section_view_voices",
    "section_view_book_class", "section_view_faq",
    "faq_open", "read_complete",
]


def get_client():
    key_json = os.environ.get("GA4_SERVICE_ACCOUNT_JSON")
    if not key_json:
        sys.exit("GA4_SERVICE_ACCOUNT_JSON 환경변수가 없습니다.")
    info = json.loads(key_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    return BetaAnalyticsDataClient(credentials=creds)


def run_report(client, property_id, **kwargs):
    request = RunReportRequest(property=f"properties/{property_id}", **kwargs)
    return client.run_report(request)


def fetch_totals(client, property_id):
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        metrics=[Metric(name="sessions"), Metric(name="activeUsers"), Metric(name="newUsers")],
    )
    if not resp.rows:
        return {"sessions": 0, "activeUsers": 0, "newUsers": 0, "returningUsers": 0}
    row = resp.rows[0]
    sessions = int(row.metric_values[0].value)
    active = int(row.metric_values[1].value)
    new = int(row.metric_values[2].value)
    return {
        "sessions": sessions,
        "activeUsers": active,
        "newUsers": new,
        "returningUsers": max(active - new, 0),
    }


def fetch_daily(client, property_id):
    """AARRR 상단 KPI(최초방문→재방문→문의)의 앞 두 단계용 일별 시계열.
    activeUsers - newUsers = 그날의 재방문자. 음수 방지로 0 하한."""
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="sessions"), Metric(name="activeUsers"), Metric(name="newUsers")],
    )
    rows = []
    for r in resp.rows:
        d = r.dimension_values[0].value  # YYYYMMDD
        active = int(r.metric_values[1].value)
        new = int(r.metric_values[2].value)
        rows.append({
            "date": f"{d[0:4]}-{d[4:6]}-{d[6:8]}",
            "sessions": int(r.metric_values[0].value),
            "activeUsers": active,
            "newUsers": new,
            "returningUsers": max(active - new, 0),
        })
    rows.sort(key=lambda x: x["date"])
    return rows


def fetch_daily_event(client, property_id, event_name):
    """AARRR 상단 KPI의 마지막 단계(문의)용 일별 이벤트 발생 횟수.
    eventName 차원에 필터를 걸어 해당 이벤트만 날짜별로 집계한다."""
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value=event_name),
            )
        ),
    )
    rows = []
    for r in resp.rows:
        d = r.dimension_values[0].value
        rows.append({
            "date": f"{d[0:4]}-{d[4:6]}-{d[6:8]}",
            "count": int(r.metric_values[0].value),
        })
    rows.sort(key=lambda x: x["date"])
    return rows


def fetch_event_totals(client, property_id, event_names):
    """지정한 이벤트들의 최근 30일 총 발생 횟수를 한 번에. 문의 퍼널(모달 열림→
    제출→실패)처럼 여러 이벤트를 나란히 비교할 때 쓴다."""
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="eventName",
                in_list_filter=Filter.InListFilter(values=event_names),
            )
        ),
    )
    counts = {name: 0 for name in event_names}
    for r in resp.rows:
        name = r.dimension_values[0].value
        if name in counts:
            counts[name] = int(r.metric_values[0].value)
    return counts


def load_post_titles():
    """posts.json에서 URL→제목 매핑을 만든다. GA4는 랜딩페이지를 경로로만 주기
    때문에, 어떤 글이 문의로 이어졌는지 사람이 읽을 수 있는 제목으로 보여주려면
    필요하다. 파일이 없거나 형식이 다르면 빈 매핑으로 조용히 넘어간다."""
    try:
        with open("assets/data/posts.json", encoding="utf-8") as f:
            posts = json.load(f)
        if isinstance(posts, dict):
            posts = posts.get("posts", [])
        return {p.get("url", ""): p.get("title", "") for p in posts if p.get("url")}
    except Exception:
        return {}


def fetch_leads_by_landing_page(client, property_id, title_map):
    """실제로 문의(generate_lead)로 이어진 세션이 어느 페이지에 착지했었는지.
    콘텐츠 자산(재고 586건)과 실제 성과를 잇는 연결고리 -- 어떤 글이 진짜
    기여하는지는 지금까지 전혀 안 보였다."""
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="landingPage")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value="generate_lead"),
            )
        ),
        limit=20,
    )
    rows = []
    for r in resp.rows:
        path = r.dimension_values[0].value or ""
        count = int(r.metric_values[0].value)
        title = title_map.get(path)
        if not title:
            if path in ("/", ""):
                title = "홈"
            elif path.startswith("/log.html"):
                title = "로그 목록"
            else:
                title = path
        rows.append({"path": path, "title": title, "count": count})
    rows.sort(key=lambda x: -x["count"])
    return rows


def fetch_top_landing_posts(client, property_id, title_map):
    """개별 글이 랜딩(첫 착지)으로 얼마나 쓰였는지 상위 목록 -- 전환(문의) 여부와
    무관하게 어떤 글이 실제로 사람을 데려오는지. leads_by_post는 문의로 이어진
    것만 보여주므로, 이건 그보다 앞단(유입 자체)의 순위표다."""
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="landingPage")],
        metrics=[Metric(name="sessions")],
        limit=500,
    )
    rows = []
    for r in resp.rows:
        path = r.dimension_values[0].value or ""
        if not path.startswith("/log_assets/markdown/"):
            continue  # 개별 글만 -- 홈/로그목록/기타 비중은 landing_types에서 이미 다룬다
        sessions = int(r.metric_values[0].value)
        rows.append({"path": path, "title": title_map.get(path, path), "sessions": sessions})
    rows.sort(key=lambda x: -x["sessions"])
    return rows[:15]


def fetch_landing_types(client, property_id):
    """방문자가 처음 착지하는 곳이 홈 / 로그 홈(목록) / 개별 글 중 어디인지.
    최초방문을 만드는 또 다른 축 -- GEO/AEO 유입은 홈이 아니라 특정 글로 바로
    착지할 가능성이 높으므로, 소스만으로는 안 보이는 걸 여기서 잡는다."""
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="landingPage")],
        metrics=[Metric(name="sessions")],
        limit=500,
    )
    buckets = {"home": 0, "log_home": 0, "individual_post": 0, "other": 0}
    for r in resp.rows:
        path = r.dimension_values[0].value or ""
        sessions = int(r.metric_values[0].value)
        if path in ("/", ""):
            buckets["home"] += sessions
        elif path.startswith("/log.html"):
            buckets["log_home"] += sessions
        elif path.startswith("/log_assets/markdown/"):
            buckets["individual_post"] += sessions
        else:
            buckets["other"] += sessions
    return buckets


def fetch_sources(client, property_id):
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="sessionSource")],
        metrics=[Metric(name="sessions")],
        limit=25,
    )
    top = []
    ai_hits = []
    for r in resp.rows:
        source = r.dimension_values[0].value
        sessions = int(r.metric_values[0].value)
        entry = {"source": source, "sessions": sessions}
        top.append(entry)
        if any(marker in source.lower() for marker in AI_SOURCE_MARKERS):
            ai_hits.append(entry)
    top.sort(key=lambda x: -x["sessions"])
    ai_hits.sort(key=lambda x: -x["sessions"])
    return top[:15], ai_hits


def fetch_engagement_events(client, property_id):
    resp = run_report(
        client, property_id,
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        limit=50,
    )
    counts = {name: 0 for name in ENGAGEMENT_EVENTS}
    for r in resp.rows:
        name = r.dimension_values[0].value
        if name in counts:
            counts[name] = int(r.metric_values[0].value)
    return counts


def main():
    property_id = os.environ.get("GA4_PROPERTY_ID")
    if not property_id:
        sys.exit("GA4_PROPERTY_ID 환경변수가 없습니다.")

    client = get_client()
    top_sources, ai_referrals = fetch_sources(client, property_id)
    title_map = load_post_titles()

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "range": "last_30_days",
        "totals": fetch_totals(client, property_id),
        "daily": fetch_daily(client, property_id),
        "daily_leads": fetch_daily_event(client, property_id, "generate_lead"),
        "landing_types": fetch_landing_types(client, property_id),
        "top_sources": top_sources,
        "ai_referrals": ai_referrals,
        "engagement_events": fetch_engagement_events(client, property_id),
        "contact_funnel": fetch_event_totals(client, property_id, ["contact_open", "generate_lead", "contact_error"]),
        "leads_by_post": fetch_leads_by_landing_page(client, property_id, title_map),
        "top_landing_posts": fetch_top_landing_posts(client, property_id, title_map),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
