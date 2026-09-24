#!/usr/bin/env python3
"""구PC 작업실 SNS 숫자 읽기 (크롬 확장 대체 실험, 2026-09-24 탐).

크롬 확장(_sns-extension)이 사장님 크롬에서 읽던 것과 같은 화면을, 구PC의 SNS 전용 크롬(9227·9228)에서
같은 방식(화면 글자 + 같은 숫자 규칙)으로 읽는다. 화면 캡처와 AI 호출이 없다.
1단계(이 파일): 계정 팔로워 수 + 숏폼 채널 게시물별 조회수. 결과를 JSON 한 줄씩 출력한다.
인스타 릴스는 목록 타일에 마우스를 올려 좋아요·댓글까지 읽는다.

사용: python sns_read.py > out/sns/<날짜>.jsonl   (틱톡은 자동 로그인이 막혀 크롬 확장이 계속 담당. 링크드인은 2026-09-24 휴대폰 승인으로 로그인됨)
"""
import argparse, json, re, sys, time
from playwright.sync_api import sync_playwright

NUMBER = r"([\d][\d,\.]*)\s*(천|만|K|k|M|m)?"

# (포트, 키, 주소, 팔로워 키워드들, 목록 링크 패턴) -- 확장 background.js·content-script.js와 같은 값
TARGETS = [
    (9227, "linkedin", "https://www.linkedin.com/in/simplifier/", ["팔로워", "followers"], None),
    (9227, "facebook", "https://www.facebook.com/simplifier.seoul", ["팔로워", "친구", "followers", "friends"], None),
    (9227, "instagram", "https://www.instagram.com/simplifier_seoul/", ["followers", "팔로워"], None),
    (9227, "threads", "https://www.threads.com/@simplifier_seoul", ["followers", "팔로워"], None),
    (9227, "remember", "https://connect.rememberapp.co.kr/profile/1582110/posts", ["팔로워"], None),
    (9227, "rocketpunch", "https://www.rocketpunch.com/@simplfier", ["팔로워", "Total Followers", "Followers"], None),
    (9228, "content_instagram", "https://www.instagram.com/sinkihanapt/", ["followers", "팔로워"], r"/reel/([^/?#]+)"),
    (9228, "content_threads", "https://www.threads.com/@sinkihanapt", ["followers", "팔로워"], None),
    (9228, "content_facebook", "https://www.facebook.com/profile.php?id=61593748241305", ["팔로워", "팔로우", "followers"], None),
    (9228, "naver_clip", "https://clip.naver.com/@simkihanapt", ["팔로워"], None),
]


def parse_abbrev(num, suffix):
    try:
        n = float(num.replace(",", ""))
    except ValueError:
        return None
    n *= {"천": 1e3, "만": 1e4, "K": 1e3, "k": 1e3, "M": 1e6, "m": 1e6}.get(suffix or "", 1)
    return round(n)


def find_count(text, keyword):
    """한국어 화면은 "팔로워 317"(라벨이 앞), 영어 화면은 "317 followers"(숫자가 앞)가 기본이다.
    순서를 한 가지로 고정하면 영어 화면에서 "317 followers / 169 following"의 169를 잡는다(2026-09-24 실측).
    그래서 키워드가 한글이면 라벨 먼저, 영문이면 숫자 먼저 찾는다."""
    label_first = r"\D{0,8}" + NUMBER
    orders = ("label", "number") if re.search(r"[가-힣]", keyword) else ("number", "label")
    for o in orders:
        m = re.search(keyword + label_first, text, re.I) if o == "label" else re.search(NUMBER + r"[ \t]*" + keyword, text, re.I)
        if m:
            return parse_abbrev(m.group(1), m.group(2))
    return None


def list_items(pg, pattern, url):
    """릴스 목록 타일: 평소에는 조회수가, 마우스를 올리면 좋아요·댓글 두 숫자가 보인다(2026-09-24 실측)."""
    pg.goto(url.rstrip("/") + "/reels/", wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(5000)
    items, seen = [], set()
    for a in pg.locator("a[href]").all():
        href = a.get_attribute("href") or ""
        m = re.search(pattern, href)
        if not m or m.group(1) in seen:
            continue
        nm = re.search(NUMBER, (a.inner_text() or "").strip())
        if not nm:
            continue
        seen.add(m.group(1))
        it = {"id": m.group(1), "views": parse_abbrev(nm.group(1), nm.group(2)),
              "url": href if href.startswith("http") else "https://www.instagram.com" + href}
        try:
            a.hover(); pg.wait_for_timeout(700)
            nums = re.findall(NUMBER, a.inner_text() or "")
            if len(nums) >= 2:
                it["likes"], it["comments"] = parse_abbrev(*nums[0]), parse_abbrev(*nums[1])
        except Exception:
            pass
        items.append(it)
    return items


def naver_clip_items(pg):
    """확장 collectLabeledCards와 같은 규칙: '조회수' 라벨 span 다음 형제의 숫자, 카드 aria-label을 캡션으로."""
    out = []
    for span in pg.locator("span", has_text=re.compile(r"^조회수$")).all():
        nxt = span.locator("xpath=following-sibling::*[1]")
        if not nxt.count():
            continue
        nm = re.search(NUMBER, nxt.first.inner_text().strip())
        card = span.locator("xpath=ancestor::*[@aria-label][1]")
        cap = card.first.get_attribute("aria-label") if card.count() else ""
        if nm and cap:
            out.append({"caption": cap[:40], "views": parse_abbrev(nm.group(1), nm.group(2))})
    return out


def post_detail(pg, url):
    """게시물 화면의 좋아요·댓글 수. 인스타: '좋아요 N개' / 'N likes', 댓글: '댓글 N개' / 'View all N comments'."""
    pg.goto(url, wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(4000)
    text = pg.locator("body").inner_text()
    likes = find_count(text, "좋아요") or find_count(text, "likes")
    m = re.search(r"댓글\s*" + NUMBER + r"\s*개", text) or re.search(r"View all\s*" + NUMBER + r"\s*comments", text, re.I)
    comments = parse_abbrev(m.group(1), m.group(2)) if m else None
    return {"likes": likes, "comments": comments}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--detail", type=int, default=0)
    a = ap.parse_args()
    with sync_playwright() as p:
        browsers = {}
        for port, key, url, kws, lp in TARGETS:
            t0 = time.time()
            rec = {"key": key, "port": port, "date": time.strftime("%Y-%m-%d")}
            try:
                if port not in browsers:
                    browsers[port] = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
                pg = browsers[port].contexts[0].new_page()
                pg.goto(url, wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(6000)
                text = pg.locator("body").inner_text()
                rec["login_wall"] = bool(re.search(r"로그인|Log in|Sign in", text[:400])) and len(text) < 3000
                rec["followers"] = next((c for c in (find_count(text, k) for k in kws) if c is not None), None)
                if lp:
                    rec["items"] = list_items(pg, lp, url)
                if key == "naver_clip":
                    rec["items"] = naver_clip_items(pg)
                pg.close()
            except Exception as e:
                rec["error"] = str(e)[:150]
            rec["sec"] = round(time.time() - t0)
            print(json.dumps(rec, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
