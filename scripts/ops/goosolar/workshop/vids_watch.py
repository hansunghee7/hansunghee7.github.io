import time
from playwright.sync_api import sync_playwright
t0 = time.time()
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ed = [pg for c in b.contexts for pg in c.pages if "/videos/d/1VW9" in pg.url][0]
    last = None
    while time.time() - t0 < 840:
        lines = [l.strip() for l in ed.locator("body").aria_snapshot().splitlines() if l.strip()]
        i = next((k for k,l in enumerate(lines) if "AI 동영상 클립" in l and "heading" in l), None)
        panel = lines[i:i+30] if i is not None else ["(panel not found)"]
        panel = [l for l in panel if "배너" not in l and "영어로" not in l]
        if panel != last:
            print(f"[{time.time()-t0:5.0f}s]", " || ".join(panel)[:900], flush=True); last = panel
        if any(k in " ".join(panel) for k in ("삽입", "실패", "위반", "한도", "다시 시도")) and "생성 중" not in " ".join(panel): break
        ed.wait_for_timeout(15000)
    print("video elems:", ed.locator("video").count())
