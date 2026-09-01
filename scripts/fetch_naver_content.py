"""
"신기한 아파트사전" 채널의 네이버 블로그·네이버 클립 게시물별 조회수를
매일 수집해 assets/data/naver-content.json에 쌓는다. 유튜브(fetch_youtube.py)와
같은 목적(채널이 아니라 콘텐츠 단위 성과)이지만, 네이버 쪽엔 공식 조회수 API가
없어서 fetch_sns_public.py와 같은 방식(Playwright로 공개 페이지 직접 읽기)을 쓴다.

## 왜 블로그 "이웃수"는 여기서 안 다루는가
블로그 이웃수(팔로워 개념)는 이미 scripts/fetch_sns_public.py가
assets/data/sns-insight.json에 수집하고 있다(회사 계정 "심플리파이어"용).
이 스크립트는 그것과 겹치지 않고, "이 게시물이 몇 번 조회됐는지"라는
콘텐츠 단위 성과만 새로 추가한다. 완전히 다른 계정(신기한 아파트사전)이라
파일도 따로 둔다.

## 게시글 목록은 어떻게 얻는가
처음엔 네이버 블로그 공개 RSS(rss.blog.naver.com/{blogId}.xml)를 썼는데,
실제로 돌려보니 게시글이 분명히 있는데도 0개로 나왔다(2026-09-01 확인) --
RSS는 블로그 주인이 "관리 > 기본설정 > RSS 발행"을 켜야만 채워지고, 새로
만든 블로그는 기본이 꺼짐이라 항상 비어 있었다. 그래서 RSS 대신 모바일판
블로그 홈(m.blog.naver.com/{blogId})을 직접 읽어서 게시글 링크·제목을
뽑는다 -- PC판은 본문이 iframe(#mainFrame) 안에 있어(fetch_sns_public.py가
이미 겪은 문제) 모바일판이 더 간단하고 안정적이다. 조회수는 이 목록에
없어서, 각 게시글 페이지를 직접 열어(모바일판) fetch_sns_public.py와 동일한
"키워드 주변 텍스트" 방식으로 읽는다(parse_count/first_count_near 로직 동일).

## 네이버 클립은 근거가 약하다 -- 첫 실행 결과를 보고 다듬을 것
네이버 클립은 공식 API도, 참고할 만한 공개 문서도 마땅치 않다. 크리에이터
프로필 페이지의 실제 DOM을 이 저장소 작업 환경에서 미리 열어볼 수가 없어서
(네이버 도메인이 이 세션 네트워크 정책에 막혀 있음), 가장 가능성 높은 방식
(클립 링크가 포함된 카드마다 텍스트에서 숫자를 뽑는 느슨한 방식)으로 짜고
GitHub Actions(네트워크 제약 없음)에서 실제로 돌려본 뒤 로그를 보고 고치는
순서로 간다 -- 이 저장소의 다른 수집 스크립트들도 처음엔 이렇게 시작해서
다듬었다(예: fetch_youtube.py의 숏츠 길이 기준·썸네일 해상도).

## 설계 원칙 (다른 fetch_*.py와 동일)
- 게시물 하나가 실패해도 나머지는 계속 진행한다(항목별 try/except).
- 날짜는 KST 기준(자정 근처 실행이 "어제"로 잘못 잡히는 사고 재발 방지).
- 값을 못 읽으면 그 항목은 건너뛴다 -- 0으로 덮어쓰지 않는다.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KST = timezone(timedelta(hours=9))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

BLOG_ID = "sinkihanapt"
CLIP_HANDLE = "simkihanapt"  # clip.naver.com/@simkihanapt -- 블로그 핸들과 철자가
                             # 다르지만 사장님이 알려준 실제 주소 그대로 쓴다.
OUT_PATH = os.path.join("assets", "data", "naver-content.json")
MAX_POSTS = 20
MAX_CLIPS = 20


def log(*a):
    print(*a, flush=True)


def parse_count(text):
    """텍스트에서 정확한 숫자만 뽑는다(fetch_sns_public.py와 동일 원칙).

    만/천 단위 축약(예: '1.2만')은 반올림된 값이라 증감 추적에 못 쓰므로
    버린다 -- 정확한 숫자를 못 읽으면 None을 반환해서 그날은 건너뛴다.
    """
    if not text:
        return None
    t = text.replace(" ", "")
    m = re.search(r"([\d,]{1,12}(?:\.\d+)?)\s*([만천억kKmM])?", t)
    if not m:
        return None
    num, unit = m.group(1), m.group(2)
    if unit or "." in num:
        return None
    try:
        n = int(num.replace(",", ""))
    except ValueError:
        return None
    # fetch_sns_public.py는 팔로워 수 맥락이라 0을 "선택자가 엉뚱한 걸
    # 읽었다"는 신호로 버리지만, 여긴 콘텐츠 조회수라 갓 올린 글/클립은
    # 진짜 0이 정상값이다(2026-09-01: 실제로 클립 하나가 0회였음). 그래서
    # 0은 허용하고, 음수·비현실적으로 큰 값만 버린다.
    if n < 0 or n > 100_000_000:
        return None
    return n


def first_count_near(page, keywords):
    """키워드가 들어간 요소의 텍스트에서 숫자를 뽑는다 -- CSS 선택자를
    박아두면 페이지가 조금만 바뀌어도 깨지므로 '키워드 주변 텍스트'로
    느슨하게 찾는다(fetch_sns_public.py와 동일 함수)."""
    for kw in keywords:
        try:
            loc = page.locator(f"text={kw}").first
            if loc.count() == 0:
                continue
            for target in (loc, loc.locator("xpath=..")):
                try:
                    n = parse_count(target.inner_text(timeout=4000))
                except Exception:
                    n = None
                if n is not None:
                    return n
        except Exception:
            continue
    return None


def upsert(history, today, entry):
    """같은 날짜 기록이 이미 있으면 갱신, 없으면 추가 후 날짜순 정렬."""
    for i, e in enumerate(history):
        if e.get("date") == today:
            history[i] = entry
            return
    history.append(entry)
    history.sort(key=lambda e: e.get("date", ""))


def list_recent_blog_posts(browser, limit):
    """모바일판 블로그 홈에서 게시글 링크·제목을 직접 읽는다(RSS 대신 --
    이유는 모듈 docstring 참고)."""
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    posts = []
    try:
        page.goto(f"https://m.blog.naver.com/{BLOG_ID}", timeout=45000)
        # "네트워크가 잠잠해질 때까지"(networkidle)는 분석 스크립트가 계속
        # 폴링하는 요즘 사이트에서는 거의 항상 타임아웃까지 그냥 흘러가버려
        # 신호가 안 된다(2026-09-01 실측: RSS→모바일 페이지로 바꿔도 여전히
        # 0건). 실제 콘텐츠가 떴다는 더 직접적인 증거(이미지 등장)를 기다린다.
        try:
            page.wait_for_selector("img", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        # 링크가 경로형(/{blogId}/{logNo})인지 쿼리스트링형
        # (PostView.naver?blogId=...&logNo=...)인지 몰라서(2026-09-01: 경로형만
        # 가정했다가 0건) blogId가 href 어디에 있든 일단 후보로 잡고,
        # logNo는 두 형식 다 시도해서 뽑는다.
        links = page.locator(f"a[href*='{BLOG_ID}']")
        seen = set()
        for i in range(links.count()):
            if len(posts) >= limit:
                break
            try:
                href = links.nth(i).get_attribute("href") or ""
                m = re.search(rf"{BLOG_ID}/(\d+)", href) or re.search(r"[?&]logNo=(\d+)", href)
                if not m:
                    continue
                log_no = m.group(1)
                if log_no in seen:
                    continue
                title = links.nth(i).inner_text(timeout=3000).strip()
                if not title:
                    continue
                seen.add(log_no)
                url = href if href.startswith("http") else f"https://blog.naver.com/{BLOG_ID}/{log_no}"
                posts.append({"logNo": log_no, "title": title, "url": url, "pubDate": ""})
            except Exception:
                continue
        if not posts:
            # 또 0건이면 다음엔 바로 원인을 보게, 실제로 뭐가 있었는지
            # 진단 로그를 남긴다(전체 <a> 개수·href 샘플 몇 개).
            all_links = page.locator("a")
            n = all_links.count()
            samples = []
            for i in range(min(n, 5)):
                try:
                    samples.append((all_links.nth(i).get_attribute("href") or "")[:80])
                except Exception:
                    pass
            log(f"  진단: 전체 링크 {n}개, href 샘플 {samples}")
    except Exception as e:
        log(f"블로그 홈 접근 실패 — {type(e).__name__}: {e}")
    finally:
        page.close()
    return posts


def collect_post_views(browser, log_no):
    """모바일판 게시글 페이지에서 조회수를 읽는다."""
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(f"https://m.blog.naver.com/{BLOG_ID}/{log_no}", timeout=45000)
        try:
            page.wait_for_selector("img", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        return first_count_near(page, ["조회수", "조회"])
    finally:
        page.close()


def collect_recent_clips(browser, limit):
    """클립 크리에이터 프로필 페이지에서 최근 클립 목록(링크·조회수)을
    읽는다. 처음엔 href에 '/clip/'이 들어있을 거라 짐작하고 짰는데 실제로는
    0건이었다(2026-09-01 확인, 실제 링크 패턴은 못 알아냄) -- 링크 패턴을
    아예 안 가정하고, "썸네일(이미지)을 감싸는 링크"라는 더 일반적인 구조로
    카드를 찾는다. 조회수는 프로필 목록 화면에 이미 보여서(각 클립 클릭 없이)
    같은 카드의 텍스트에서 바로 읽는다."""
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    clips = []
    try:
        page.goto(f"https://clip.naver.com/@{CLIP_HANDLE}", timeout=45000)
        # networkidle 대신 실제 콘텐츠(이미지) 등장을 기다린다 -- 이유는
        # list_recent_blog_posts 쪽 주석 참고(2026-09-01, 둘 다 같은 증상).
        try:
            page.wait_for_selector("img", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        cards = page.locator("a:has(img)")
        count = min(cards.count(), limit)
        seen = set()
        for i in range(count):
            card = cards.nth(i)
            try:
                href = card.get_attribute("href") or ""
                if not href:
                    continue
                # href 형식을 모르니 마지막 경로 조각을 느슨하게 다듬어
                # id로 쓴다 -- 정확한 스킴보다 "매일 같은 클립이 같은 키로
                # 잡히는지"가 중요하다.
                tail = href.rstrip("/").split("/")[-1] or href
                clip_id = re.sub(r"[^a-zA-Z0-9_-]", "_", tail)[:40]
                if not clip_id or clip_id in seen:
                    continue
                seen.add(clip_id)
                text = card.inner_text(timeout=4000)
                n = parse_count(text)
                clips.append({"id": clip_id, "url": href, "raw_text": text[:80], "views": n})
            except Exception:
                continue
        if not clips:
            # a:has(img)도 0건이면 클립 카드가 <a>가 아닌 다른 요소(div
            # 클릭 핸들러 등)일 가능성이 크다 -- 다음엔 바로 보게 진단 로그.
            n_img = page.locator("img").count()
            n_a = page.locator("a").count()
            log(f"  진단: img {n_img}개, a {n_a}개 (카드가 <a> 태그가 아닐 수 있음)")
    except Exception as e:
        log(f"  클립 목록 수집 실패 — {type(e).__name__}: {e}")
    finally:
        page.close()
    return clips


def main():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    captured_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    data = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("posts", {})
    data.setdefault("clips", {})

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            # ── 블로그 ──
            try:
                posts = list_recent_blog_posts(browser, MAX_POSTS)
                log(f"블로그: 최근 게시글 {len(posts)}개 확인")
            except Exception as e:
                posts = []
                log(f"블로그 게시글 목록 수집 실패 — {type(e).__name__}: {e}")

            blog_ok = 0
            for post in posts:
                try:
                    views = collect_post_views(browser, post["logNo"])
                except Exception as e:
                    views = None
                    log(f"  {post['title'][:20]}: 수집 실패 — {type(e).__name__}")
                if views is None:
                    continue
                blog_ok += 1
                p_entry = data["posts"].setdefault(post["logNo"], {"history": []})
                p_entry["title"] = post["title"]
                p_entry["url"] = post["url"]
                p_entry["published_at"] = post["pubDate"]
                upsert(p_entry["history"], today, {"date": today, "views": views})
            log(f"블로그: {blog_ok}/{len(posts)}개 조회수 갱신")

            # ── 클립 ──
            clips = collect_recent_clips(browser, MAX_CLIPS)
            clip_ok = 0
            for c in clips:
                if c.get("views") is None:
                    continue
                clip_ok += 1
                clip_url = c["url"]
                if clip_url.startswith("/"):
                    clip_url = "https://clip.naver.com" + clip_url
                c_entry = data["clips"].setdefault(c["id"], {"history": []})
                c_entry["url"] = clip_url
                upsert(c_entry["history"], today, {"date": today, "views": c["views"]})
            log(f"클립: {clip_ok}/{len(clips)}개 조회수 갱신"
                + (f" (참고: 원문 예시 '{clips[0]['raw_text']}')" if clips else ""))
        finally:
            browser.close()

    data["updated_at"] = captured_at
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log(f"저장 완료 → {OUT_PATH}")


if __name__ == "__main__":
    main()
