# -*- coding: utf-8 -*-
"""브런치에 제목·본문·표지 이미지까지 채워 **임시저장**만 한다. 발행은 절대 안 누른다
(사장님이 휴대폰 브런치 앱에서 확인 후 직접 발행 클릭 — 2026-09-28 사장님 지시).

탐지 회피 도구(undetected-chromedriver 등)는 안 쓴다. 대신 실측으로 확인한 제약:
- 헤드리스(화면 없이)로 돌리면 로그인이 풀린다 → 반드시 headless=False로 돌린다
  (사장님 PC가 켜져 있을 때만 실행 가능, 화면이 잠깐 나타났다 사라진다).
- 로그인 세션은 scripts/sns/playwright_login.py로 미리 저장해 둔
  C:/work/_ops/sns_playwright_state/brunch.json을 그대로 쓴다(재로그인 안 함).

사용법:
  python scripts/sns/post_brunch.py --title "제목" --body-file 본문.txt --cover 이미지.jpg
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_PATH = r"C:\work\_ops\sns_playwright_state\brunch.json"


def post(title: str, body: str, cover_path: str | None) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(storage_state=STATE_PATH)
        page = ctx.new_page()
        page.goto("https://brunch.co.kr/write")
        page.wait_for_timeout(2000)

        # 임시저장된 글이 있으면 묻는 팝업 -> 새 글로 시작(아니요)
        try:
            page.get_by_text("아니요", exact=True).click(timeout=3000)
        except Exception:
            pass
        page.wait_for_timeout(500)

        # 제목·본문은 placeholder가 CSS 가상요소라 get_by_text로 못 찾는다.
        # 실제 구조(froala 에디터): h1.cover_title(제목) / div.wrap_body(본문).
        try:
            page.locator("h1.cover_title").click(timeout=10000)
            page.keyboard.type(title)
            page.locator("div.wrap_body").click(timeout=5000)
            page.keyboard.type(body)
        except Exception:
            page.screenshot(path=r"C:\work\_ops\sns_playwright_state\brunch_fail.png", full_page=True)
            Path(r"C:\work\_ops\sns_playwright_state\brunch_fail.html").write_text(page.content(), encoding="utf-8")
            raise

        if cover_path:
            # 보이는 버튼을 클릭하면 네이티브 파일창이 뜨므로, 숨은 input에 바로 넣는다.
            page.locator('input[type="file"][title="커버 이미지"]').set_input_files(cover_path)
            page.wait_for_timeout(2000)

        page.get_by_text("저장", exact=True).click()
        page.wait_for_timeout(2000)
        saved = "저장되었습니다" in page.content()
        url = page.url
        browser.close()
        if not saved:
            raise RuntimeError(f"저장 확인 실패, url={url}")
        return url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--cover")
    a = ap.parse_args()
    body = Path(a.body_file).read_text(encoding="utf-8")
    url = post(a.title, body, a.cover)
    print("OK", url)


if __name__ == "__main__":
    main()
