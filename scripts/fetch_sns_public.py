"""
로그인 없이 공개 페이지에서 팔로워/구독자/이웃 수가 보이는 SNS 채널
3개(브런치·네이버 블로그·로켓펀치)를 매일 자동 수집해
assets/data/sns-insight.json에 날짜별로 쌓는다.

## 왜 3개만인가

나머지 5개(링크드인·페이스북·인스타그램·스레드·리멤버)는 로그인해야만
숫자가 보인다. 서버에서 로그인 세션 없이 접근하면 아예 값을 못 읽고,
억지로 뚫는 것은 약관 위반·계정 정지 위험이라 하지 않는다. 특히 링크드인은
공식 API마저 팔로워 수를 파트너 전용으로 막아뒀고 신규 파트너 접수도
닫혀 있다(2026-08-30 확인). 그 5개는 계속 크롬 확장(_sns-extension/)이
사장님 브라우저에서 수집한다 -- 이 스크립트는 그걸 대체하는 게 아니라
"안 돌려도 알아서 채워지는 부분"을 늘리는 것이다.

## 확장 프로그램과 같은 파일을 쓴다

둘 다 assets/data/sns-insight.json에 쓰지만 **서로 다른 채널 키만**
건드리므로 충돌하지 않는다. 이 스크립트는 SCRAPE_CHANNELS에 있는 키
외에는 절대 손대지 않는다(확장이 모은 링크드인 기록 등을 날리지 않도록).

## 설계 원칙 (fetch_book_insight.py와 동일)

- 채널 하나가 깨져도 나머지는 정상 수집된다(채널 단위 try/except).
- 값을 못 읽으면 그 채널은 그냥 건너뛴다 -- 0이나 null로 덮어쓰지 않는다.
  잘못된 값을 쌓는 것보다 그날 기록이 비는 게 낫다(모닝 브리핑이
  "수집 안 됨"으로 알려준다).
- 날짜는 KST 기준. UTC로 계산하면 새벽 실행분이 전부 "어제"로 잡혀
  전날 기록을 덮어쓰는 버그가 난다(도서 수집에서 실제로 겪은 사고).
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

OUT_PATH = os.path.join("assets", "data", "sns-insight.json")

# 이 스크립트가 건드리는 채널 키. 여기 없는 키(linkedin 등)는 크롬 확장의
# 영역이므로 읽기만 하고 절대 쓰지 않는다.
SCRAPE_CHANNELS = ("brunch", "naver_blog", "rocketpunch")


def log(*a):
    print(*a, flush=True)


def parse_count(text):
    """'구독자 271' / '이웃 6,743명' / '팔로워 890' 같은 문자열에서 숫자만.

    만/천 단위 축약(예: '1.2만')은 일부러 처리하지 않는다 -- 반올림된 값이라
    증감 추적에 쓰면 며칠씩 변화가 0으로 보인다. 정확한 숫자를 못 읽으면
    None을 반환해서 그날은 건너뛰는 편이 낫다.
    """
    if not text:
        return None
    t = text.replace(" ", "")
    # 소수점과 축약 단위까지 한 번에 잡아야 판별할 수 있다. 숫자만 먼저
    # 뽑으면 "1.2만"에서 앞의 1만 읽혀 12,000이 1로 저장된다.
    m = re.search(r"([\d,]{1,12}(?:\.\d+)?)\s*([만천억kKmM])?", t)
    if not m:
        return None
    num, unit = m.group(1), m.group(2)
    # 축약 표기(1.2만, 5천, 3.4K, 2M)는 반올림된 값이라 증감 추적에 못 쓴다.
    # 틀린 값을 쌓느니 그날은 건너뛴다.
    if unit or "." in num:
        return None
    try:
        n = int(num.replace(",", ""))
    except ValueError:
        return None
    # 0이나 비현실적으로 큰 값은 페이지 구조가 바뀌어 엉뚱한 숫자를 읽은
    # 것으로 보고 버린다.
    if n <= 0 or n > 100_000_000:
        return None
    return n


def first_count_near(page, keywords):
    """키워드가 들어간 요소의 텍스트에서 숫자를 뽑는다.

    CSS 선택자를 박아두면 그쪽 페이지가 조금만 바뀌어도 깨진다. 크롬 확장이
    쓰는 방식과 같게 '키워드 주변 텍스트'로 느슨하게 찾는다.
    """
    for kw in keywords:
        try:
            loc = page.locator(f"text={kw}").first
            if loc.count() == 0:
                continue
            # 키워드 자체 텍스트에 숫자가 같이 있는 경우가 대부분이고,
            # 없으면 부모 요소까지 한 단계 넓혀 본다.
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


def collect_brunch(browser):
    """브런치 구독자 수 (https://brunch.co.kr/@simplifier)."""
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto("https://brunch.co.kr/@simplifier", timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        return first_count_near(page, ["구독자", "팔로워", "Followers"])
    finally:
        page.close()


NAVER_KEYWORDS = ["블로그 이웃", "서로이웃", "이웃", "구독자"]


def collect_naver_blog(browser):
    """네이버 블로그 이웃 수.

    PC판(blog.naver.com)은 본문이 iframe(#mainFrame) 안에 들어있고 그 안이
    늦게 채워져서, 처음 시도에서 숫자를 못 읽고 건너뛰었다(2026-08-30 실제
    실행 로그 확인). 그래서 iframe이 아예 없는 모바일판을 먼저 보고,
    실패하면 PC판 + iframe 대기로 넘어간다.
    """
    # 1순위: 모바일판 -- iframe 없이 프로필 영역에 이웃 수가 바로 있다.
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto("https://m.blog.naver.com/simplifiers", timeout=45000)
        page.wait_for_load_state("networkidle", timeout=20000)
        n = first_count_near(page, NAVER_KEYWORDS)
        if n is not None:
            return n
    except Exception as e:
        log(f"    (네이버 모바일판 실패, PC판으로 재시도 — {type(e).__name__})")
    finally:
        page.close()

    # 2순위: PC판 -- iframe이 실제로 채워질 때까지 기다린 뒤 프레임까지 뒤진다.
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto("https://blog.naver.com/simplifiers", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(3000)  # iframe 내부 렌더 여유

        n = first_count_near(page, NAVER_KEYWORDS)
        if n is not None:
            return n

        for frame in page.frames:
            if frame == page.main_frame:
                continue
            for kw in NAVER_KEYWORDS:
                try:
                    loc = frame.locator(f"text={kw}").first
                    if loc.count() == 0:
                        continue
                    for target in (loc, loc.locator("xpath=..")):
                        try:
                            v = parse_count(target.inner_text(timeout=4000))
                        except Exception:
                            v = None
                        if v is not None:
                            return v
                except Exception:
                    continue
        return None
    finally:
        page.close()


def collect_rocketpunch(browser):
    """로켓펀치 팔로워 수 (https://www.rocketpunch.com/@simplfier).

    핸들의 'simplfier'는 오타가 아니라 실제 계정 주소다(사이트 곳곳의
    링크와 동일).
    """
    page = browser.new_page(user_agent=UA, locale="ko-KR")
    try:
        page.goto("https://www.rocketpunch.com/@simplfier", timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        return first_count_near(page, ["팔로워", "Followers"])
    finally:
        page.close()


COLLECTORS = {
    "brunch": ("브런치", collect_brunch),
    "naver_blog": ("네이버 블로그", collect_naver_blog),
    "rocketpunch": ("로켓펀치", collect_rocketpunch),
}


def upsert(records, today, count, captured_at):
    """같은 날짜 기록이 이미 있으면 갱신, 없으면 추가 후 날짜순 정렬."""
    record = {"date": today, "count": count, "capturedAt": captured_at}
    for i, entry in enumerate(records):
        if entry.get("date") == today:
            records[i] = record
            return
    records.append(record)
    records.sort(key=lambda e: e.get("date", ""))


def main():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    captured_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    data = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            data = json.load(f)

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for key in SCRAPE_CHANNELS:
                label, fn = COLLECTORS[key]
                try:
                    n = fn(browser)
                except Exception as e:
                    n = None
                    log(f"  {label}: 수집 실패 — {type(e).__name__}: {e}")
                if n is None:
                    log(f"  {label}: 숫자를 못 읽어 건너뜀 (기존 기록은 그대로 둠)")
                else:
                    log(f"  {label}: {n:,}")
                    results[key] = n
        finally:
            browser.close()

    if not results:
        log("수집된 채널이 없습니다. 파일을 건드리지 않고 종료합니다.")
        return

    for key, n in results.items():
        data.setdefault(key, [])
        upsert(data[key], today, n, captured_at)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log(f"저장 완료 — {len(results)}개 채널 ({today}) → {OUT_PATH}")


if __name__ == "__main__":
    main()
