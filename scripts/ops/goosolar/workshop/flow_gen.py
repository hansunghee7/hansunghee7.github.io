import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright
prompt = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
out = Path(sys.argv[2]); t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = [pg for c in b.contexts for pg in c.pages if "flow.google.com/project" in pg.url][0]
    trig = pg.get_by_role("button", name="설정 트리거").inner_text().replace("\n", " ")
    log(f"settings: {trig}")
    if not all(k in trig for k in ("동영상", "4초", "9_16", "x1")):
        sys.exit("STOP: settings mismatch")
    before = set(v.get_attribute("src") for v in pg.locator("video").all())
    box = pg.locator("[contenteditable=true]").first
    box.click(); box.fill("") if False else None
    pg.keyboard.insert_text(prompt)
    log(f"prompt typed ({len(prompt)} chars)")
    go = pg.get_by_role("button", name="생성 시작")
    pg.wait_for_timeout(800)
    if go.is_disabled(): sys.exit("STOP: 생성 시작 disabled after typing")
    go.click(); log("generation started")
    src = None
    while time.time() - t0 < 600:
        pg.wait_for_timeout(10000)
        now = [v.get_attribute("src") for v in pg.locator("video").all()]
        new = [s for s in now if s and s not in before]
        if new:
            src = new[0]; break
        body = pg.locator("body").inner_text()
        pct = [l for l in body.splitlines() if "%" in l][:1]
        log(f"waiting... videos={len(now)} {pct}")
    if not src: sys.exit("STOP: timeout waiting for video")
    log(f"video ready: {src[:60]}...")
    r = pg.context.request.get(src)
    out.write_bytes(r.body())
    log(f"saved {out} ({out.stat().st_size} bytes, http {r.status})")
