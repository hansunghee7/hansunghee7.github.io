# -*- coding: utf-8 -*-
"""네이버 블로그(스마트에디터 ONE)에 제목·본문·대표 이미지까지 채워 **저장(임시저장)**만
한다. 발행은 안 누른다(사장님이 휴대폰 앱에서 확인 후 직접 발행 — 2026-09-28 지시).

에디터가 iframe(PostWriteForm.naver) 안에 있어 프레임을 먼저 찾아야 한다.
로그인 세션은 scripts/sns/playwright_login.py로 저장한
C:/work/_ops/sns_playwright_state/naver.json을 그대로 쓴다.

사용법:
  python scripts/sns/post_naver.py --blog-id simplifiers --title "제목" --body-file 본문.txt --cover 이미지.jpg
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_PATH = r"C:\work\_ops\sns_playwright_state\naver.json"


def post(blog_id: str, title: str, body: str, cover_path: str | None) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(storage_state=STATE_PATH)
        page = ctx.new_page()
        page.goto(f"https://blog.naver.com/{blog_id}?Redirect=Write&")
        page.wait_for_timeout(3000)

        fr = next(f for f in page.frames if "PostWriteForm" in f.url)

        # "작성 중인 글이 있습니다" 팝업이 뜨면 취소(새 글로 시작).
        try:
            fr.locator("button.se-popup-button-cancel").click(timeout=6000)
        except Exception:
            pass
        page.wait_for_timeout(500)

        # 우측 "도움말" 패널이 열려 있으면 닫는다 -- 열려 있으면 표지(배경사진) 아이콘 클릭이
        # 막힌다(2026-09-28 사장님이 실측 화면을 보고 직접 알려준 원인).
        page.mouse.click(1222, 42)
        page.wait_for_timeout(300)

        if cover_path:
            # 제목이 비어 있는 상태에서, 제목 위로 마우스를 올리면 뜨는
            # "내 컴퓨터에서 배경사진 첨부" 아이콘(표지/대표 이미지 전용, 본문에 사진을
            # 끼워 넣는 툴바의 "사진" 버튼과는 다르다). 제목·본문을 먼저 채우면 이 아이콘이
            # 다시 숨어 안 잡힌다(실측 확인, 2026-09-28) — 그래서 커버를 가장 먼저 붙인다.
            title_box = fr.locator(".se-documentTitle").bounding_box()
            page.mouse.move(title_box["x"] + title_box["width"] / 2, title_box["y"])
            page.wait_for_timeout(500)
            with page.expect_file_chooser() as fc_info:
                fr.get_by_title("내 컴퓨터에서 배경사진 첨부").click(timeout=5000)
            fc_info.value.set_files(cover_path)
            page.wait_for_timeout(2000)

        try:
            fr.locator(".se-documentTitle").click(timeout=10000)
            page.keyboard.type(title)
            page.keyboard.press("Enter")  # 제목 -> 본문 첫 줄로 이동
            page.keyboard.type(body)
        except Exception:
            page.screenshot(path=r"C:\work\_ops\sns_playwright_state\naver_fail.png", full_page=True)
            Path(r"C:\work\_ops\sns_playwright_state\naver_fail.html").write_text(fr.content(), encoding="utf-8")
            raise

        page.wait_for_timeout(1000)
        page.screenshot(path=r"C:\work\_ops\sns_playwright_state\naver_before_save.png", full_page=True)
        # 글쓰기 화면에 기본으로 열려 있는 "도움말" 패널을 닫는다(안 닫으면 저장 버튼을 가로막음).
        try:
            fr.locator(".se-help-panel-close-button").click(timeout=3000)
        except Exception:
            pass
        page.wait_for_timeout(500)
        fr.get_by_text("저장", exact=True).first.click()
        page.wait_for_timeout(2000)
        # 저장 확인(카테고리 선택 등) 팝업이 뜨면 스크린샷만 남기고 멈춘다 -- 발행 경로로
        # 잘못 들어가지 않기 위해 여기서 더 클릭하지 않는다.
        page.screenshot(path=r"C:\work\_ops\sns_playwright_state\naver_after_save.png", full_page=True)
        url = page.url
        browser.close()
        return url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blog-id", default="simplifiers")
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--cover")
    a = ap.parse_args()
    body = Path(a.body_file).read_text(encoding="utf-8")
    url = post(a.blog_id, a.title, body, a.cover)
    print("OK", url)


if __name__ == "__main__":
    main()
