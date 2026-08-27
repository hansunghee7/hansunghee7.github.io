"""
뉴스레터 주제 후보를 모으는 리서치 봇.

목적: 한 주제 키워드를 넣으면, 그 주제와 관련된 뉴스/유튜브 결과를
제목·요약·링크만 모아서 보여준다 (본문 스크래핑 없음 -- 저작권 안전).
최종 선별은 사람이 한다 -- 이 스크립트는 후보를 넓게 모아주는 역할까지만 한다.

뉴스레터 콘텐츠 원칙(대화에서 합의): "사용법"이 아니라 "Before→After 수치가
있는 사례"만 채택한다. 그래서 검색어에 결과 지향 단어(후기/시간 단축/효율/절감)를
같이 붙이고, 제목·요약에 숫자+단위(%, 배, 시간, 분, 원) 패턴이 있으면
hasNumberSignal=true로 표시해 우선순위를 매긴다. 이건 참고용 신호일 뿐이고,
실제로 진짜 성과 수치인지는 사람이 링크를 열어 확인해야 한다.

뉴스는 구글 뉴스 검색 RSS를 쓴다 -- API 키도, 회원가입도 필요 없다. (원래
네이버 검색 API를 썼는데, 네이버가 이걸 별도 유료 클라우드 플랫폼으로
이전시켜서 비개발자가 쓰기엔 가입 절차가 너무 무거워졌다. 구글 뉴스 RSS로
교체함.)

필요한 API 키 (선택, 없으면 유튜브만 건너뛴다):
  YOUTUBE_API_KEY  -- Google Cloud Console에서 발급 (무료 할당량으로 충분)

사용법:
  python scripts/research_newsletter_topics.py "회의록 자동화"

결과는 assets/data/newsletter_research.json에 주제별로 쌓인다(같은 주제로
다시 돌리면 그 주제 항목만 갱신). Simplifier Studio의 "뉴스레터 리서치" 탭이
이 파일을 그대로 읽어서 보여준다 -- 그래서 실행 후에는 이 파일을 커밋해야
탭에 반영된다. 비밀키(YOUTUBE_API_KEY)는 이 파일에 들어가지 않는다 --
결과로 나온 제목·요약·링크만 저장되므로 공개 저장소에 남겨도 안전하다.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape

import requests

OUT_PATH = "assets/data/newsletter_research.json"

# 검색어에 붙여서 "사용법"보다 "결과가 있는 사례"가 걸리도록 유도한다.
RESULT_ORIENTED_SUFFIXES = ["후기", "시간 단축", "효율", "사례", "절감"]

# 제목/요약에 이 패턴이 있으면 정량적 결과가 언급됐을 가능성이 높다고 본다.
# 어디까지나 힌트다 -- 진짜인지는 사람이 링크를 열어 확인해야 한다.
NUMBER_SIGNAL_RE = re.compile(
    r"\d+\s*(%|퍼센트|배|시간|분|원|건)\s*(이|가|로)?\s*(단축|절감|감소|증가|줄|늘|절약)"
    r"|(단축|절감|감소|증가|절약)\s*\d+\s*(%|퍼센트|배)"
    # "1시간을 5분으로 줄인"처럼 두 숫자(전/후)가 붙는 축소 관용구
    r"|\d+\s*(시간|분|원|건)\s*(을|를)?\s*.{0,12}?\d+\s*(시간|분|원|건)\s*(으로|로)?\s*(줄|단축|절감)"
)

TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s):
    return unescape(TAG_RE.sub("", s or "")).strip()


def has_number_signal(*texts):
    combined = " ".join(t or "" for t in texts)
    return bool(NUMBER_SIGNAL_RE.search(combined))


def fetch_google_news(topic):
    """구글 뉴스 검색 RSS. API 키도 회원가입도 필요 없다 -- URL 하나로 바로
    결과를 준다. 실패해도(네트워크 문제 등) 조용히 빈 목록을 돌려준다."""
    results = []
    seen_links = set()
    for suffix in [""] + RESULT_ORIENTED_SUFFIXES:
        query = f"{topic} {suffix}".strip()
        try:
            resp = requests.get(
                "https://news.google.com/rss/search",
                params={"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
                timeout=10,
            )
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            continue
        for item in root.findall(".//item"):
            link = (item.findtext("link") or "").strip()
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            title = (item.findtext("title") or "").strip()
            source_el = item.find("source")
            source_name = strip_tags(source_el.text) if source_el is not None and source_el.text else ""
            # 구글 뉴스는 제목 끝에 "- 언론사명"을 덧붙여 준다. channel로 따로
            # 보여줄 것이므로 제목에서는 중복을 떼어낸다.
            if source_name and title.endswith(f" - {source_name}"):
                title = title[: -(len(source_name) + 3)].strip()
            results.append({
                "source": "google_news",
                "title": title,
                "description": "",
                "link": link,
                "date": (item.findtext("pubDate") or "").strip(),
                "channel": source_name,
                "matchedQuery": query,
                "hasNumberSignal": has_number_signal(title),
            })
    return results


def fetch_youtube(topic):
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return []

    results = []
    seen_ids = set()
    for suffix in [""] + RESULT_ORIENTED_SUFFIXES:
        query = f"{topic} {suffix}".strip()
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 10,
                "order": "relevance",
                "relevanceLanguage": "ko",
                "key": api_key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            continue
        for item in resp.json().get("items", []):
            vid = item.get("id", {}).get("videoId")
            if not vid or vid in seen_ids:
                continue
            seen_ids.add(vid)
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            desc = snippet.get("description", "")
            results.append({
                "source": "youtube",
                "title": title,
                "description": desc,
                "link": f"https://www.youtube.com/watch?v={vid}",
                "date": snippet.get("publishedAt", ""),
                "channel": snippet.get("channelTitle", ""),
                "matchedQuery": query,
                "hasNumberSignal": has_number_signal(title, desc),
            })
    return results


def research(topic):
    rows = []
    rows += fetch_google_news(topic)
    rows += fetch_youtube(topic)
    # 숫자 신호가 있는 것부터 보이도록 정렬 (완전 제외는 하지 않음 -- 사람이 최종 판단)
    rows.sort(key=lambda r: not r["hasNumberSignal"])
    return rows


def load_existing(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("topics"), list):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"topics": []}


def upsert_topic(data, topic, rows):
    """같은 주제로 다시 실행하면 그 주제 항목만 최신 결과로 교체한다.
    나머지 주제(지난주 이전) 기록은 그대로 남아 탭에서 계속 보인다."""
    entry = {
        "topic": topic,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "results": rows,
    }
    data["topics"] = [t for t in data["topics"] if t.get("topic") != topic]
    data["topics"].insert(0, entry)
    return data


def print_report(topic, rows):
    signal_count = sum(1 for r in rows if r["hasNumberSignal"])
    print(f"\n=== '{topic}' 리서치 결과: {len(rows)}건 (숫자 신호 있음 {signal_count}건) ===\n")
    if not rows:
        print("검색 결과가 없습니다. 네트워크 문제이거나 정말 결과가 없을 수 있습니다. 유튜브까지 보려면 YOUTUBE_API_KEY 환경변수를 설정하세요.")
        return
    for r in rows:
        mark = "★" if r["hasNumberSignal"] else " "
        print(f"[{mark}] ({r['source']}) {r['title']}")
        if r.get("description"):
            print(f"    {r['description'][:100]}")
        print(f"    {r['link']}")
        print()


def main():
    if len(sys.argv) < 2:
        sys.exit('사용법: python scripts/research_newsletter_topics.py "주제 키워드"')
    topic = sys.argv[1]

    rows = research(topic)
    print_report(topic, rows)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    data = load_existing(OUT_PATH)
    data = upsert_topic(data, topic, rows)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"저장됨: {OUT_PATH}")
    print('이 파일을 커밋해야 Simplifier Studio의 "뉴스레터 리서치" 탭에 반영됩니다.')


if __name__ == "__main__":
    main()
