#!/usr/bin/env python3
"""마야 링크드인 글별 성과 읽기(구PC 무인 프로필, 2026-10-12 마야, 사장님 지시 '구PC 무인 프로필로 매일 자동 읽기').

왜: 링크드인 개인 계정은 공식 API·컴포지오로 글별 노출·좋아요를 못 받는다(컴포지오 링크드인 도구 4개: 글 작성·삭제·회사·내정보).
방식: 탐의 read_tracked_posts.py와 같은 SNS 전용 크롬(9227, 링크드인 로그인됨)에서, 사람이 하는 것과 같은 한 동작
(내 활동 페이지 열기, 몇 번 스크롤, 글 카드 끝 문구 읽기)만 하루 1번 한다. docs/마야_좋아요_수집_절차.md 1절과 같은 규칙.
결과: ~/workshop/out/maya/linkedin_<KST날짜>_<HHMM>.json, 최신본 latest.json(성공일 때만 덮어씀).
값을 못 읽으면 종료 코드 1, latest.json은 그대로 둔다. 크롬은 끄지 않는다.
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

OUT = os.path.expanduser("~/workshop/out/maya")
URL = "https://www.linkedin.com/in/simplifier/recent-activity/all/"  # /in/me/ 는 무인 프로필에서 빈 화면(10/12 실측)
NUM = r"(\d[\d,]*)"


def to_int(s):
    return int(s.replace(",", "")) if s else None


def parse_cards(body):
    """본문 글자를 '피드 게시물' 표지로 나눠 카드마다 읽는다(2026-10-12 실측: 링크드인이 article 요소를 없애 글자 구조로 읽는다).
    카드 모양: 이름 | • 회원님 | 직함 | 나이(4일) | 첫 줄 제목 | ... | 반응 수 | 노출수 N | 분석 보기."""
    lines = [l.strip().replace("​", "").strip() for l in body.split("\n")]
    starts = [i for i, l in enumerate(lines) if l == "피드 게시물"]
    cards = []
    for k, s in enumerate(starts):
        seg = [l for l in lines[s + 1:(starts[k + 1] if k + 1 < len(starts) else len(lines))] if l]
        age = next((l for l in seg[:8] if re.fullmatch(r"(수정됨 • )?\d+(분|시간|일|주|개월|년)( •.*)?", l)), None)
        ai = seg.index(age) if age in seg else 0
        head = seg[ai + 1] if ai + 1 < len(seg) else ""
        j = next((n for n, l in enumerate(seg) if re.match(r"노출수\s*" + NUM, l)), None)
        views = to_int(re.match(r"노출수\s*" + NUM, seg[j]).group(1)) if j is not None else None
        # "… 더보기" 뒤부터 노출수 앞까지 숫자만 있는 줄: 첫 숫자가 좋아요(반응) 수, 나머지는 댓글·퍼감(글자 이름이 없어 순서만 기록).
        react, extra = None, []
        if j is not None:
            k0 = max((n for n, l in enumerate(seg[:j]) if "더보기" in l), default=-1)
            nums = [to_int(l) for l in seg[k0 + 1:j] if re.fullmatch(NUM, l)]
            react = nums[0] if nums else 0
            extra = nums[1:]
        tailtxt = " | ".join(seg[max(0, (j or len(seg)) - 6):(j or len(seg)) + 1])
        cards.append({"age": age, "head": head[:140], "reactions": react, "extra_counts": extra,
                      "impressions": views, "tail": tailtxt[-120:]})
    return cards


def main():
    os.makedirs(OUT, exist_ok=True)
    kst = time.gmtime(time.time() + 9 * 3600)
    stamp = time.strftime("%Y-%m-%d_%H%M", kst)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9227")
        pg = b.contexts[0].new_page()
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(9000)
            if "login" in pg.url or "authwall" in pg.url:
                print(json.dumps({"error": "링크드인 로그인 풀림", "url": pg.url}, ensure_ascii=False))
                return 1
            for _ in range(5):
                pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                pg.wait_for_timeout(2200)
            body = pg.locator("body").inner_text()
        finally:
            pg.close()
    posts = parse_cards(body)[:16]
    good = [x for x in posts if x["impressions"] is not None]
    rec = {"fetched_at_kst": time.strftime("%Y-%m-%d %H:%M", kst), "count": len(posts), "with_impressions": len(good), "posts": posts}
    path = os.path.join(OUT, f"linkedin_{stamp}.json")
    json.dump(rec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if len(good) < 3:
        print(json.dumps({"error": "노출 값을 읽은 글이 3개 미만", "count": len(posts), "with_impressions": len(good)}, ensure_ascii=False))
        return 1
    json.dump(rec, open(os.path.join(OUT, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": True, "path": path, "count": len(posts), "with_impressions": len(good)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
