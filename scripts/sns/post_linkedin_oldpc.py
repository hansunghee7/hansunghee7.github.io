#!/usr/bin/env python3
"""링크드인(한성희) 글 게시 레시피 (구PC 작업실 9227, 2026-10-15 마야).
post_rocketpunch.py와 같은 방식: 구PC 무인 크롬(링크드인 로그인됨)을 CDP로 잡아 사람이 하는 순서대로 한다.
순서: 피드 → 글쓰기 시작 → (이미지 먼저 넣어 링크 미리보기 카드를 피함) → 본문 입력(문단 사이 빈 줄은 Enter 두 번) → 게시 직전 화면 저장
→ (--post일 때만) 게시 → 내 활동 맨 위 글 확인. 기본은 모의 실행(끝까지 채우고 화면 저장 뒤 창을 닫는다).
사용: venv/bin/python post_linkedin.py --text out/maya/li639.txt --image out/maya/cover639.jpg [--post]
"""
import argparse, json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 9227
OUT = Path.home() / "workshop" / "out" / "maya"


def shot(pg, name):
    p = OUT / f"li_{name}.png"
    pg.screenshot(path=str(p))
    return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    text = Path(a.text).read_text(encoding="utf-8").strip()
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    res = {"chars": len(text), "paragraphs": len(paras), "posted": False, "steps": []}
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        pg = b.contexts[0].new_page()
        pg.set_viewport_size({"width": 1280, "height": 900})
        try:
            pg.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(6000)
            res["url"] = pg.url
            btn = pg.get_by_role("button", name=re.compile(r"(글 올리기|게시글 시작|Start a post)"))
            res["start_buttons"] = btn.count()
            if not res["start_buttons"]:
                res["shot"] = shot(pg, "nostart")
                res["status"] = "STOP"; res["why"] = "글쓰기 시작 버튼 없음(로그인 확인)"
                print(json.dumps(res, ensure_ascii=False)); return 1
            btn.first.click(); pg.wait_for_timeout(3000)
            res["steps"].append("opened"); res["shot_open"] = shot(pg, "open")
            # 이미지 먼저: 미디어 버튼 → 파일 입력에 올린다(링크 미리보기 카드를 피하려고)
            media = pg.get_by_role("button", name=re.compile(r"^(미디어|사진|Add media|Photo)$"))
            res["media_buttons"] = media.count()
            try:
                with pg.expect_file_chooser(timeout=8000) as fc:
                    media.first.click()
                fc.value.set_files(a.image)
                pg.wait_for_timeout(5000)
                res["steps"].append("image_set"); res["shot_image"] = shot(pg, "image")
                nxt = pg.get_by_role("button", name=re.compile(r"^(다음|Next)$"))
                if nxt.count():
                    nxt.first.click(); pg.wait_for_timeout(3000); res["steps"].append("next")
            except Exception as e:
                res["image_error"] = str(e)[:200]
                res["shot_image_err"] = shot(pg, "image_err")
            # 본문
            ed = pg.locator("div.ql-editor[contenteditable=true], div[role=textbox][contenteditable=true]").first
            ed.wait_for(timeout=15000)
            ed.click(); pg.wait_for_timeout(500)
            for i, para in enumerate(paras):
                if i:
                    pg.keyboard.press("Enter"); pg.keyboard.press("Enter")
                for j, line in enumerate(para.split("\n")):
                    if j:
                        pg.keyboard.press("Shift+Enter")
                    pg.keyboard.insert_text(line)
                pg.wait_for_timeout(150)
            pg.wait_for_timeout(2500)
            res["steps"].append("typed")
            res["editor_chars"] = len(ed.inner_text())
            etxt = ed.inner_text()
            res["has_link_line"] = "simplifier.co.kr/logs/639" in etxt
            res["has_first_line"] = etxt.strip().startswith("열심히는 했는데")
            pg.mouse.move(640, 400); pg.mouse.wheel(0, 4000); pg.wait_for_timeout(1500)
            res["shot_bottom"] = shot(pg, "bottom")
            pg.mouse.wheel(0, -8000); pg.wait_for_timeout(800)
            res["shot_filled"] = shot(pg, "filled")
            # 링크 미리보기 카드가 생겼으면 닫는다(X 버튼)
            for nm in (r"(링크 미리보기 삭제|미리보기 닫기|Dismiss)",):
                d = pg.get_by_role("button", name=re.compile(nm))
                if d.count():
                    d.first.click(); pg.wait_for_timeout(1000); res["steps"].append("preview_closed")
            if a.post:
                post = pg.get_by_role("button", name=re.compile(r"^(게시물|게시|Post)$")).last
                post.click(timeout=10000); pg.wait_for_timeout(8000)
                res["steps"].append("post_clicked")
                pg.goto("https://www.linkedin.com/in/simplifier/recent-activity/all/", wait_until="domcontentloaded")
                pg.wait_for_timeout(7000)
                top = pg.locator("body").inner_text()
                res["posted"] = "숫자로 증명되지 않는 땀방울" in top or "열심히는 했는데 숫자는 그대로" in top
                res["shot_after"] = shot(pg, "after")
            else:
                pg.keyboard.press("Escape"); pg.wait_for_timeout(1500)
                disc = pg.get_by_role("button", name=re.compile(r"(삭제|Discard)"))
                if disc.count():
                    disc.first.click()
                res["status"] = "DRYRUN"
        finally:
            try:
                pg.close()
            except Exception:
                pass
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
