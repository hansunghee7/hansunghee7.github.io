# -*- coding: utf-8 -*-
"""브런치 예약발행: 제목·본문·커버를 채우고 매거진 Be the PO 선택, 예약 시각 지정, 완료 후 '네'(일반 글)까지 한다.
반드시 headless=False. 로그인이 풀리면 카카오 계정 선택 화면에서 계정명을 눌러 복구한다(비밀번호 입력 없음, 사장님 안내 2026-09-30).
사용: python scripts/sns/reserve_brunch.py --title 제목 --body-file 본문.txt --cover 표지.jpg --when "2026-10-05 09:00" [--go]
검증: brunch.co.kr/ready 예약 글 목록, 글 페이지 cover_image 존재. 2026-09-30 마야 4건 실측.
"""
import argparse
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--title", required=True)
ap.add_argument("--body-file", required=True)
ap.add_argument("--cover", required=True)
ap.add_argument("--when", required=True, help='예약 시각 "2026-10-05 09:00" (1시간 단위)')
ap.add_argument("--go", action="store_true", help="없으면 마지막 확정 클릭 직전에 멈춘다(dry-run)")
A = ap.parse_args()
title = A.title
body = Path(A.body_file).read_text(encoding="utf-8")
cover = A.cover
OUT = Path(r"C:\work\_ops\sns_playwright_state")
n = "run"
with sync_playwright() as p:
    b=p.chromium.launch(headless=False)
    ctx=b.new_context(storage_state=r"C:\work\_ops\sns_playwright_state\brunch.json",viewport={'width':1280,'height':900})
    page=ctx.new_page(); page.goto("https://brunch.co.kr/write"); page.wait_for_timeout(2500)
    try: page.get_by_text("아니요",exact=True).click(timeout=3000)
    except Exception: pass
    page.locator("h1.cover_title").click(timeout=10000); page.keyboard.type(title)
    page.locator("div.wrap_body").click(timeout=5000)
    chunks=body.strip().split(chr(10)*2)
    for ci,ch in enumerate(chunks):
        page.keyboard.type(ch)
        if ci<len(chunks)-1:
            page.keyboard.press("Enter"); page.wait_for_timeout(120); page.keyboard.press("Enter"); page.wait_for_timeout(120)
    page.evaluate("window.scrollTo(0,0)"); page.wait_for_timeout(800)
    page.screenshot(path=str(OUT/(n+"_bfill.png")))
    print("BTNS",page.evaluate("()=>[...document.querySelectorAll('button,input')].filter(x=>(x.title||x.getAttribute('aria-label')||x.textContent||'').includes(String.fromCharCode(52964,48260))).map(x=>x.tagName+x.className+x.title+JSON.stringify(x.getBoundingClientRect()))"))
    btn=page.get_by_role("button",name="커버 이미지"); box=btn.bounding_box()
    for attempt in range(4):
        try:
            page.evaluate("window.scrollTo(0,0)"); page.wait_for_timeout(1200)
            box=page.get_by_role("button",name="커버 이미지").bounding_box()
            with page.expect_file_chooser(timeout=6000) as fc: page.mouse.click(box["x"]+box["width"]/2,box["y"]+box["height"]/2)
            fc.value.set_files(cover); page.wait_for_timeout(3000); break
        except Exception as e:
            print("cover retry",attempt)
            if attempt==3: raise
    page.get_by_text("발행",exact=True).first.click(); page.wait_for_timeout(2000)
    page.get_by_text("매거진 7").first.click(); page.wait_for_timeout(800)
    page.locator("button.chk_editor",has_text="발행 시간 예약").click(); page.wait_for_timeout(800)
    page.locator("button.link_choose",has_text="Be the PO").click(); page.wait_for_timeout(500)
    page.locator("button.reserve_input").first.click(); page.wait_for_timeout(800)
    from datetime import datetime
    when=datetime.strptime(A.when,"%Y-%m-%d %H:%M")
    cur=datetime.now()
    for _ in range((when.year-cur.year)*12+when.month-cur.month):
        page.locator("button.svelte-1j8ncx9:not(.reserve_input)").nth(1).click(); page.wait_for_timeout(400)
    page.locator("td.svelte-1j8ncx9 button",has_text=re.compile("^%d$"%when.day)).first.click(); page.wait_for_timeout(600)
    page.locator("button.reserve_input").nth(1).click(); page.wait_for_timeout(600)
    page.get_by_text("%02d시"%when.hour,exact=True).last.click(); page.wait_for_timeout(600)
    txt=page.locator("div.wrap_input").first.inner_text().replace(chr(10)," ")
    print("SET",txt)
    page.screenshot(path=str(OUT/(n+'_bset.png')))
    assert ("%04d. %02d. %02d"%(when.year,when.month,when.day)) in txt and ("%02d시"%when.hour) in txt, txt
    if A.go:
        page.locator("button.save").click(); page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT/(n+'_bdone1.png')))
        print("DLG",page.evaluate("()=>[...document.querySelectorAll('button,a')].filter(x=>x.offsetParent&&x.getBoundingClientRect().y>250&&x.getBoundingClientRect().y<600&&x.getBoundingClientRect().x<940).map(x=>x.tagName+'|'+x.className+'|'+x.textContent.trim()+'|'+Math.round(x.getBoundingClientRect().x)+','+Math.round(x.getBoundingClientRect().y))"))
        page.locator("button,a",has_text=re.compile(r"^\s*네\s*$")).last.click(timeout=5000); page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT/(n+'_bdone15.png')))
        try: page.get_by_text("확인",exact=True).first.click(timeout=4000)
        except Exception as e: print("no second popup")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT/(n+'_bdone2.png'))); print("CONFIRMED", page.url)
        pass
    b.close()
