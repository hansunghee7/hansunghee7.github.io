"""
「기획자의 질문법」(한성희 저, 파지트, 2025-06-13) 베스트셀러 순위·판매지수를
예스24·알라딘·교보문고·리디북스·밀리의서재에서 매일 수집해
assets/data/book-insight.json에 날짜별로 쌓는다.

cinaeng/ux-book-tracker(다른 책 「UX의 언어들」용, Node.js+Playwright)와 같은
원리지만, 이 저장소는 지금까지 100% Python이라 Node를 새로 들이지 않고
Playwright의 Python 바인딩으로 옮겨왔다 -- 같은 브라우저 엔진, 같은 API라
기능 차이는 없다.

소스 5개(예스24/알라딘/교보문고/리디북스/밀리의서재)를 각각 독립적으로
try/except로 감싼다 -- 하나가 사이트 구조 변경으로 깨져도(가장 취약한 건
교보문고 -- Next.js 클라이언트 렌더링) 나머지는 그날 값을 정상적으로
남겨야 하기 때문이다.

리디북스: 카테고리 베스트셀러 페이지(주간/월간)를 직접 확인한 결과, 이 책은
순위 차트(1~11위, _rdt_idx 마커로 확인 가능)에는 없고 그 아래 순위 없는
"관련 도서" 목록에만 텍스트로 등장한다 -- 즉 실제 순위가 없다. 그래서
평점/리뷰만 참고용으로 수집한다 (collect_ridi 참고).

밀리의서재: 검색은 로그인이 필요해 자동화 대상이 아니지만, 카테고리
브라우즈 페이지(자기계발 > 기획, "인기 순" 정렬)는 로그인 없이 접근되고
이 책도 그 목록에 있다. "더보기" 버튼으로 계속 불러오는 무한 스크롤형
목록이라 페이지네이션 URL이 없어, Playwright로 버튼을 눌러가며 이 책이
나타날 때까지 로드한 뒤 등장 순서를 rank로 쓴다 (collect_millie 참고).

카테고리 번호는 각 서점 사이트를 직접 뒤져서 확인한 값이다:
  예스24  001001026003     = 국내도서 > 자기계발 > 기획/정보/시간관리
  예스24  001001025001004  = 국내도서 > 경제경영 > CEO/비즈니스맨 > 기획/정보/시간관리
  알라딘  CID 70229        = 자기계발 > 기획/보고 > 기획
  알라딘  CID 70222        = 자기계발 > 시간관리/정보관리 > 정보관리
  교보문고 150503           = 자기계발 > 비즈니스능력계발 > 기획력

이 스크립트는 「기획자의 질문법」이 메인이지만, 같은 Playwright 브라우저를
띄운 김에 「UX의 언어들」의 보조 지표도 몇 개 더 수집해서
assets/data/ux-book-extra.json에 남긴다. cinaeng/ux-book-tracker(그 책의
메인 트래커)가 커버하지 않는 카테고리들이라 -- 책 저자가 직접 확인해준
실제 진열 카테고리(알라딘 광고/홍보/PR, 교보 경영전략일반)라서 메인
미러링과는 별도로 이렇게 보충한다. 메인 트래커를 건드리거나 대체하는
게 아니라, 그게 안 보는 부분만 우리가 따로 본다.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

OUT_PATH = "assets/data/book-insight.json"
UX_OUT_PATH = "assets/data/ux-book-extra.json"

BOOK = {
    "title": "기획자의 질문법",
    "author": "한성희",
    "publisher": "파지트",
    "pub_date": "2025-06-13",
}

YES24_GOODS_ID = "147079674"
YES24_CATEGORY = "001001026003"   # 국내도서 > 자기계발 > 기획/정보/시간관리
YES24_CATEGORY2 = "001001025001004"  # 국내도서 > 경제경영 > CEO/비즈니스맨 > 기획/정보/시간관리

ALADIN_ITEM_ID = "364986311"
ALADIN_CID_PLANNING = "70229"  # 자기계발 > 기획/보고 > 기획
ALADIN_CID_INFO = "70222"      # 자기계발 > 시간관리/정보관리 > 정보관리

KYOBO_CODE = "S000216681258"
KYOBO_CATEGORY_PATH = "150503"  # 자기계발 > 비즈니스능력계발 > 기획력

RIDI_ID = "2234005394"

MILLIE_CATEGORY_URL = "https://www.millie.co.kr/v3/search/3depth/1298/?parentSeq=1287&nav_hidden=y"  # 자기계발 > 기획, 인기 순
MILLIE_BOOK_TITLE = "기획자의 질문법"

# ── 「UX의 언어들」 보조 수집 (cinaeng/ux-book-tracker가 안 보는 카테고리만) ──
UX_ALADIN_ITEM_ID = "397807838"
UX_ALADIN_CID_AD = "268"       # 경제경영 > 마케팅/세일즈 > 광고/홍보/PR
UX_KYOBO_CODE = "S000220493173"
UX_KYOBO_CID_STRATEGY = "130701"  # 경제/경영 > 경영전략 > 경영전략일반

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def log(*a):
    print("·", *a)


def get_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def html_to_text(html):
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text)


# ────────────────────────────────────────────────────────────
# 예스24 -- 서버 렌더링이라 일반 HTTP fetch로 충분 (Playwright 불필요)

def yes24_rank_in_list(html, target_id):
    """목록에 박혀 있는 절대 순위 마커를 읽는다. 등장 순서를 세면 관련상품/
    eBook/중고 링크가 섞여 순위가 부풀려지므로 반드시 마커를 읽어야 한다."""
    at = html.find(f'data-goods-no="{target_id}"')
    if at == -1:
        return None
    block = html[at:at + 3000]
    m = re.search(r'class="[^"]*\brank\b[^"]*"[^>]*>\s*(\d+)\s*<', block)
    if m:
        return int(m.group(1))
    ids = re.findall(r'data-goods-no="(\d+)"', html)
    if target_id in ids:
        return ids.index(target_id) + 1
    return None


def yes24_category_rank(category_number, goods_id=YES24_GOODS_ID, max_pages=3):
    for page_no in range(1, max_pages + 1):
        url = (
            f"https://www.yes24.com/product/category/bestseller"
            f"?categoryNumber={category_number}&pageNumber={page_no}&pageSize=100"
        )
        rank = yes24_rank_in_list(get_html(url), goods_id)
        if rank:
            return rank
    return None


def collect_yes24():
    out = {"category_rank": None, "category2_rank": None, "sales_index": None, "reviews": 0, "rating": None}
    try:
        out["category_rank"] = yes24_category_rank(YES24_CATEGORY)
        log("예스24 기획/정보/시간관리:", out["category_rank"] or "권외")
    except Exception as e:
        log("!! 예스24 카테고리 수집 실패:", e)

    try:
        out["category2_rank"] = yes24_category_rank(YES24_CATEGORY2)
        log("예스24 CEO/비즈니스맨 기획/정보/시간관리:", out["category2_rank"] or "권외")
    except Exception as e:
        log("!! 예스24 카테고리2 수집 실패:", e)

    try:
        text = html_to_text(get_html(f"https://www.yes24.com/product/goods/{YES24_GOODS_ID}"))
        si = re.search(r"판매지수\s*([\d,]+)", text)
        if si:
            out["sales_index"] = int(si.group(1).replace(",", ""))
        rv = re.search(r"회원리뷰\s*\(\s*(\d+)\s*건\s*\)", text)
        if rv:
            out["reviews"] = int(rv.group(1))
        rt = re.search(r"리뷰\s*총점\s*([\d.]+)", text)
        if rt:
            out["rating"] = float(rt.group(1))
        log("예스24 판매지수:", out["sales_index"], "· 리뷰:", out["reviews"])
    except Exception as e:
        log("!! 예스24 상품 페이지 수집 실패:", e)

    return out


# ────────────────────────────────────────────────────────────
# 알라딘 -- 상품 페이지는 fetch, 카테고리 순위는 Playwright

def collect_aladin_product():
    out = {"sales_point": None, "reviews": 0, "rating": None}
    try:
        text = html_to_text(get_html(f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={ALADIN_ITEM_ID}"))
        sp = re.search(r"Sales\s*Point\s*:?\s*([\d,]+)", text, re.I)
        if sp:
            out["sales_point"] = int(sp.group(1).replace(",", ""))

        r100 = re.search(r"100자평\s*\(?\s*(\d+)", text)
        rvw = re.search(r"리뷰\s*\(?\s*(\d+)", text)
        out["reviews"] = (int(r100.group(1)) if r100 else 0) + (int(rvw.group(1)) if rvw else 0)

        rt = (
            re.search(r"([\d.]+)\s*100자평", text)
            or re.search(r"([\d.]+)\s*점", text)
            or re.search(r"별점\s*([\d.]+)", text)
        )
        if rt and out["reviews"] > 0:
            out["rating"] = float(rt.group(1))

        log("알라딘 세일즈포인트:", out["sales_point"], "· 리뷰:", out["reviews"])
    except Exception as e:
        log("!! 알라딘 상품 페이지 수집 실패:", e)
    return out


def aladin_rank_on_page(page, cid, page_no, item_id=ALADIN_ITEM_ID):
    url = (
        f"https://www.aladin.co.kr/shop/common/wbest.aspx"
        f"?BranchType=1&CID={cid}&BestType=Bestseller&cnt=100&SortOrder=1&page={page_no}"
    )
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector(f'a[href*="ItemId={item_id}"]', timeout=8000)
    except Exception:
        return None  # 이 페이지엔 없음

    return page.evaluate(
        """(id) => {
            const link = document.querySelector(`a[href*="ItemId=${id}"]`);
            if (!link) return null;
            // 항목 컨테이너를 위로 올라가며 "N." 로 시작하는 블록을 찾는다
            let box = link;
            for (let i = 0; i < 10; i++) {
                const p = box.parentElement;
                if (!p) break;
                box = p;
                const m = (box.innerText || '').match(/^\\s*(\\d+)\\.\\s/);
                if (m) return Number(m[1]);
            }
            return null;
        }""",
        item_id,
    )


def aladin_category_rank(page, cid, item_id=ALADIN_ITEM_ID, max_pages=1):
    for p in range(1, max_pages + 1):
        rank = aladin_rank_on_page(page, cid, p, item_id)
        if rank is not None:
            return rank
    return None


def collect_aladin_categories(browser):
    out = {"planning_rank": None, "info_mgmt_rank": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        out["planning_rank"] = aladin_category_rank(page, ALADIN_CID_PLANNING)
        log("알라딘 기획:", out["planning_rank"] or "권외")
        out["info_mgmt_rank"] = aladin_category_rank(page, ALADIN_CID_INFO)
        log("알라딘 정보관리:", out["info_mgmt_rank"] or "권외")
    except Exception as e:
        log("!! 알라딘 카테고리 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 교보문고 -- Next.js 클라이언트 렌더링이라 Playwright 필수

def kyobo_pos_in_list(page, url, code=KYOBO_CODE):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector('a[href*="/detail/S"]', timeout=20000)
    except Exception:
        pass  # 목록이 정말 비어 있을 수도 있다
    return page.evaluate(
        """(code) => {
            const anchors = [...document.querySelectorAll('a[href*="/detail/S"]')];
            const ids = [];
            for (const a of anchors) {
                const m = a.getAttribute('href').match(/detail\\/(S\\d+)/);
                if (!m) continue;
                if (ids[ids.length - 1] !== m[1]) ids.push(m[1]);
            }
            const i = ids.indexOf(code);
            return i === -1 ? null : i + 1;
        }""",
        code,
    )


def collect_kyobo(browser):
    out = {"badge_rank": None, "category_rank": None, "reviews": 0, "rating": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(f"https://product.kyobobook.co.kr/detail/{KYOBO_CODE}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("main", timeout=25000)
        # 리뷰 수·평점은 초기 렌더 이후 비동기로 채워진다 -- 숫자가 붙을 때까지 대기.
        try:
            page.wait_for_function("() => /리뷰\\s*\\(?\\s*\\d+/.test(document.body.innerText)", timeout=15000)
        except Exception:
            pass
        text = page.evaluate("() => document.body.innerText")

        badge = re.search(r"주간베스트\s*자기계발\s*([\d,]+)\s*위", text)
        if badge:
            out["badge_rank"] = int(badge.group(1).replace(",", ""))

        rv = re.search(r"리뷰\s*\(\s*(\d+)\s*\)", text) or re.search(r"리뷰\s+(\d+)\b", text)
        if rv:
            out["reviews"] = int(rv.group(1))

        rt = re.search(r"(\d{1,2}(?:\.\d)?)\s*리뷰\s+\d+\b", text)
        if rt:
            v = float(rt.group(1))
            out["rating"] = v if out["reviews"] > 0 and 0 < v <= 10 else None

        log("교보 뱃지(자기계발):", out["badge_rank"] or "표시 없음", "· 리뷰:", out["reviews"])

        out["category_rank"] = kyobo_pos_in_list(
            page, f"https://store.kyobobook.co.kr/category/domestic/{KYOBO_CATEGORY_PATH}/best"
        )
        log("교보 기획력 카테고리:", out["category_rank"] or "권외")
    except Exception as e:
        log("!! 교보문고 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 리디북스 -- 베스트셀러 순위 없음(확인함). 평점/리뷰만 참고용으로 가볍게.

def collect_ridi(browser):
    out = {"rating_count": 0, "rating": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(f"https://ridibooks.com/books/{RIDI_ID}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        text = page.evaluate("() => document.body.innerText")

        rv = re.search(r"(\d+)\s*명\s*평가", text)
        if rv:
            out["rating_count"] = int(rv.group(1))

        rt = re.search(r"([\d.]+)\s*구매자\s*별점", text)
        if rt:
            out["rating"] = float(rt.group(1))

        log("리디북스 평가:", out["rating_count"], "명 · 평점", out["rating"])
    except Exception as e:
        log("!! 리디북스 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 밀리의서재 -- 검색은 로그인 필요라 자동화 대상이 아니지만, 카테고리
# 브라우즈 페이지(자기계발 > 기획, 인기 순)는 로그인 없이 볼 수 있고
# 이 책도 그 목록에 있다. 페이지네이션 URL이 없는 "더보기" 무한 스크롤이라
# 책이 나타날 때까지 버튼을 눌러가며 로드한 뒤, 등장 순서를 rank로 쓴다.

def millie_find_rank(page):
    return page.evaluate(
        """(title) => {
            const links = [...document.querySelectorAll('a[href^="/v4/book/"]')];
            const target = links.find(a => a.textContent.includes(title));
            if (!target) return null;
            const href = target.getAttribute('href');
            const ids = [];
            links.forEach(a => {
                const h = a.getAttribute('href');
                if (ids[ids.length - 1] !== h) ids.push(h);
            });
            const pos = ids.indexOf(href);
            return pos === -1 ? null : pos + 1;
        }""",
        MILLIE_BOOK_TITLE,
    )


def collect_millie(browser):
    out = {"category_rank": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(MILLIE_CATEGORY_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector('a[href^="/v4/book/"]', timeout=20000)

        # "더보기"를 눌러도 안 나오면 목록이 끝났거나(권외) 최대 시도 횟수를 채운 것.
        for _ in range(15):
            if millie_find_rank(page) is not None:
                break
            more = page.query_selector("button:has-text('더보기')")
            if not more:
                break
            more.click()
            page.wait_for_timeout(1200)

        out["category_rank"] = millie_find_rank(page)
        log("밀리의서재 자기계발>기획 인기순:", out["category_rank"] or "권외")
    except Exception as e:
        log("!! 밀리의서재 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 「UX의 언어들」 보조 지표 -- 메인 트래커(cinaeng)가 안 보는 카테고리만.
# 예스24는 이 책 항목이 없어 대상이 아니고, 알라딘/교보 각각 하나씩만 추가한다.

def collect_ux_extra(browser):
    out = {"aladin_ad_rank": None, "kyobo_strategy_rank": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        out["aladin_ad_rank"] = aladin_category_rank(page, UX_ALADIN_CID_AD, UX_ALADIN_ITEM_ID)
        log("UX의 언어들 · 알라딘 광고/홍보/PR:", out["aladin_ad_rank"] or "권외")
    except Exception as e:
        log("!! UX의 언어들 알라딘 보조 수집 실패:", e)

    try:
        out["kyobo_strategy_rank"] = kyobo_pos_in_list(
            page, f"https://store.kyobobook.co.kr/category/domestic/{UX_KYOBO_CID_STRATEGY}/best", UX_KYOBO_CODE
        )
        log("UX의 언어들 · 교보 경영전략일반:", out["kyobo_strategy_rank"] or "권외")
    except Exception as e:
        log("!! UX의 언어들 교보 보조 수집 실패:", e)
    finally:
        page.close()
    return out


def save_ux_extra(record, today):
    data = {"history": []}
    if os.path.exists(UX_OUT_PATH):
        with open(UX_OUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("history", [])
    upsert(data["history"], today, dict(record, date=today))
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(UX_OUT_PATH), exist_ok=True)
    with open(UX_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ────────────────────────────────────────────────────────────

def upsert(history, today, record):
    """같은 날짜 레코드가 있으면 덮어쓴다 (재실행 대비, idempotent)."""
    for i, entry in enumerate(history):
        if entry["date"] == today:
            history[i] = record
            return
    history.append(record)
    history.sort(key=lambda e: e["date"])


def main():
    print("=== 기획자의 질문법 순위 수집 ===")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    yes24 = collect_yes24()
    aladin = collect_aladin_product()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            aladin.update(collect_aladin_categories(browser))
            kyobo = collect_kyobo(browser)
            ridi = collect_ridi(browser)
            millie = collect_millie(browser)
            ux_extra = collect_ux_extra(browser)
        finally:
            browser.close()

    record = {"date": today, "yes24": yes24, "aladin": aladin, "kyobo": kyobo, "ridibooks": ridi, "millie": millie}
    save_ux_extra(ux_extra, today)

    data = {"book": BOOK, "history": []}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["book"] = BOOK
    data.setdefault("history", [])
    upsert(data["history"], today, record)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료 — 총 {len(data['history'])}개 레코드")


if __name__ == "__main__":
    main()
