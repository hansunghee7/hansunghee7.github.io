#!/usr/bin/env python3
"""링크드인 메시지 목록 읽기 전용 점검 (구PC 작업실 9227, 2026-10-21 마야).

왜: 사장님 링크드인에 협업·자문 제안 메시지가 오는데 확인과 답장 초안 통로가 없었다. 이 스크립트는 메시지 목록의
발신자·마지막 문장 미리보기·시각·안 읽음 표시만 읽어 JSON으로 남긴다. 슈퍼인박스 때 마야가 새 메시지를 정리하고
답장 초안을 쓰며, 보내는 것은 사장님이 한다(외부 발신은 에이전트 금지).

안전장치: 대화를 열지 않는다(열면 상대에게 '읽음'이 표시된다). 입력·클릭·전송 동작이 없다. 읽기만 한다.
출력: ~/workshop/out/maya/linkedin_msgs_latest.json, linkedin_msgs_<날짜시각>.json
사용: python read_linkedin_messages.py [--limit 30]
"""
import argparse, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 9227
KST = timezone(timedelta(hours=9))
OUT = Path.home() / "workshop" / "out" / "maya"

JS = """(limit) => {
  const rows = [...document.querySelectorAll('li.msg-conversation-listitem, li[class*=msg-conversation-listitem]')].slice(0, limit);
  return rows.map(li => {
    const q = (s) => { const e = li.querySelector(s); return e ? e.innerText.replace(/\\s+/g, ' ').trim() : ''; };
    const html = li.innerHTML;
    return {
      name: q('[class*=participant-names]') || q('h3'),
      snippet: q('[class*=message-snippet]') || q('p'),
      time: q('time') || q('[class*=time-stamp]'),
      unread: /unread|notification-badge--show|msg-conversation-card--unread/.test(html) && !/notification-badge--hidden/.test(html.slice(0, 400)),
      raw: li.innerText.replace(/\\s+/g, ' ').trim().slice(0, 240)
    };
  });
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    now = datetime.now(KST)
    res = {"read_at": now.isoformat(timespec="seconds"), "status": "ok", "count": 0, "items": []}
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        pg = b.contexts[0].new_page()
        try:
            pg.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(6000)
            if "login" in pg.url or "authwall" in pg.url or "checkpoint" in pg.url:
                res.update(status="STOP", why="링크드인 로그인 확인 필요", url=pg.url[:80])
            else:
                res["items"] = pg.evaluate(JS, a.limit)
                res["count"] = len(res["items"])
                if not res["count"]:
                    res.update(status="EMPTY", why="대화 목록을 못 찾음(화면 구조 변경 또는 로딩 지연)")
        finally:
            pg.close()
    OUT.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    (OUT / "linkedin_msgs_latest.json").write_text(txt, encoding="utf-8")
    (OUT / f"linkedin_msgs_{now:%Y%m%d_%H%M}.json").write_text(txt, encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "items"}, ensure_ascii=False),
          "| 안 읽음", sum(1 for i in res["items"] if i.get("unread")))
    for i in res["items"][:8]:
        print(("● " if i.get("unread") else "  ") + (i.get("name") or "?")[:20], "|", (i.get("snippet") or i.get("raw") or "")[:70], "|", i.get("time"))
    return 0 if res["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
