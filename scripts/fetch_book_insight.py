"""
「기획자의 질문법」과 「UX의 언어들」 두 책의 베스트셀러 순위·판매지수를
예스24·알라딘·교보문고(+리디북스·밀리의서재는 질문법만)에서 매일 수집해
각각 assets/data/book-insight.json, assets/data/ux-book-insight.json에
날짜별로 쌓는다.

원래 「UX의 언어들」은 cinaeng/ux-book-tracker(외부 저장소, Node.js+Playwright)를
서버사이드에서 그대로 미러링만 했었다. 이번에 「기획자의 질문법」과 같은 방식
(이 저장소가 직접 스크래핑)으로 통일했다 -- 이유 두 가지:
  1) 그쪽 사이트/스키마가 바뀌면 우리 페이지도 같이 흔들리는 외부 의존을 없애고,
     그쪽이 몇 달째 계속 null만 주던 알라딘 디자인/브랜드 랭크도(실제로는
     값이 있음을 직접 확인) 우리가 직접 채울 수 있게 하려고.
  2) 소스 코드가 두 갈래(Node 미러 + Python 스크래퍼)로 나뉘어 있던 걸 하나로
     합쳐 유지보수 지점을 줄이려고.
예전 cinaeng 히스토리는 assets/data/ux-book-insight.json으로 한 번
마이그레이션해서 그대로 보존했다 (scripts/mirror_ux_book.py,
assets/data/ux-book-history.json, ux-book-extra.json은 더 이상 안 씀).

"그쪽 페이지 변경이 이쪽 페이지에 최대한 안 번지게" 하는 게 이 스크립트의
핵심 설계 원칙이다 -- 그래서 두 겹으로 감싼다:
  - 소스 하나(예: 알라딘 카테고리 하나)가 깨져도 그 값만 null로 남고 나머지는
    정상 수집된다(항목별 try/except).
  - 책 하나가 통째로 실패해도(예: 그 책의 사이트 구조가 크게 바뀌어 전체가
    깨짐) 다른 책 수집·저장은 전혀 영향받지 않는다(책 단위 try/except,
    main()에서 확인).
교보문고 "주간베스트" 배지도 원래 "자기계발"처럼 카테고리명을 정규식에
박아뒀었는데, 책마다(예: UX의 언어들은 "경제/경영") 카테고리명이 달라서
그 페이지가 다른 카테고리로 재진열되기만 해도 깨지는 문제가 있었다.
카테고리명을 안 가리고 숫자만 읽도록 일반화했다.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import urllib.request

from playwright.sync_api import sync_playwright

# 로컬(Windows, cp949) 콘솔에서 em dash 등 일부 문자를 못 찍어 print()가
# 죽는 바람에, 이미 파일 저장까지 끝난 뒤인데도 "전체 실패"로 잘못 보이는
# 문제가 있었다. GitHub Actions(ubuntu, UTF-8)에서는 원래 안 나던 문제지만,
# 로컬 디버깅 편의를 위해 항상 UTF-8로 강제한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# "오늘 날짜"는 KST 기준으로 계산해야 한다. UTC로 계산하면 00:00~09:00 KST에
# 도는 실행(예: 06:41 cron)이 전부 "어제"로 잡혀서, 그날의 진짜 어제 기록을
# 오늘 스크랩 값으로 덮어써버린다 (실제로 이 버그로 2026-08-27 기록이
# 2026-08-28 아침 실행 값에 덮어써짐 -- 확인됨).
KST = timezone(timedelta(hours=9))

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


def upsert(history, today, record):
    """같은 날짜 레코드가 있으면 덮어쓴다 (재실행 대비, idempotent)."""
    for i, entry in enumerate(history):
        if entry["date"] == today:
            history[i] = record
            return
    history.append(record)
    history.sort(key=lambda e: e["date"])


def save(out_path, book_meta, record, today):
    data = {"book": book_meta, "history": []}
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["book"] = book_meta
    data.setdefault("history", [])
    upsert(data["history"], today, record)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  저장 완료 — 총 {len(data['history'])}개 레코드 ({out_path})")


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


def yes24_category_rank(category_number, goods_id, max_pages=3):
    for page_no in range(1, max_pages + 1):
        url = (
            f"https://www.yes24.com/product/category/bestseller"
            f"?categoryNumber={category_number}&pageNumber={page_no}&pageSize=100"
        )
        rank = yes24_rank_in_list(get_html(url), goods_id)
        if rank:
            return rank
    return None


def collect_yes24_categories(goods_id, category_map):
    """category_map: {결과 키: 예스24 카테고리 번호}. 카테고리별 독립 try/except."""
    out = {}
    for key, cat in category_map.items():
        try:
            out[key] = yes24_category_rank(cat, goods_id)
            log(f"예스24 {key}:", out[key] or "권외")
        except Exception as e:
            out[key] = None
            log(f"!! 예스24 {key} 수집 실패:", e)
    return out


def collect_yes24_product(goods_id):
    out = {"sales_index": None, "reviews": 0, "rating": None}
    try:
        text = html_to_text(get_html(f"https://www.yes24.com/product/goods/{goods_id}"))
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

def collect_aladin_product(item_id):
    out = {"sales_point": None, "reviews": 0, "rating": None}
    try:
        text = html_to_text(get_html(f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}"))
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


def aladin_rank_on_page(page, cid, page_no, item_id):
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


def aladin_category_rank(page, cid, item_id, max_pages=1):
    for p in range(1, max_pages + 1):
        rank = aladin_rank_on_page(page, cid, p, item_id)
        if rank is not None:
            return rank
    return None


def collect_aladin_categories(browser, item_id, category_map):
    """category_map: {결과 키: 알라딘 CID}. 카테고리별 독립 try/except."""
    out = {}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        for key, cid in category_map.items():
            try:
                out[key] = aladin_category_rank(page, cid, item_id)
                log(f"알라딘 {key}:", out[key] or "권외")
            except Exception as e:
                out[key] = None
                log(f"!! 알라딘 {key} 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 교보문고 -- Next.js 클라이언트 렌더링이라 Playwright 필수

def kyobo_pos_in_list(page, url, code):
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


def collect_kyobo_categories(browser, code, category_map):
    """category_map: {결과 키: 교보 카테고리 경로}. 카테고리별 독립 try/except."""
    out = {}
    for key, path in category_map.items():
        page = browser.new_page(user_agent=UA, locale="ko-KR")
        try:
            out[key] = kyobo_pos_in_list(page, f"https://store.kyobobook.co.kr/category/domestic/{path}/best", code)
            log(f"교보 {key}:", out[key] or "권외")
        except Exception as e:
            out[key] = None
            log(f"!! 교보 {key} 수집 실패:", e)
        finally:
            page.close()
    return out


def collect_kyobo_product(browser, code, want_reviews=True):
    """상품 페이지의 "주간베스트 N위" 배지 + (선택) 리뷰/평점.
    배지 카테고리명(자기계발/경제·경영 등)은 책마다 다르고 언제든 바뀔 수
    있어서, 이름은 무시하고 숫자만 읽는다."""
    out = {"badge_rank": None, "reviews": 0, "rating": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(f"https://product.kyobobook.co.kr/detail/{code}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("main", timeout=25000)
        if want_reviews:
            try:
                page.wait_for_function("() => /리뷰\\s*\\(?\\s*\\d+/.test(document.body.innerText)", timeout=15000)
            except Exception:
                pass
        text = page.evaluate("() => document.body.innerText")

        badge = re.search(r"주간베스트\s*[^\d]{0,12}?(\d[\d,]*)\s*위", text)
        if badge:
            out["badge_rank"] = int(badge.group(1).replace(",", ""))

        if want_reviews:
            rv = re.search(r"리뷰\s*\(\s*(\d+)\s*\)", text) or re.search(r"리뷰\s+(\d+)\b", text)
            if rv:
                out["reviews"] = int(rv.group(1))
            rt = re.search(r"(\d{1,2}(?:\.\d)?)\s*리뷰\s+\d+\b", text)
            if rt:
                v = float(rt.group(1))
                out["rating"] = v if out["reviews"] > 0 and 0 < v <= 10 else None

        log("교보 뱃지:", out["badge_rank"] or "표시 없음", "· 리뷰:", out["reviews"])
    except Exception as e:
        log("!! 교보문고 상품 페이지 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 리디북스 -- 「기획자의 질문법」 전용. 베스트셀러 순위 없음(확인함).
# 평점/리뷰만 참고용으로 가볍게.

def collect_ridi(browser, ridi_id):
    out = {"rating_count": 0, "rating": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(f"https://ridibooks.com/books/{ridi_id}", wait_until="domcontentloaded", timeout=60000)
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
# 밀리의서재 -- 「기획자의 질문법」 전용. 검색은 로그인 필요라 자동화 대상이
# 아니지만, 카테고리 브라우즈 페이지(자기계발 > 기획, "인기 순" 정렬)는
# 로그인 없이 접근되고 이 책도 그 목록에 있다. "더보기" 버튼으로 계속
# 불러오는 무한 스크롤형 목록이라 페이지네이션 URL이 없어, Playwright로
# 버튼을 눌러가며 이 책이 나타날 때까지 로드한 뒤 등장 순서를 rank로 쓴다.

def millie_find_rank(page, title):
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
        title,
    )


def collect_millie(browser, category_url, title):
    out = {"category_rank": None}
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto(category_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector('a[href^="/v4/book/"]', timeout=20000)

        # "더보기"를 눌러도 안 나오면 목록이 끝났거나(권외) 최대 시도 횟수를 채운 것.
        for _ in range(15):
            if millie_find_rank(page, title) is not None:
                break
            more = page.query_selector("button:has-text('더보기')")
            if not more:
                break
            more.click()
            page.wait_for_timeout(1200)

        out["category_rank"] = millie_find_rank(page, title)
        log("밀리의서재 자기계발>기획 인기순:", out["category_rank"] or "권외")
    except Exception as e:
        log("!! 밀리의서재 수집 실패:", e)
    finally:
        page.close()
    return out


# ────────────────────────────────────────────────────────────
# 책별 수집 -- 책 하나가 통째로 실패해도 다른 책에 영향 안 주도록,
# main()에서 이 함수들을 각각 try/except로 감싼다.

def fetch_question_book(today):
    """「기획자의 질문법」(한성희 저, 파지트, 2025-06-13)."""
    print("\n=== 기획자의 질문법 순위 수집 ===")
    OUT_PATH = "assets/data/book-insight.json"
    BOOK = {"title": "기획자의 질문법", "author": "한성희", "publisher": "파지트", "pub_date": "2025-06-13"}

    YES24_GOODS_ID = "147079674"
    YES24_CATS = {
        "category_rank": "001001026003",       # 국내도서 > 자기계발 > 기획/정보/시간관리
        "category2_rank": "001001025001004",   # 국내도서 > 경제경영 > CEO/비즈니스맨 > 기획/정보/시간관리
    }
    ALADIN_ITEM_ID = "364986311"
    ALADIN_CATS = {
        "planning_rank": "70229",  # 자기계발 > 기획/보고 > 기획
        "info_mgmt_rank": "70222",  # 자기계발 > 시간관리/정보관리 > 정보관리
    }
    KYOBO_CODE = "S000216681258"
    KYOBO_CATS = {"category_rank": "150503"}  # 자기계발 > 비즈니스능력계발 > 기획력
    RIDI_ID = "2234005394"
    MILLIE_URL = "https://www.millie.co.kr/v3/search/3depth/1298/?parentSeq=1287&nav_hidden=y"  # 자기계발 > 기획, 인기 순
    MILLIE_TITLE = "기획자의 질문법"

    yes24 = collect_yes24_categories(YES24_GOODS_ID, YES24_CATS)
    yes24.update(collect_yes24_product(YES24_GOODS_ID))
    aladin = collect_aladin_product(ALADIN_ITEM_ID)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            aladin.update(collect_aladin_categories(browser, ALADIN_ITEM_ID, ALADIN_CATS))
            kyobo = collect_kyobo_categories(browser, KYOBO_CODE, KYOBO_CATS)
            kyobo.update(collect_kyobo_product(browser, KYOBO_CODE, want_reviews=False))
            ridi = collect_ridi(browser, RIDI_ID)
            millie = collect_millie(browser, MILLIE_URL, MILLIE_TITLE)
        finally:
            browser.close()

    record = {"date": today, "yes24": yes24, "aladin": aladin, "kyobo": kyobo, "ridibooks": ridi, "millie": millie}
    save(OUT_PATH, BOOK, record, today)


def fetch_ux_book(today):
    """「UX의 언어들」(한성희·신행철 저, 파지트).
    2026-08-28까지는 cinaeng/ux-book-tracker를 미러링했고, 그 이전 히스토리는
    assets/data/ux-book-insight.json으로 마이그레이션해서 보존했다."""
    print("\n=== UX의 언어들 순위 수집 ===")
    OUT_PATH = "assets/data/ux-book-insight.json"
    BOOK = {"title": "UX의 언어들", "author": "한성희·신행철", "publisher": "파지트"}

    YES24_GOODS_ID = "193444437"
    YES24_CATS = {
        "mkt_rank": "001001025009",         # 마케팅/세일즈
        "ad_rank": "001001025009006",       # 광고/홍보/PR
        "web_rank": "001001003020",         # 웹사이트
        "uxui_rank": "001001003020004",     # UX/UI
        "design_rank": "001001007003004",   # 디자인
        "econ_rank": "001001025",           # 경제경영 종합
    }
    ALADIN_ITEM_ID = "397807838"
    ALADIN_CATS = {
        "design_rank": "51089",  # 디자인이야기
        "brand_rank": "1632",    # 마케팅/브랜드
        "ad_rank": "268",        # 광고/홍보/PR
    }
    KYOBO_CODE = "S000220493173"
    KYOBO_CATS = {
        "uxui_cat": "331902",       # UX/UI
        "strategy_rank": "130701",  # 경영전략일반
    }

    yes24 = collect_yes24_categories(YES24_GOODS_ID, YES24_CATS)
    yes24.update(collect_yes24_product(YES24_GOODS_ID))
    aladin = collect_aladin_product(ALADIN_ITEM_ID)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            aladin.update(collect_aladin_categories(browser, ALADIN_ITEM_ID, ALADIN_CATS))
            kyobo = collect_kyobo_categories(browser, KYOBO_CODE, KYOBO_CATS)
            kyobo.update(collect_kyobo_product(browser, KYOBO_CODE, want_reviews=False))
        finally:
            browser.close()

    record = {"date": today, "yes24": yes24, "aladin": aladin, "kyobo": kyobo}
    save(OUT_PATH, BOOK, record, today)


def main():
    today = datetime.now(KST).strftime("%Y-%m-%d")

    try:
        fetch_question_book(today)
    except Exception as e:
        log("!!! 기획자의 질문법 수집 전체 실패 (UX의 언어들에는 영향 없음):", e)

    try:
        fetch_ux_book(today)
    except Exception as e:
        log("!!! UX의 언어들 수집 전체 실패 (기획자의 질문법에는 영향 없음):", e)


if __name__ == "__main__":
    main()
