#!/usr/bin/env python3
"""라이브 페이지를 실제 브라우저(Playwright)로 열어 계산된 스타일과
스크린샷을 실측한다. 여러 세션(시안·마야 등)이 이 저장소나
simplifier.co.kr, *.run.app 같은 실제 도메인에 직접 접속하지 못해(원격
클라우드 세션의 네트워크 정책, egress 차단) 배포 결과를 눈으로 확인할
방법이 없었던 문제(2026-09-14, 사장님 보고)를 GitHub Actions 러너(제약
없는 인터넷)를 대신 실행 채널로 써서 해결한다.

fetch_naver_content.py와 같은 방식(Playwright로 공개 페이지 직접 읽기)을
재사용한다 -- 새 인프라가 아니라 이미 검증된 패턴의 확장이다.

출력은 전부 텍스트라 세션이 get_job_logs로 그대로 읽을 수 있다:
  1. --selector를 줬으면 그 요소의 계산된 스타일(font-family/font-weight/
     font-size/line-height/color) + innerText 앞부분을 그대로 찍는다 --
     "폰트 두께가 몇인가" 같은 질문은 스크린샷을 눈으로 볼 필요 없이 이
     텍스트만으로 답이 나온다(더 정확하기도 하다, 사람 눈보다).
  2. 스크린샷(선택 요소가 있으면 그 요소만 클립, 없으면 뷰포트 전체)을
     PNG로 찍어 base64로 인코딩해 고정 마커 사이에 찍는다. 호출 세션은
     그 블록을 잘라 `base64 -d`로 로컬 PNG 파일로 복원하고, Read 도구로
     실제 이미지를 볼 수 있다(이미지 판독이 필요한 경우에만 이 단계까지
     쓴다 -- 텍스트로 충분하면 1번에서 끝).

사용법:
    pip install playwright && playwright install --with-deps chromium
    python3 scripts/verify_live_page.py --url https://simplifier.co.kr/ \\
        --selector ".hero h1" --wait-ms 1500
"""

from __future__ import annotations

import argparse
import base64
import sys

SCREENSHOT_MARK_START = "===SCREENSHOT_BASE64_START==="
SCREENSHOT_MARK_END = "===SCREENSHOT_BASE64_END==="

COMPUTED_STYLE_PROPS = [
    "fontFamily",
    "fontWeight",
    "fontSize",
    "lineHeight",
    "color",
    "backgroundColor",
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True, help="확인할 실제 주소")
    p.add_argument("--selector", help="계산된 스타일·클립 스크린샷을 뽑을 CSS 셀렉터(생략하면 뷰포트 전체 스크린샷만)")
    p.add_argument("--wait-ms", type=int, default=1000, help="페이지 로드 후 추가로 기다릴 시간(ms), 기본 1000")
    p.add_argument("--viewport-width", type=int, default=1280)
    p.add_argument("--viewport-height", type=int, default=900)
    p.add_argument("--no-screenshot", action="store_true", help="스크린샷 없이 계산된 스타일/텍스트만 출력")
    args = p.parse_args()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": args.viewport_width, "height": args.viewport_height})
        print(f"=== GET {args.url} ===")
        resp = page.goto(args.url, wait_until="networkidle", timeout=30_000)
        print(f"상태 코드: {resp.status if resp else 'N/A'}")
        page.wait_for_timeout(args.wait_ms)

        target = page
        clip = None
        if args.selector:
            print(f"\n=== 셀렉터 '{args.selector}' ===")
            try:
                page.wait_for_selector(args.selector, timeout=10_000)
            except Exception as exc:  # noqa: BLE001
                print(f"셀렉터를 못 찾았습니다: {exc!r}")
                browser.close()
                return 1
            handle = page.query_selector(args.selector)
            if handle is None:
                print("셀렉터를 못 찾았습니다(query_selector가 None)")
                browser.close()
                return 1
            styles = handle.evaluate(
                """(el, props) => {
                    const cs = getComputedStyle(el);
                    const out = {};
                    for (const p of props) out[p] = cs[p];
                    return out;
                }""",
                COMPUTED_STYLE_PROPS,
            )
            for k, v in styles.items():
                print(f"  {k}: {v}")
            text = (handle.inner_text() or "").strip()
            print(f"  innerText(앞 200자): {text[:200]!r}")
            box = handle.bounding_box()
            if box:
                clip = {
                    "x": max(box["x"] - 8, 0),
                    "y": max(box["y"] - 8, 0),
                    "width": box["width"] + 16,
                    "height": box["height"] + 16,
                }

        if not args.no_screenshot:
            print(f"\n=== 스크린샷 ({'셀렉터 클립' if clip else '뷰포트 전체'}) ===")
            if clip:
                png_bytes = page.screenshot(clip=clip)
            else:
                png_bytes = page.screenshot()
            b64 = base64.b64encode(png_bytes).decode("ascii")
            print(f"(PNG {len(png_bytes)} bytes, base64 {len(b64)} chars)")
            print(SCREENSHOT_MARK_START)
            print(b64)
            print(SCREENSHOT_MARK_END)

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
