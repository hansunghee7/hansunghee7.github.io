# -*- coding: utf-8 -*-
"""네이버 블로그 예약발행: 제목·본문·표지를 채우고 발행 패널에서 예약 시각을 넣어 예약한다(헤드리스 가능).
사용: python scripts/sns/reserve_naver.py --title 제목 --body-file 본문.txt --cover 표지.jpg --when "2026-10-05 09:00" [--go]
검증: 글쓰기 화면 상단 '예약 발행 N건' 또는 예약 목록 팝업. 2026-09-30 마야 4건 실측(DONE=VERIFIED).
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
    b=p.chromium.launch(headless=True)
    ctx=b.new_context(storage_state=r"C:\work\_ops\sns_playwright_state\naver.json",viewport={'width':1280,'height':900})
    page=ctx.new_page(); page.goto("https://blog.naver.com/simplifiers?Redirect=Write&"); page.wait_for_timeout(3000)
    fr=next(f for f in page.frames if "PostWriteForm" in f.url)
    try: fr.locator("button.se-popup-button-cancel").click(timeout=6000)
    except Exception: pass
    page.wait_for_timeout(500)
    try: fr.locator('.se-help-panel-close-button').click(timeout=4000)
    except Exception: page.mouse.click(1222,42)
    page.wait_for_timeout(500)
    tb=fr.locator(".se-documentTitle").bounding_box()
    page.mouse.move(tb["x"]+tb["width"]/2,tb["y"]); page.wait_for_timeout(500)
    with page.expect_file_chooser() as fc: fr.get_by_title("내 컴퓨터에서 배경사진 첨부").click(timeout=5000)
    fc.value.set_files(cover); page.wait_for_timeout(2500)
    fr.locator(".se-documentTitle").click(timeout=10000); page.keyboard.type(title); page.keyboard.press("Enter")
    chunks=body.strip().split(chr(10)*2)
    for ci,ch in enumerate(chunks):
        page.keyboard.type(ch)
        if ci<len(chunks)-1:
            page.keyboard.press("Enter"); page.wait_for_timeout(150); page.keyboard.press("Enter"); page.wait_for_timeout(150)
    page.wait_for_timeout(1000)
    try: fr.locator(".se-help-panel-close-button").click(timeout=3000)
    except Exception: pass
    paras=fr.evaluate("()=>[...document.querySelectorAll('.se-component.se-text .se-text-paragraph')].map(p=>p.textContent.replace(/\u200b/g,''))")
    exp=body.split(chr(10))
    (OUT/(n+'_paras.txt')).write_text(chr(10).join('%d|%s'%(len(p),p[:40]) for p in paras),encoding='utf-8')
    print('PARAS',len(paras),'nonempty',sum(1 for p in paras if p.strip()),'expected_nonempty',sum(1 for x in exp if x.strip()),'star',any('**' in p for p in paras))
    fr.locator("button[class*=publish_btn]").click(); page.wait_for_timeout(1500)
    fr.get_by_text("예약",exact=True).first.click(); page.wait_for_timeout(800)
    page.screenshot(path=str(OUT/f'{n}_panel.png'))
    from datetime import datetime
    when=datetime.strptime(A.when,"%Y-%m-%d %H:%M")
    fr.locator("input[class*=input_date]").click(); page.wait_for_timeout(600)
    cur=fr.locator("input[class*=input_date]").input_value()
    def ym(s):
        a=[int(x) for x in s.replace(' ','').split('.') if x]; return a[0]*12+a[1]
    for _ in range(3):
        head=fr.locator('.ui-datepicker-title').inner_text()
        nums=[int(x) for x in re.findall(r'[0-9]+',head)]
        if nums[0]*12+nums[1]==when.year*12+when.month: break
        fr.locator("button.ui-datepicker-next").click(); page.wait_for_timeout(400)
    fr.locator("td:not(.ui-state-disabled) button.ui-state-default",has_text=re.compile("^%d$"%when.day)).first.click(); page.wait_for_timeout(500)
    fr.locator("select[class*=hour_option]").select_option("%02d"%when.hour)
    fr.locator("select[class*=minute_option]").select_option("%02d"%when.minute)
    page.wait_for_timeout(500)
    got=(fr.locator("input[class*=input_date]").input_value(),fr.locator("select[class*=hour_option]").input_value(),fr.locator("select[class*=minute_option]").input_value())
    print("SET",got)
    page.screenshot(path=str(OUT/(n+'_set.png')))
    want=(when.strftime("%Y. %m. %d"),"%02d"%when.hour,"%02d"%when.minute)
    assert got==want,(got,want)
    if A.go:
        fr.locator("button[class*=confirm_btn]").click(); page.wait_for_timeout(4000)
        page.screenshot(path=str(OUT/(n+'_done.png'))); print("CONFIRMED")
    b.close()
