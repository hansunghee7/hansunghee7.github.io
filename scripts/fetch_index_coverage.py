"""서치콘솔 URL 검사 API로 사이트맵의 모든 URL이 구글에 색인됐는지 확인한다.

왜 있나: 2026-09-02 진단에서 글 587편의 90일 구글 노출이 130회뿐이었다.
기술 SEO(사이트맵·canonical·JSON-LD)는 정상이라, "색인이 안 된 것인지 / 색인은
됐는데 순위가 없는 것인지"를 갈라야 다음 조치가 정해진다. 서치콘솔 화면의
"페이지 색인" 보고서는 API로 못 가져오지만, URL 검사 API는 URL 하나씩 같은
판정(verdict·coverageState)을 돌려준다. 사이트맵 600여 개면 한 번에 다 본다.

한도: 속성당 하루 2,000회, 분당 600회. 600개 URL이면 한 번 실행에 다 들어가고
남는다. 매일 돌릴 이유는 없다(색인은 주 단위로 움직임) — 주 1회 + 수동 실행.

인증: fetch_gsc.py와 같은 서비스 계정(GA4_SERVICE_ACCOUNT_JSON). URL 검사는
Search Console 속성의 "전체" 권한 사용자면 되고, webmasters.readonly 스코프로 동작한다.

출력: assets/data/index-coverage.json
  summary            — verdict / coverageState 별 URL 수
  posts_summary      — 글(log_assets/markdown)만 따로 센 것
  not_indexed_posts  — 색인 안 된 글 목록 (경로 · coverageState · 마지막 크롤)
  canonical_mismatch — 구글이 고른 canonical이 우리 URL과 다른 것 (중복 판정의 증거)
  urls               — 전 URL 판정 (경로 기준, 매주 비교용)
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

OUT_PATH = "assets/data/index-coverage.json"
SITEMAP_URL = "https://simplifier.co.kr/sitemap.xml"
SITE_MARKER = "simplifier.co.kr"
POST_PREFIX = "/log_assets/markdown/"
# 분당 600회 한도 — 0.15초 간격이면 분당 400회로 여유 있음
CALL_INTERVAL_SEC = 0.15


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
        sys.exit(f"서비스 계정이 접근할 수 있는 속성 중 {SITE_MARKER}가 없습니다.")
    candidates.sort(key=lambda u: 0 if u.startswith("sc-domain:") else 1)
    return candidates[0]


def load_sitemap_urls():
    with urllib.request.urlopen(SITEMAP_URL, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    if not urls:
        sys.exit("사이트맵에서 URL을 하나도 못 읽었습니다.")
    return urls


def path_of(url):
    return urllib.parse.unquote(urllib.parse.urlparse(url).path) or "/"


def inspect(service, site_url, url):
    body = {"inspectionUrl": url, "siteUrl": site_url}
    for attempt in range(3):
        try:
            res = service.urlInspection().index().inspect(body=body).execute()
            return res.get("inspectionResult", {}).get("indexStatusResult", {})
        except HttpError as e:
            # 429(한도)·5xx는 잠깐 쉬고 재시도, 나머지는 그 URL만 실패로 기록
            if e.resp.status in (429, 500, 502, 503) and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            return {"error": f"HTTP {e.resp.status}"}
    return {"error": "재시도 3회 실패"}


def main():
    service = get_service()
    site_url = find_site_url(service)
    urls = load_sitemap_urls()
    print(f"site: {site_url}, sitemap urls: {len(urls)}")

    results = []
    for i, url in enumerate(urls, 1):
        r = inspect(service, site_url, url)
        google_canonical = r.get("googleCanonical")
        results.append(
            {
                "path": path_of(url),
                "verdict": r.get("verdict", "ERROR" if "error" in r else "UNKNOWN"),
                "coverage_state": r.get("coverageState") or r.get("error"),
                "indexing_state": r.get("indexingState"),
                "last_crawl": r.get("lastCrawlTime"),
                "google_canonical": path_of(google_canonical) if google_canonical else None,
            }
        )
        if i % 50 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(CALL_INTERVAL_SEC)

    def count_by(items, key):
        out = {}
        for it in items:
            k = it.get(key) or "(없음)"
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    posts = [r for r in results if r["path"].startswith(POST_PREFIX)]
    not_indexed_posts = [
        {k: r[k] for k in ("path", "coverage_state", "last_crawl")}
        for r in posts
        if r["verdict"] != "PASS"
    ]
    canonical_mismatch = [
        {"path": r["path"], "google_canonical": r["google_canonical"]}
        for r in results
        if r["google_canonical"] and r["google_canonical"] != r["path"]
    ]

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "site_url": site_url,
        "sitemap_url_count": len(urls),
        "summary": {
            "by_verdict": count_by(results, "verdict"),
            "by_coverage_state": count_by(results, "coverage_state"),
        },
        "posts_summary": {
            "total": len(posts),
            "indexed": sum(1 for r in posts if r["verdict"] == "PASS"),
            "by_coverage_state": count_by(posts, "coverage_state"),
        },
        "not_indexed_posts": not_indexed_posts,
        "canonical_mismatch": canonical_mismatch,
        "urls": results,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH}")
    print("verdict:", data["summary"]["by_verdict"])
    print("posts indexed:", data["posts_summary"]["indexed"], "/", data["posts_summary"]["total"])


if __name__ == "__main__":
    main()
