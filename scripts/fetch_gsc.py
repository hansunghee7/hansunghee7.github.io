"""
Google Search Console(서치콘솔) Search Analytics API에서 검색 성과를 가져와
assets/data/search-console.json으로 저장하는 스크립트. fetch_ga4.py와 같은
패턴 -- 수집은 여기서, 화면은 스튜디오(insight-7b3e9f2c/)의 정적 JS가 그린다.

왜 필요한가(2026-08-30 CMO 논의): 실사용자 월 40명·실제 문의 0건 상황에서
가장 먼저 판별할 것이 "구글에 노출 자체가 안 되는가(색인 문제) vs 노출은
되는데 클릭을 못 받는가(제목·검색어 미스매치)"이고, 그 답은 서치콘솔
실적 데이터에만 있다. 그래서 뽑는 지표도 그 질문에 맞춘다:
  - 전체 노출/클릭/CTR/평균순위 (28일·90일 두 창 -- 트래픽이 적어 90일도 본다)
  - 일별 시계열 (노출이 늘고 있는지 방향)
  - 상위 검색어 -- 어떤 질문으로 우리가 발견되는지 (AEO 리라이트 대상 선정 근거)
  - 상위 페이지 -- 어떤 글이 검색 유입을 만드는지
  - 기기·국가 분포 (참고용)

인증은 GA4와 같은 서비스 계정을 재사용한다(GA4_SERVICE_ACCOUNT_JSON).
사장님이 서치콘솔 "사용자 및 권한"에 이 서비스 계정 이메일을 추가해야
작동한다. 속성 URL은 하드코딩하지 않고 sites().list()로 서비스 계정이
접근 가능한 속성 중 simplifier.co.kr을 찾는다 -- 도메인 속성(sc-domain:)인지
URL 접두어 속성인지 미리 알 필요가 없게 하기 위해서다.

서치콘솔 데이터는 약 2일 지연되므로 end_date를 이틀 전으로 잡는다.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

OUT_PATH = "assets/data/search-console.json"
SITE_MARKER = "simplifier.co.kr"


def get_service():
    key_json = os.environ.get("GA4_SERVICE_ACCOUNT_JSON")
    if not key_json:
        sys.exit("GA4_SERVICE_ACCOUNT_JSON 환경변수가 없습니다.")
    info = json.loads(key_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def find_site_url(service):
    entries = service.sites().list().execute().get("siteEntry", [])
    candidates = [e["siteUrl"] for e in entries if SITE_MARKER in e.get("siteUrl", "")]
    if not candidates:
        sys.exit(
            f"서비스 계정이 접근할 수 있는 속성 중 {SITE_MARKER}가 없습니다. "
            "서치콘솔 '설정 > 사용자 및 권한'에 서비스 계정 이메일이 추가됐는지, "
            "권한이 충분한지(403이면 소유자로 승격) 확인하세요."
        )
    # 도메인 속성(sc-domain:)이 URL 접두어 속성보다 커버 범위가 넓으니 우선한다.
    candidates.sort(key=lambda u: 0 if u.startswith("sc-domain:") else 1)
    return candidates[0]


def query(service, site_url, start_date, end_date, dimensions=None, row_limit=50):
    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "rowLimit": row_limit,
    }
    if dimensions:
        body["dimensions"] = dimensions
    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    return resp.get("rows", [])


def summarize(rows):
    """차원 없는 질의는 rows가 0~1개다. 노출 0이면 색인 문제라는 신호."""
    if not rows:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    r = rows[0]
    return {
        "clicks": int(r.get("clicks", 0)),
        "impressions": int(r.get("impressions", 0)),
        "ctr": round(r.get("ctr", 0.0), 4),
        "position": round(r.get("position", 0.0), 1),
    }


def keyed_rows(rows, key_name):
    out = []
    for r in rows:
        keys = r.get("keys", [])
        out.append({
            key_name: keys[0] if keys else "",
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round(r.get("ctr", 0.0), 4),
            "position": round(r.get("position", 0.0), 1),
        })
    out.sort(key=lambda x: (-x["impressions"], -x["clicks"]))
    return out


def main():
    service = get_service()
    site_url = find_site_url(service)

    end = datetime.now(timezone.utc).date() - timedelta(days=2)
    start_28 = end - timedelta(days=27)
    start_90 = end - timedelta(days=89)

    daily = keyed_rows(query(service, site_url, start_90, end, ["date"], row_limit=100), "date")
    daily.sort(key=lambda x: x["date"])

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "site_url": site_url,
        "data_delay_note": "서치콘솔 데이터는 약 2일 지연 -- end_date는 이틀 전",
        "totals_28d": summarize(query(service, site_url, start_28, end)),
        "totals_90d": summarize(query(service, site_url, start_90, end)),
        "daily_90d": daily,
        "top_queries_90d": keyed_rows(query(service, site_url, start_90, end, ["query"], row_limit=50), "query"),
        "top_pages_90d": keyed_rows(query(service, site_url, start_90, end, ["page"], row_limit=30), "page"),
        "by_device_90d": keyed_rows(query(service, site_url, start_90, end, ["device"], row_limit=5), "device"),
        "by_country_90d": keyed_rows(query(service, site_url, start_90, end, ["country"], row_limit=10), "country"),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH} (site: {site_url})")


if __name__ == "__main__":
    main()
