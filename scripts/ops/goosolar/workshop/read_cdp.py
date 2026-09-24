from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [pg for c in b.contexts for pg in c.pages if "flow.google.com" in pg.url]
    pg = pages[0]
    print("url:", pg.url, "| title:", pg.title())
    snap = pg.locator("body").aria_snapshot()
    lines = [l for l in snap.splitlines() if l.strip()]
    print("aria lines:", len(lines), "chars:", len(snap))
    keep = [l for l in lines if any(k in l for k in ("button", "link", "textbox", "heading", "combobox"))]
    print("\n".join(keep[:40]))
