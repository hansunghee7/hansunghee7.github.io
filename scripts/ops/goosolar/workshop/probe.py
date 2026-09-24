import sys, time
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    t = time.time()
    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)
    print("load_s", round(time.time() - t, 1), "| title:", pg.title(), "| url:", pg.url[:80])
    snap = pg.locator("body").aria_snapshot()
    lines = [l for l in snap.splitlines() if l.strip()]
    print("aria lines:", len(lines), "| chars:", len(snap))
    print("\n".join(lines[:25]))
    b.close()
