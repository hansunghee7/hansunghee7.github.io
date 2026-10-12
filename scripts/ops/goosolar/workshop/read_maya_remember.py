#!/usr/bin/env python3
"""마야 리멤버 커넥트 글별 좋아요·댓글 읽기(구PC 무인 프로필 9227, 2026-10-12 마야, N14).
내 게시물 화면(connect.rememberapp.co.kr/profile/1582110/posts)을 하루 1번 열고 글 카드의 '좋아요 N·댓글 N'을 읽는다.
리멤버는 조회수를 화면에 보여 주지 않는다. 결과 ~/workshop/out/maya/remember_latest.json(성공일 때만 덮어씀), 실패는 종료 코드 1.
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

OUT = os.path.expanduser("~/workshop/out/maya")
URL = "https://connect.rememberapp.co.kr/profile/1582110/posts"


def parse(body):
    L = [l.strip() for l in body.split("\n") if l.strip()]
    heads = [i for i, l in enumerate(L) if l == "심플리파이어 Success Coach / CEO"]
    posts = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(L)
        seg = L[i + 1:end]
        if len(seg) < 2:
            continue
        likes = next((int(m.group(1)) for l in seg for m in [re.fullmatch(r"좋아요\s+(\d+)", l)] if m), 0)
        comments = next((int(m.group(1)) for l in seg for m in [re.fullmatch(r"댓글\s+(\d+)", l)] if m), 0)
        posts.append({"date": seg[0], "title": seg[1][:140], "likes": likes, "comments": comments})
    return posts


def main():
    os.makedirs(OUT, exist_ok=True)
    kst = time.gmtime(time.time() + 9 * 3600)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9227")
        pg = b.contexts[0].new_page()
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(8000)
            if "login" in pg.url or "signin" in pg.url:
                print(json.dumps({"error": "리멤버 로그인 풀림", "url": pg.url}, ensure_ascii=False))
                return 1
            for _ in range(2):
                pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                pg.wait_for_timeout(2000)
            body = pg.locator("body").inner_text()
        finally:
            pg.close()
    posts = parse(body)
    if len(posts) < 3:
        print(json.dumps({"error": "글 3개 미만", "count": len(posts)}, ensure_ascii=False))
        return 1
    rec = {"fetched_at_kst": time.strftime("%Y-%m-%d %H:%M", kst), "count": len(posts), "posts": posts}
    json.dump(rec, open(os.path.join(OUT, "remember_latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": True, "count": len(posts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
