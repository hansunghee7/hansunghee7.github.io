"""심플리파이어 개인 계정 게시물별 반응 수를 하루 2회 읽어 비공개 저장소에 쌓는다(2026-10-03 탐, N108 핏 요청: 레트로 실사판 1호).

왜 화면 읽기인가: 인스타·스레드·링크드인 한성희 계정은 개인 계정이라 공식 API로 게시물 지표를 못 받는다.
그래서 구PC SNS 전용 크롬(9227, 이미 로그인됨)에서 게시물 화면의 숫자를 읽는다(sns_read.py와 같은 방식).
대상 목록: ~/workshop/track_posts.json  [{"id": "pm01", "channel": "instagram", "url": "..."}]
  - url이 비어 있으면 "url 없음"으로 기록만 한다(게시 확인 뒤 주소를 넣는다).
결과: ~/ops/repos/carvit-insight-data/data/simplifier_posts.json  {"history": [{"at": "...", "items": [...]}]}
값을 못 읽으면 null로 남기고 덮어쓰지 않는다(다른 fetch_*와 같은 원칙). 크롬은 끄지 않는다.
"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.expanduser("~/workshop"))
from sns_read import find_count, parse_abbrev, NUMBER  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TRACK = os.path.expanduser("~/workshop/track_posts.json")
REPO = os.path.expanduser("~/ops/repos/carvit-insight-data")
OUT = os.path.join(REPO, "data", "simplifier_posts.json")


def first(text, pats):
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            return parse_abbrev(m.group(1), m.group(2))
    return None


def read(pg, ch, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(6000)
    t = pg.locator("body").inner_text()
    if ch == "instagram":
        # 릴스 화면 아래에 남의 추천 릴스가 이어 붙는다(10/3 실측: 그 숫자가 섞여 좋아요 90으로 오독).
        # 내 캡션 뒤 "more" 다음부터 다음 계정 이름 전까지의 숫자만 본다. 순서는 좋아요·댓글·공유, 0인 칸은 화면에 안 나온다.
        seg = t.split("more", 1)[1] if "more" in t else t
        lines = [l.strip() for l in seg.splitlines() if l.strip()]
        nums = []
        for l in lines:
            m = re.fullmatch(NUMBER, l)
            if not m:
                break
            nums.append(parse_abbrev(m.group(1), m.group(2)))
        return {"counts_raw": nums, "likes": nums[0] if nums else 0}
    if ch == "linkedin":
        # 내 게시물 화면은 반응이 0이면 반응 칸이 없고 "노출수 N"만 있다(10/3 실측).
        return {"reactions": first(t, [NUMBER + r"\s*(?:reactions|개의 반응)", r"반응\s*" + NUMBER]),
                "comments": first(t, [NUMBER + r"\s*comments?", r"댓글\s*" + NUMBER]),
                # 왼쪽 프로필 칸에도 "게시물 노출수 3,245"가 있어(10/3 실측), 게시물 아래의 마지막 "노출수 N"을 읽는다.
                "views": (lambda ms: parse_abbrev(*ms[-1]) if ms else None)(re.findall(r"(?<!게시물 )노출수\s*" + NUMBER, t))}
    if ch == "threads":
        return {"likes": first(t, [r"좋아요\s*" + NUMBER, NUMBER + r"\s*likes?"]),
                "replies": first(t, [r"답글\s*" + NUMBER, NUMBER + r"\s*repl(?:y|ies)"]),
                "views": first(t, [r"조회\s*" + NUMBER, NUMBER + r"\s*views"])}
    return {}


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, timeout=120)


def main():
    track = json.load(open(TRACK, encoding="utf-8"))
    at = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 9 * 3600))  # KST
    items = []
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9227")
        ctx = b.contexts[0]
        pg = ctx.new_page()
        try:
            for it in track:
                # 주소가 없는 게시물은 건너뛴다. 프로필 첫 글을 자동으로 집으면 고정 글·다른 글을 잘못 읽는다(10/3 실측).
                rec = {"id": it["id"], "channel": it["channel"], "url": it.get("url")}
                try:
                    rec.update(read(pg, it["channel"], it["url"]) if it.get("url") else {"error": "url 없음"})
                except Exception as e:  # 한 곳이 실패해도 나머지는 읽는다
                    rec["error"] = type(e).__name__
                items.append(rec)
        finally:
            pg.close()
    print(json.dumps(items, ensure_ascii=False))
    if "--no-push" in sys.argv:
        return 0
    git("pull", "-q", "--rebase")
    data = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"history": []}
    data["history"] = (data["history"] + [{"at": at, "items": items}])[-200:]
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    git("add", "data/simplifier_posts.json")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return 0
    git("-c", "user.name=goosolar-bot", "-c", "user.email=goosolar@users.noreply.github.com", "commit", "-qm", f"chore: simplifier posts {at} [skip ci]")
    r = git("push", "-q")
    print("push rc", r.returncode, r.stderr[-200:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
