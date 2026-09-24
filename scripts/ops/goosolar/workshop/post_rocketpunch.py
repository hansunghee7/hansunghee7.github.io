#!/usr/bin/env python3
"""로켓펀치 글 게시 레시피 (구PC 작업실 9227, 2026-09-24 탐). 마야 실측 절차(SNS_자동게시_설계안.md 부록 A)를 옮김.

순서: 피드의 "게시하기" → tiptap 편집기에 붙여넣기(paste 이벤트, 문단 사이 빈 줄) → 글자 수 카운터 확인(2,000자 제한)
→ (--post일 때만) "글쓰기" → "게시물이 등록되었습니다." 확인 → 내 글 목록 맨 위 "방금" 확인.
기본은 모의 실행(--post 없음): 끝까지 채우고 글자 수만 확인한 뒤 창을 닫는다. 공개 게시는 --post를 줄 때만.

사용: python post_rocketpunch.py --file post.txt [--post]
post.txt: 첫 줄 제목, 빈 줄, 본문, 끝 줄 "from <원문 URL>"(사장님 기존 게시물과 같은 모양)
"""
import argparse, json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 9227
PASTE_JS = """(t) => {
  const ed = document.querySelector('div.tiptap.ProseMirror[contenteditable=true]');
  if (!ed) return 'no-editor';
  ed.focus();
  const dt = new DataTransfer(); dt.setData('text/plain', t);
  ed.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
  return 'ok';
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True); ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8").strip()
    body = re.sub(r"\n{2,}", "\n\n", text)  # 문단 사이는 빈 줄 하나(마야 실측: \n 하나면 문단이 붙어 보임)
    res = {"chars_local": len(body), "posted": False}
    if len(body) > 2000:
        print(json.dumps({**res, "status": "STOP", "why": "2,000자 초과: 줄인 안을 사장님 컨펌 후 사용"}, ensure_ascii=False)); return 1
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        pg = b.contexts[0].new_page()
        pg.goto("https://www.rocketpunch.com/", wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(5000)
        # 구PC 크롬에서는 로켓펀치가 영어 화면(/en)으로 고정된다(2026-09-24). 한국어·영어 이름을 둘 다 본다.
        btn = pg.get_by_role("button", name=re.compile(r"^(게시하기|Post)$"))
        res["write_buttons"] = btn.count()
        if not res["write_buttons"]:
            res.update(status="STOP", why="게시하기 버튼 없음(로그인 확인)"); print(json.dumps(res, ensure_ascii=False)); return 1
        btn.last.click(); pg.wait_for_timeout(2500)
        ed = pg.locator("div.tiptap.ProseMirror[contenteditable=true]")
        ed.first.wait_for(timeout=15000)
        res["paste"] = pg.evaluate(PASTE_JS, body); pg.wait_for_timeout(1500)
        m = re.search(r"(\d[\d,]*)\s*/\s*2,?000", pg.locator("body").inner_text())
        res["counter"] = m.group(0) if m else None
        res["editor_head"] = ed.first.inner_text()[:60]
        if a.post:
            dlg = pg.get_by_role("dialog")
            scope = dlg.last if dlg.count() else pg
            scope.get_by_role("button", name=re.compile(r"^(글쓰기|Post)$")).last.click()
            try:
                pg.get_by_text(re.compile(r"게시물이 등록되었습니다|has been posted|posted", re.I)).first.wait_for(timeout=20000); res["toast"] = True
            except Exception:
                res["toast"] = False
            pg.goto("https://www.rocketpunch.com/@simplfier/post", wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
            top = pg.locator("body").inner_text()[:3000]
            res["posted"] = bool(re.search(r"방금|just now|\d+\s*(s|sec|m|min)", top, re.I))
        else:
            pg.keyboard.press("Escape")
        pg.close()
    res["status"] = "ok"
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
