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

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "range": "last_30_days",
        "totals": fetch_totals(client, property_id),
        "daily": fetch_daily(client, property_id),
        "daily_leads": fetch_daily_event(client, property_id, "generate_lead"),
        "top_sources": top_sources,
        "ai_referrals": ai_referrals,
        "engagement_events": fetch_engagement_events(client, property_id),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
