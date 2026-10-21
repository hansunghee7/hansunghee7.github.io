#!/usr/bin/env python3
"""리멤버 커넥트 글 게시 레시피 (구PC 작업실 9227, 2026-10-21 마야). post_rocketpunch.py와 같은 방식.

순서: 피드 → "게시물 작성" → 본문 입력(1,500자 한도) → "주제 선택" 창에서 커리어·자기계발 → 그 창의 "등록"
→ "사진 추가" → 파일 입력에 표지 → "첨부" → (--post일 때만) 글쓰기 창의 "등록" → 안내 창이 뜨면 "등록하기".
기본은 모의 실행(--post 없음): 끝까지 채우고 상태만 읽은 뒤 창을 닫는다. 공개 게시는 --post를 줄 때만.
사용: python post_remember.py --file post.txt [--image 표지.jpg] [--topic 커리어·자기계발] [--post]
--image가 없으면 본문 파일과 같은 이름의 .jpg/.png를 찾는다. 사진이 없으면 사진 없이 올리지 않고 멈춘다.
"""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 9227


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--image", default="")
    ap.add_argument("--topic", default="커리어·자기계발")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    body = re.sub(r"\n{2,}", "\n\n", Path(a.file).read_text(encoding="utf-8").strip())
    img = a.image or next((str(q) for q in (Path(a.file).with_suffix(".jpg"), Path(a.file).with_suffix(".png")) if q.exists()), "")
    res = {"chars_local": len(body), "posted": False, "image": Path(img).name if img else ""}
    if len(body) > 1500:
        print(json.dumps({**res, "status": "STOP", "why": "1,500자 초과: 줄인 안을 사장님 컨펌 후 사용"}, ensure_ascii=False)); return 1
    if not img:
        print(json.dumps({**res, "status": "STOP", "why": "표지 이미지 없음: 사진 없이 게시하지 않음"}, ensure_ascii=False)); return 1
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        pg = b.contexts[0].new_page()
        try:
            pg.goto("https://connect.rememberapp.co.kr/feed", wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(5000)
            btn = pg.get_by_role("button", name="게시물 작성")
            res["write_buttons"] = btn.count()
            if not res["write_buttons"]:
                res.update(status="STOP", why="게시물 작성 버튼 없음(로그인 확인)"); print(json.dumps(res, ensure_ascii=False)); return 1
            btn.first.click(); pg.wait_for_timeout(2000)
            ta = pg.locator("textarea[placeholder*='어떤 이야기']").first
            ta.wait_for(timeout=15000)
            ta.fill(body); pg.wait_for_timeout(800)
            m = re.search(r"([\d,]+)\s*/\s*1,?500", pg.locator("body").inner_text())
            res["counter"] = m.group(0) if m else None
            # 주제 선택(필수)
            pg.get_by_role("button", name=re.compile(r"주제 선택")).first.click(); pg.wait_for_timeout(1200)
            pg.get_by_text(a.topic, exact=True).last.click(); pg.wait_for_timeout(500)
            pg.get_by_role("button", name="등록").last.click(); pg.wait_for_timeout(1200)
            res["topic"] = a.topic if pg.get_by_text(a.topic, exact=True).count() else "미확인"
            # 사진
            pg.get_by_role("button", name=re.compile(r"사진 추가")).first.click(); pg.wait_for_timeout(1500)
            fin = pg.locator("input[type=file]")
            res["file_inputs"] = fin.count()
            if not res["file_inputs"]:
                res.update(status="STOP", why="사진 입력칸 없음: 사진 없이 게시하지 않음"); print(json.dumps(res, ensure_ascii=False)); return 1
            fin.first.set_input_files(img); pg.wait_for_timeout(4000)
            pg.get_by_role("button", name="첨부").last.click(); pg.wait_for_timeout(2500)
            res["img_preview"] = pg.locator("img[src^='blob:'], img[src*='rememberapp']").count()
            res["editor_head"] = ta.input_value()[:40] if ta.count() else ""
            if a.post:
                pg.get_by_role("button", name="등록").last.click(); pg.wait_for_timeout(2500)
                ok = pg.get_by_role("button", name=re.compile(r"등록하기"))
                if ok.count():
                    ok.last.click(); pg.wait_for_timeout(3000)
                pg.goto("https://connect.rememberapp.co.kr/feed", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
                top = pg.locator("body").inner_text()[:6000]
                res["posted"] = body.splitlines()[0][:20] in top
        finally:
            pg.close()
    res["status"] = "ok"
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
