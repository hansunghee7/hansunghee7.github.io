"""
브런치 공개 프로필 페이지(https://brunch.co.kr/@simplifier)를 읽어서
팔로워 수·발행 글 수를 assets/data/sns-insight.json에 날짜별로 기록한다.

브런치는 로그인이나 JS 실행 없이도 프로필 페이지의 HTML 안에
followerCount/articleCount가 그대로 들어있어(직접 확인함), 다른
SNS(크롬 확장으로 수집)와 달리 서버에서 바로 읽을 수 있다.

같은 날 여러 번 돌아도 그날 값을 덮어쓸 뿐 중복으로 쌓이지 않는다
(idempotent) -- publish-pipeline.yml의 다른 스크립트들과 같은 원칙.
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

PROFILE_URL = "https://brunch.co.kr/@simplifier"
OUT_PATH = "assets/data/sns-insight.json"


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_counts(html):
    follower_m = re.search(r'"followerCount":(\d+)', html)
    article_m = re.search(r'"articleCount":(\d+)', html)
    if not follower_m:
        raise RuntimeError("followerCount를 못 찾았습니다 -- 브런치가 페이지 구조를 바꿨을 수 있습니다.")
    return {
        "followers": int(follower_m.group(1)),
        "articles": int(article_m.group(1)) if article_m else None,
    }


def upsert(series, today, count):
    for entry in series:
        if entry["date"] == today:
            entry["count"] = count
            return
    series.append({"date": today, "count": count})
    series.sort(key=lambda e: e["date"])


def main():
    html = fetch_html(PROFILE_URL)
    counts = extract_counts(html)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    data = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.setdefault("brunch", [])
    upsert(data["brunch"], today, counts["followers"])

    if counts["articles"] is not None:
        data.setdefault("brunch_articles", [])
        upsert(data["brunch_articles"], today, counts["articles"])

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("브런치 팔로워 {}명, 발행 글 {}편 기록됨 ({})".format(
        counts["followers"], counts["articles"], today))


if __name__ == "__main__":
    main()
