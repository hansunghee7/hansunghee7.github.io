from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = [pg for c in b.contexts for pg in c.pages if "flow.google.com/project" in pg.url][0]
    for name in ("설정 트리거", "생성 시작"):
        loc = pg.get_by_role("button", name=name)
        print(name, "->", loc.count(), "|", (loc.first.inner_text() if loc.count() else "").replace("\n"," / ")[:80], "| disabled:", loc.first.is_disabled() if loc.count() else "-")
    print("videos on page:", pg.locator("video").count())
    for r in ("동영상","9:16","x1"):
        l = pg.get_by_role("radio", name=r)
        print("radio", r, l.count(), l.first.get_attribute("aria-checked") if l.count() else "-")
