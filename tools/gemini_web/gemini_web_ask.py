#!/usr/bin/env python3
"""제미나이 웹앱(gemini.google.com) 텍스트 질문 1건 실행기(구PC 작업실에서 돈다). 2026-10-11 G1, N184 교차 검토 반영.

왜: 무료 API 키는 검색 연동 요청만 429라, Vertex 크레딧이 끝나면 검색이 막힌다. 이미 로그인된 구PC 크롬(디버그 포트)의
    제미나이 웹앱으로 질문하고 답과 출처 링크를 읽어 온다. 이미지 생성에서 이미 성공한 동선(logos_gem_batch.py)을 텍스트 질문으로 줄였다.
호출: 이 파일은 질문 1건만 한다. 하루 상한·호출 간격·계정 중지 상태는 PC 쪽 래퍼(scripts/ops/gemini_web.py)가 정본으로 지킨다.
입력: --port 디버그 포트, --question-file UTF-8 파일(질문, '-'면 표준입력), [--expect 이메일 일부], [--timeout 전체 예산 초]
출력: 표준출력에 JSON 한 줄 {"status": ok|blocked|login|consent|mismatch|timeout|error, "text", "sources":[{"title","uri"}], "secs", "note"}
      consent = 약관·동의 카드가 입력창을 가렸다(사람이 동의해야 함, 에이전트는 누르지 않는다). blocked = 한도·정책·차단 문구.
      이 둘과 login·mismatch 는 그 계정을 그날 중지해야 한다. 계정을 바꿔 다시 두드리지 않는다.
이전 답 방지: 전송 전에 마지막 응답의 해시와 응답 노드 수를 적어 두고, 노드 수가 늘었거나 해시가 달라지고 4초 안정일 때만 ok.
구PC 설치 위치: ~/workshop/gemini_web/gemini_web_ask.py, 파이썬 ~/workshop/venv/bin/python (Playwright 1.63).
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time

URL = "https://gemini.google.com/app"
# 화면 전체 하단에서 응답이 아직 없을 때 보는 차단 문구
BLOCK_WORDS = ("can't generate", "cannot generate", "생성할 수 없", "한도", "정책", "다시 시도", "Sorry", "죄송",
               "too many requests", "unusual traffic", "비정상적인 트래픽", "잠시 후 다시")
# 응답 본문 앞부분에서 보는 문구(일반 답에 흔한 낱말은 뺀 구체적 문구만, 길이와 무관하게 앞 600자 검사)
ANSWER_BLOCK_PHRASES = ("can't help with that", "can't generate", "cannot generate", "생성할 수 없", "한도에", "한도를", "too many requests",
                        "unusual traffic", "비정상적인 트래픽", "로그인이 필요", "로그인하세요", "Sign in to", "동의 화면", "약관에 동의",
                        "정책에 따라", "정책상", "죄송합니다. 도와", "잠시 후 다시 시도")
HEAD_CHARS = 600
MAX_Q = 1500

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


def h(text):
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def block_phrase(text):
    """응답 앞 600자에서 차단·정책·로그인·동의 문구를 찾는다(길이와 무관). 없으면 ''."""
    head = (text or "")[:HEAD_CHARS]
    low = head.lower()
    for w in ANSWER_BLOCK_PHRASES:
        if w.lower() in low:
            return w
    return ""


def wait_answer(read, busy, body, sleep, clock, h0, n0, timeout, stable_s=4):
    """전송 뒤 새 답을 기다린다. read()->{"text","sources","n"}, busy()->bool, body()->화면 하단 글, sleep(초), clock()->초.
    반환 (status, text, sources, note). ok 는 '노드가 늘었거나 해시가 달라졌고' 같은 글이 stable_s 초 유지될 때만."""
    t0 = clock()
    last, since = None, None
    while clock() - t0 < timeout:
        sleep(2)
        r = read()
        txt = r["text"]
        fresh = bool(txt) and (r["n"] > n0 or h(txt) != h0)
        if not fresh:
            since = None
            b = body()
            if clock() - t0 > 8 and any(w in b for w in BLOCK_WORDS):
                w = [w for w in BLOCK_WORDS if w in b][0]
                return "blocked", "", [], f"차단 문구: {w}"
            continue
        if txt == last and not busy():
            since = since or clock()
            if clock() - since >= stable_s:
                w = block_phrase(txt)
                if w:
                    return "blocked", txt, [], f"차단 문구: {w}"
                return "ok", txt, r["sources"], ""
        else:
            since = None
        last = txt
    if last is None:
        return "error", "", [], "새 응답이 생기지 않음(이전 답은 반환하지 않음)"
    return "timeout", last, [], "응답 대기 초과"


def out(status, text="", sources=None, secs=0, note=""):
    print(json.dumps({"status": status, "text": text, "sources": sources or [], "secs": secs, "note": note}, ensure_ascii=False), flush=True)
    return 0 if status == "ok" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--question-file", required=True)
    ap.add_argument("--expect", default="")
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()
    q = (sys.stdin.read() if a.question_file == "-" else open(a.question_file, encoding="utf-8").read()).strip()
    if not q or len(q) > MAX_Q:
        return out("error", note=f"질문 길이 1~{MAX_Q}자만 허용")
    start = time.time()
    left = lambda: max(3, a.timeout - (time.time() - start))  # noqa: E731  전체 예산에서 남은 초
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{a.port}", timeout=8000)
        pg = b.contexts[0].new_page()
        consent_re = re.compile("동의 화면|시작하기|Get started")
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=int(min(20, left()) * 1000))
            pg.wait_for_timeout(3500)  # 온보딩 카드가 늦게 뜨는 계정이 있다
            # 동의 화면 검사를 입력창 찾기보다 먼저(입력창이 DOM에는 있어도 카드가 가리면 클릭이 실패한다, 9224 10/11)
            if pg.get_by_role("button", name=consent_re).count():
                return out("consent", note="약관·동의 화면이 떠 있음. 동의 클릭은 사람 몫이라 중지")
            if "accounts.google.com" in pg.url:
                return out("login", note="로그인 화면. 로그인은 사람 몫이라 중지")
            box = pg.get_by_role("textbox", name=re.compile("Gemini 프롬프트 입력|Enter a prompt"))
            try:
                box.wait_for(timeout=int(min(15, left()) * 1000))
            except Exception:  # noqa: BLE001
                if pg.get_by_role("button", name=consent_re).count():
                    return out("consent", note="입력창 없음 + 동의 화면")
                return out("login" if "accounts.google.com" in pg.url else "error", note="입력창을 못 찾음")
            if a.expect and not pg.locator(f"[aria-label*='{a.expect}']").count():
                return out("mismatch", note="계정 불일치: 기대 이메일이 화면에 없음")
            pre = pg.evaluate(JS_LAST)
            h0, n0 = h(pre["text"]), pre["n"]
            box.click(timeout=int(min(8, left()) * 1000))
            pg.wait_for_timeout(300)
            pg.keyboard.type(q, delay=random.randint(18, 45))  # 사람이 치듯
            pg.wait_for_timeout(600)
            t0 = time.time()
            pg.get_by_role("button", name=re.compile("메시지 보내기|Send message")).first.click(timeout=8000)  # 실패하면 예외 -> error
            st, txt, src, note = wait_answer(
                lambda: pg.evaluate(JS_LAST),
                lambda: pg.get_by_role("button", name=re.compile("응답 중지|Stop response")).count() > 0,
                lambda: pg.locator("body").inner_text()[-1500:],
                lambda s: pg.wait_for_timeout(int(s * 1000)), time.time, h0, n0, max(5, left()))
            return out(st, txt, src, round(time.time() - t0), note)
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
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
