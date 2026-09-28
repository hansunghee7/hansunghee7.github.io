"""브런치·네이버블로그 자동 등록용 로그인 세션 1회 저장.

탐지 회피 도구(undetected-chromedriver 등)는 안 쓴다(사장님 지시 2026-09-28,
근거: docs/SNS_자동게시_설계안.md). 사장님이 이 창에서 직접 로그인(진짜 사용자
로그인)하면, 그 쿠키를 저장해서 다음부터는 로그인을 다시 안 하는 방식이다.

사용법:
  python scripts/sns/playwright_login.py brunch
  python scripts/sns/playwright_login.py naver

창이 뜨면 사장님이 직접 로그인한다. 로그인 완료 신호는 터미널 Enter가 아니라
신호 파일(다른 창에서 이 스크립트를 부른 세션이 만든다)로 받는다 — 이 스크립트가
백그라운드로 돌기 때문에 사장님이 이 터미널에 직접 입력할 수 없어서다.
최대 10분 기다리고, 신호가 없으면 그냥 종료한다(다시 실행하면 됨).

저장 위치: C:/work/_ops/sns_playwright_state/<플랫폼>.json (저장소 밖, git 대상 아님)
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_DIR = Path(r"C:\work\_ops\sns_playwright_state")
URLS = {
    "brunch": "https://brunch.co.kr/write",
    "naver": "https://blog.naver.com/",
}
TIMEOUT_SEC = 600


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in URLS:
        sys.exit(f"사용법: python {sys.argv[0]} brunch|naver")
    platform = sys.argv[1]
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = STATE_DIR / f"{platform}.json"
    ready_flag = STATE_DIR / f".ready_{platform}"
    ready_flag.unlink(missing_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(URLS[platform])
        print(f"[{platform}] 창에서 직접 로그인하세요. 로그인 완료되면 세션에 알려주세요.")
        waited = 0
        while not ready_flag.exists() and waited < TIMEOUT_SEC:
            time.sleep(2)
            waited += 2
        if not ready_flag.exists():
            print("시간 초과(10분), 로그인 저장 안 함. 다시 실행하세요.")
            browser.close()
            return
        ready_flag.unlink(missing_ok=True)
        context.storage_state(path=str(state_path))
        browser.close()
    print(f"저장 완료: {state_path}")


if __name__ == "__main__":
    main()
