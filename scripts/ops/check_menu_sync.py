#!/usr/bin/env python3
"""carvit.ai 머리 메뉴가 한국어·영어에서 같은 항목 수·같은 링크 경로인지 점검한다(과제 N127).
사용: python scripts/ops/check_menu_sync.py [URL]
출력은 숫자와 판정만(쿠키·값 출력 없음). 종료코드: 0 같음 또는 서버 언어 구분 없음, 1 다름, 2 받기 실패.
"""
import sys
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

URL = "https://carvit.ai/"


class _Links(HTMLParser):
    """<header>·<nav> 안의 <a href>를 순서대로 모은다. 없으면 호출 쪽이 문서 전체로 대체한다."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.links = []
        self.all_links = []

    def handle_starttag(self, tag, attrs):
        if tag in ("header", "nav"):
            self.depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.all_links.append(href)
                if self.depth > 0:
                    self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("header", "nav") and self.depth > 0:
            self.depth -= 1


def extract_links(html):
    """머리 영역 링크 목록(없으면 문서 전체 링크)."""
    p = _Links()
    p.feed(html)
    return p.links if p.links else p.all_links


def path_of(href):
    """링크 목적지를 경로만으로 줄인다(도메인·쿼리·해시 제거, 언어 접두사는 그대로 둔다)."""
    return urlparse(href).path or "/"


def compare(links_a, links_b):
    """(같음 여부, 항목 수 a, 항목 수 b, 경로 집합 a, 경로 집합 b)."""
    sa, sb = {path_of(h) for h in links_a}, {path_of(h) for h in links_b}
    same = len(links_a) == len(links_b) and sa == sb
    return same, len(links_a), len(links_b), sa, sb


def fetch(url, lang):
    req = urllib.request.Request(url, headers={"Accept-Language": lang, "User-Agent": "menu-sync-check/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main(argv):
    url = argv[1] if len(argv) > 1 else URL
    try:
        ko, en = fetch(url, "ko"), fetch(url, "en")
    except Exception as e:
        print(f"받기 실패: {type(e).__name__}")
        return 2
    identical = ko == en
    same, na, nb, _, _ = compare(extract_links(ko), extract_links(en))
    if identical:
        print(f"서버 언어 구분 없음(두 응답 동일) 항목 수 ko={na} en={nb}")
        return 0
    print(f"{'같음' if same else '다름'} 항목 수 ko={na} en={nb}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
