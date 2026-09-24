import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
prompt = Path(sys.argv[1]).read_text(encoding="utf-8").strip(); t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ed = [pg for c in b.contexts for pg in c.pages if "/videos/d/1VW9" in pg.url][0]
    st = ed.get_by_role("button", name="Omni", exact=False).first.inner_text()
    log(f"settings: {st}")
    if "세로" not in st: sys.exit("STOP: not portrait")
    box = ed.get_by_role("textbox", name="동영상을 설명하세요", exact=False)
    box.click(); ed.keyboard.insert_text(prompt); ed.wait_for_timeout(800)
    go = ed.get_by_role("button", name="생성", exact=True)
    if go.is_disabled(): sys.exit("STOP: 생성 disabled")
    go.click(); log("generation started")
    last = None
    while time.time() - t0 < 900:
        ed.wait_for_timeout(15000)
        lines = [l.strip() for l in ed.locator("body").aria_snapshot().splitlines() if l.strip()]
        sig = [l for l in lines if any(k in l for k in ("생성 중", "%", "삽입", "완료", "실패", "오류", "한도", "위반", "다시 시도", "video", "동영상 클립"))][:8]
        if sig != last: log(" || ".join(sig)); last = sig
        if any(("삽입" in l and "button" in l) or "한도" in l or "위반" in l or "실패" in l for l in sig): break
    log("stop polling")
