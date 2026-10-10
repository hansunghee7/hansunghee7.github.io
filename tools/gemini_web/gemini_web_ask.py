#!/usr/bin/env python3
"""제미나이 웹앱(gemini.google.com) 텍스트 질문 1건 실행기(구PC 작업실에서 돈다). 2026-10-11 G1.

왜: 무료 API 키는 검색 연동 요청만 429라, Vertex 크레딧이 끝나면 검색이 막힌다. 이미 로그인된 구PC 크롬(디버그 포트)의
    제미나이 웹앱으로 질문하고 답과 출처 링크를 읽어 온다. 이미지 생성에서 이미 성공한 동선(logos_gem_batch.py)을 텍스트 질문으로 줄였다.
호출: 이 파일은 질문 1건만 한다. 하루 상한·호출 간격·계정 중지 상태는 PC 쪽 래퍼(scripts/ops/gemini_web.py)가 정본으로 지킨다.
입력: --port 디버그 포트, --question-file UTF-8 파일(질문), [--expect 이메일 일부(계정 확인)], [--timeout 초]
출력: 표준출력에 JSON 한 줄 {"status": ok|blocked|login|mismatch|timeout|error, "text", "sources":[{"title","uri"}], "secs", "note"}
      consent = 약관·동의 카드가 입력창을 가렸다(사람이 동의해야 함, 에이전트는 누르지 않는다). blocked = 한도·정책·차단 문구가 보였다(그 계정은 그날 중지해야 한다). 계정을 바꿔 다시 두드리지 않는다.
사람 빈도: 새 채팅 1개, 글자 사이 간격을 두고 입력, 클릭으로 전송(엔터는 안 먹음, 10/5 실측). 키·쿠키는 읽지도 출력하지도 않는다.
구PC 설치 위치: ~/workshop/gemini_web/gemini_web_ask.py, 파이썬 ~/workshop/venv/bin/python (Playwright 1.63).
"""
import argparse
import json
import random
import re
import sys
import time

URL = "https://gemini.google.com/app"
BLOCK_WORDS = ("can't generate", "cannot generate", "생성할 수 없", "한도", "정책", "다시 시도", "Sorry", "죄송",
               "too many requests", "unusual traffic", "비정상적인 트래픽", "잠시 후 다시")
MAX_Q = 1500  # 질문 길이 상한(글자). 래퍼가 먼저 막지만 여기서도 지킨다

# 마지막 모델 응답의 본문과 외부 링크를 DOM에서 읽는다. 요소 이름은 Gemini 웹앱 기준(model-response / message-content).
JS_LAST = """() => {
  const norm = (s) => (s || '').replace(/\\s+\\n/g, '\\n').trim();
  const nodes = document.querySelectorAll('message-content, model-response .markdown, .model-response-text');
  const last = nodes.length ? nodes[nodes.length - 1] : null;
  const root = last ? (last.closest('model-response') || last) : null;
  const text = last ? norm(last.innerText) : '';
  const seen = new Set(); const src = [];
  if (root) for (const a of root.querySelectorAll('a[href]')) {
    const h = a.href || '';
    if (!/^https?:/.test(h)) continue;
    let host = ''; try { host = new URL(h).hostname; } catch (e) {}
    if (/(^|\\.)google\\.[a-z.]+$/.test(host) && !/grounding-api-redirect/.test(h)) continue;
    if (seen.has(h)) continue; seen.add(h);
    src.push({title: norm(a.innerText || a.getAttribute('aria-label') || host).slice(0, 120), uri: h});
  }
  return {text, sources: src, n: nodes.length};
}"""


def out(status, text="", sources=None, secs=0, note=""):
    print(json.dumps({"status": status, "text": text, "sources": sources or [], "secs": secs, "note": note}, ensure_ascii=False), flush=True)
    return 0 if status == "ok" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--question-file", required=True)
    ap.add_argument("--expect", default="")
    ap.add_argument("--timeout", type=int, default=150)
    a = ap.parse_args()
    q = open(a.question_file, encoding="utf-8").read().strip()
    if not q or len(q) > MAX_Q:
        return out("error", note=f"질문 길이 1~{MAX_Q}자만 허용")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{a.port}", timeout=10000)
        pg = b.contexts[0].new_page()
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=45000)
            if "accounts.google.com" in pg.url:
                return out("login", note="로그인 화면. 로그인은 사람 몫이라 중지")
            pg.wait_for_timeout(4000)  # 온보딩 카드가 늦게 뜨는 계정이 있다(9224 10/11 실측)
            box = pg.get_by_role("textbox", name=re.compile("Gemini 프롬프트 입력|Enter a prompt"))
            try:
                box.wait_for(timeout=30000)
            except Exception:  # noqa: BLE001
                return out("login" if "accounts.google.com" in pg.url else "error", note="입력창을 못 찾음")
            if pg.get_by_role("button", name=re.compile("동의 화면|시작하기|Get started")).count():
                return out("consent", note="약관·동의 화면이 떠 있음. 동의 클릭은 사람 몫이라 중지")
            pg.wait_for_timeout(2500)  # 첫 클릭은 페이지 준비 전엔 무시된다(10/5 실측)
            if a.expect and not pg.locator(f"[aria-label*='{a.expect}']").count():
                return out("mismatch", note="계정 불일치: 기대 이메일이 화면에 없음")
            box.click()
            pg.wait_for_timeout(300)
            pg.keyboard.type(q, delay=random.randint(18, 45))  # 사람이 치듯
            pg.wait_for_timeout(600)
            t0 = time.time()
            pg.get_by_role("button", name=re.compile("메시지 보내기|Send message")).first.click(timeout=8000)
            last, stable_since = "", None
            while time.time() - t0 < a.timeout:
                pg.wait_for_timeout(2000)
                body = pg.locator("body").inner_text()[-1500:]
                r = pg.evaluate(JS_LAST)
                busy = pg.get_by_role("button", name=re.compile("응답 중지|Stop response")).count() > 0
                if not r["text"] and any(w in body for w in BLOCK_WORDS) and time.time() - t0 > 8:
                    w = [w for w in BLOCK_WORDS if w in body][0]
                    return out("blocked", secs=round(time.time() - t0), note=f"차단 문구: {w}")
                if r["text"] and r["text"] == last and not busy:
                    stable_since = stable_since or time.time()
                    if time.time() - stable_since >= 4:
                        txt = r["text"]
                        if any(w in txt[:200] for w in BLOCK_WORDS) and len(txt) < 200:
                            w = [w for w in BLOCK_WORDS if w in txt][0]
                            return out("blocked", txt, secs=round(time.time() - t0), note=f"차단 문구: {w}")
                        return out("ok", txt, r["sources"], round(time.time() - t0))
                else:
                    stable_since = None
                last = r["text"]
            return out("timeout", last, secs=round(time.time() - t0), note="응답 대기 초과")
        except Exception as e:  # noqa: BLE001
            return out("error", note=str(e)[:160])
        finally:
            try:
                pg.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
