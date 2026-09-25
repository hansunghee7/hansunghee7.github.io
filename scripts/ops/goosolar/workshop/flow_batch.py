#!/usr/bin/env python3
"""Flow 여러 씬 연속 생성기 (구PC 작업실, 2026-09-24 탐).

씬 목록(JSON)을 받아 씬마다: 설정 자동 선택 → 크레딧 확인 → 프롬프트 입력 → 생성 →
새 <video> src가 생기면 직접 받아 씬 이름으로 저장. 화면 캡처와 AI 호출이 없다.
멈춤 조건(사람·AI가 볼 차례): 설정이 안 맞음, 크레딧 상한 초과, 실패·정책·한도 문구, 시간 초과.
2026-09-25 핏 예외표(ep21 8건) 반영: 씬에서 무슨 예외가 나든 STOP을 남기고 다음 포트로 넘어간다('실패'는 같은 포트 1회 재시도),
대기 상한 3분, 멈춤 단어는 알림 영역(aria-live·alert·status)에서만, 새 계정 첫 화면(쿠키 '나중에', '시작하기' 창) 정리,
썸네일에 마우스를 올려도 영상이 안 붙는 화면은 크게 보기를 열어 주소를 읽는다, 페이지를 오래 열어 두면 주소가 만료되니 계정마다 새로고침.

사용: python flow_batch.py scenes.json out/ep13 [--model "Omni 1.1 Flash"] [--res 360p]
      [--ratio 9:16] [--mode 소재] [--max-credits 30] [--only 씬02,씬03]
scenes.json: [{"name": "씬02", "prompt": "...", "dur": 6}, ...]  (dur: 4/6/8/10)
결과: out/<편>/<name>.mp4, out/<편>/batch_log.jsonl
"""
import argparse, json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

STOP_WORDS = ("실패", "정책", "위반", "한도", "부족", "다시 시도", "문제가 발생")
IMG_SEL = 'img[src*="flow-content.google/image/"]'


def media_ids(pg):
    """완성된 결과는 목록에 썸네일(image/<id>)로 뜬다. 첫 실측처럼 바로 <video>로 뜰 때도 있다(2026-09-24)."""
    ids = set()
    for sel, attr in ((IMG_SEL, "src"), ("video", "src")):
        for e in pg.locator(sel).all():
            u = e.get_attribute(attr) or ""
            if "flow-content.google/" in u:
                ids.add(u.split("?")[0].rsplit("/", 1)[-1])
    return ids


def video_url_for(pg, mid):
    """썸네일에 마우스를 올리면 같은 id의 <video> src가 생긴다. 안 생기는 화면(2026-09-25 9229 새 프로젝트)은
    썸네일을 눌러 크게 보기에서 같은 id의 <video>를 읽고 목록으로 돌아온다."""
    for v in pg.locator("video").all():
        u = v.get_attribute("src") or ""
        if mid in u:
            return u
    img = pg.locator(f'img[src*="{mid}"]').first
    if img.count():
        img.hover(); pg.wait_for_timeout(2500)
        for v in pg.locator("video").all():
            u = v.get_attribute("src") or ""
            if mid in u:
                return u
        home = pg.url
        img.click(); pg.wait_for_timeout(3000)
        found = None
        for v in pg.locator("video").all():
            u = v.get_attribute("src") or ""
            if mid in u:
                found = u; break
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        if pg.url != home:
            pg.go_back(); pg.wait_for_timeout(2000)
        return found
    return None


def log(f, rec):
    rec["t"] = time.strftime("%H:%M:%S")
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()


ALERT_SEL = "[aria-live], [role=alert], [role=status]"


def alert_lines(pg):
    """알림 영역 글자만 모은다. 몸통 전체를 보면 프롬프트·카드 제목 속 '한도' 같은 낱말에 걸렸다(2026-09-24 핏)."""
    out = []
    for e in pg.locator(ALERT_SEL).all():
        try:
            out += [l.strip() for l in e.inner_text().splitlines() if l.strip()]
        except Exception:
            pass
    return out


def first_run_cleanup(pg):
    """새 계정 첫 실행: 쿠키 알림 '나중에', 환영 창의 '시작하기'를 닫는다(2026-09-24 핏 예외표 ④). 없으면 아무것도 안 한다."""
    for name in ("나중에",):
        b = pg.get_by_role("button", name=name, exact=True)
        if b.count() and b.first.is_visible():
            b.first.click(); pg.wait_for_timeout(800)
    dlg = pg.get_by_role("dialog")
    if dlg.count() and dlg.first.is_visible() and "시작하기" in dlg.first.inner_text():
        close = dlg.first.get_by_role("button", name="닫기")
        if close.count():
            close.first.click()
        else:
            pg.keyboard.press("Escape")
        pg.wait_for_timeout(800)


def agent_off(pg):
    """새 계정·새 프로젝트는 프롬프트 칸이 에이전트(대화) 모드로 열리고 그때는 `설정 트리거`가 없다(2026-09-24 무료 계정)."""
    # 에이전트 대화 창이 열린 채로 뜨면 에이전트 버튼이 가려진다(2026-09-24 핏, 9224~9226 전부) -> 창부터 닫는다
    if pg.get_by_role("button", name="새로운 세션 시작").count():
        pg.get_by_role("button", name="닫기").first.click(); pg.wait_for_timeout(1200)
    ag = pg.get_by_role("button", name="에이전트", exact=True)
    if ag.count() and ag.first.get_attribute("aria-pressed") == "true":
        ag.first.click(); pg.wait_for_timeout(1200)


def open_settings(pg):
    """설정 창이 보일 때까지 최대 3번 연다. 썸네일 미리보기(hover)가 떠 있으면 클릭이 먹히지 않아
    먼저 Esc와 빈 곳으로 마우스를 옮긴다(2026-09-24 씬03에서 창이 안 열린 사고)."""
    agent_off(pg)
    radio = pg.get_by_role("radio", name="동영상")
    for _ in range(3):
        if radio.count() and radio.first.is_visible():
            return True
        pg.keyboard.press("Escape"); pg.mouse.move(5, 5); pg.wait_for_timeout(400)
        pg.get_by_role("button", name="설정 트리거").click()
        try:
            radio.first.wait_for(state="visible", timeout=5000); return True
        except Exception:
            pass
    return False


def pick(pg, name):
    r = pg.get_by_role("radio", name=name, exact=False).first
    if r.get_attribute("aria-checked") != "true":
        r.click(); pg.wait_for_timeout(300)
    return r.get_attribute("aria-checked") == "true"


def apply_settings(pg, a, dur):
    """순서가 중요하다: 모델에 따라 해상도·길이 선택지가 달라진다(무료 계정 기본 Veo 3.1 Lite에는 360p·길이 칸이 없음, 2026-09-24).
    그래서 종류·방식·비율 → 모델 → 해상도·길이·개수 순서로 고른다."""
    if not open_settings(pg):
        return False, "settings panel did not open", None
    ok = all(pick(pg, n) for n in ("동영상", a.mode, a.ratio))
    mbtn = pg.get_by_role("button", name="모델 제품군 선택")
    model = mbtn.inner_text().strip()
    if a.model not in model:
        mbtn.click(); pg.wait_for_timeout(800)
        pg.get_by_role("menuitem", name=a.model, exact=True).click(); pg.wait_for_timeout(1000)
        open_settings(pg)
        model = pg.get_by_role("button", name="모델 제품군 선택").inner_text().strip()
    ok = ok and all(pick(pg, n) for n in (a.res, f"{dur}초", "x1"))
    body = pg.locator("body").inner_text()
    m = re.search(r"(\d+)\s*크레딧", body)
    credits = int(m.group(1)) if m else None
    pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
    return ok and a.model in model, model.splitlines()[0], credits


def download(pg, src):
    r = pg.context.request.get(src)
    return r.status, r.body()


def run_scene(pg, a, s, out, lf, port, spent):
    """씬 하나. 반환 status: ok / skip / retry('실패' 문구) / mismatch(설정이 안 맞음) / stop(그 밖의 모든 예외·한도·시간 초과)."""
    t0 = time.time(); name = s["name"]; dest = out / f"{name}.mp4"
    if dest.exists():
        log(lf, {"scene": name, "status": "skip", "why": "already saved"}); return {"status": "skip"}
    try:
        ok, model, credits = apply_settings(pg, a, s["dur"])
        if not ok:
            log(lf, {"scene": name, "status": "STOP", "why": f"settings mismatch (model={model})", "port": port}); return {"status": "mismatch"}
        if credits is None or spent + credits > a.max_credits:
            log(lf, {"scene": name, "status": "STOP", "why": f"credit cap (spent {spent}, next {credits}, cap {a.max_credits})", "port": port}); return {"status": "stop"}
        before = media_ids(pg)
        base_alerts = set(alert_lines(pg))
        box = pg.locator("[contenteditable=true]").first
        box.click(); pg.keyboard.press("Control+A"); pg.keyboard.press("Delete")
        pg.keyboard.insert_text(s["prompt"].strip()); pg.wait_for_timeout(700)
        go = pg.get_by_role("button", name="생성 시작")
        if not go.count() or go.is_disabled():
            log(lf, {"scene": name, "status": "STOP", "why": "생성 시작 없음/비활성", "port": port}); return {"status": "stop"}
        go.click()
        src, why = None, None
        while time.time() - t0 < a.timeout:
            pg.wait_for_timeout(8000)
            new = media_ids(pg) - before
            if new:
                src = video_url_for(pg, new.pop())
                if src:
                    break
            hit = [l[:80] for l in alert_lines(pg) if l not in base_alerts and any(w in l for w in STOP_WORDS)]
            if hit:
                why = f"stop words in alert: {hit}"; break
        if not src:
            log(lf, {"scene": name, "status": "STOP", "why": why or "timeout", "sec": round(time.time() - t0), "port": port})
            return {"status": "retry" if why and "실패" in why else "stop", "why": why or "timeout", "spent": credits}
        status, body = download(pg, src)
        if status != 200 or len(body) < 10000:  # 2026-09-25: 403 오류 페이지(111바이트)를 영상으로 저장하고 ok로 기록하던 버그
            log(lf, {"scene": name, "status": "STOP", "why": f"download http {status}, {len(body)} bytes", "sec": round(time.time() - t0), "port": port})
            return {"status": "stop", "spent": credits}
        dest.write_bytes(body)
        log(lf, {"scene": name, "status": "ok", "bytes": dest.stat().st_size, "http": status,
                 "sec": round(time.time() - t0), "credits": credits, "model": model, "port": port})
        return {"status": "ok", "spent": credits}
    except Exception as e:  # 핏 예외표 ①: 한 씬의 예외가 배치 전체를 끝내지 않게(9222 '생성 시작' 없음으로 28분 방치)
        log(lf, {"scene": name, "status": "STOP", "why": f"error: {type(e).__name__}: {str(e)[:150]}", "sec": round(time.time() - t0), "port": port})
        return {"status": "stop"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes"); ap.add_argument("outdir")
    ap.add_argument("--model", default="Omni 1.1 Flash"); ap.add_argument("--res", default="360p")
    ap.add_argument("--ratio", default="9:16"); ap.add_argument("--mode", default="소재")
    ap.add_argument("--max-credits", type=int, default=30); ap.add_argument("--only", default="")
    ap.add_argument("--timeout", type=int, default=180)  # 2026-09-25 핏: 10분 대기는 방치가 길다, 순수 생성은 1~2분
    ap.add_argument("--ports", default="9222",
                    help="쓸 계정 포트 순서(예: 9224,9225,9222). 크레딧·한도로 막히면 다음 포트로 넘어가 같은 씬부터 이어 한다")
    a = ap.parse_args()
    scenes = json.loads(Path(a.scenes).read_text(encoding="utf-8"))
    if a.only:
        keep = set(a.only.split(",")); scenes = [s for s in scenes if s["name"] in keep]
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    ports = [int(x) for x in a.ports.split(",")]
    with open(out / "batch_log.jsonl", "a", encoding="utf-8") as lf, sync_playwright() as p:
      for port in ports:
        spent = 0
        try:
            b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
        except Exception as e:
            log(lf, {"port": port, "status": "STOP", "why": f"cdp connect: {str(e)[:120]}"}); continue
        cands = [x for c in b.contexts for x in c.pages if "flow.google.com/project" in x.url]
        if not cands:
            pg = b.contexts[0].pages[0] if b.contexts[0].pages else b.contexts[0].new_page()
            pg.goto("https://labs.google/fx/tools/flow", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(5000)
            np_btn = pg.get_by_role("button", name="새 프로젝트", exact=False)
            if np_btn.count():
                np_btn.first.click(); pg.wait_for_timeout(6000)
            if "flow.google.com/project" not in pg.url:
                log(lf, {"port": port, "status": "STOP", "why": "no Flow project tab (사람이 프로젝트를 한 번 열어 둘 것)"}); continue
        else:
            pg = cands[0]
            try:  # 오래 열어 둔 탭은 영상 주소 서명이 만료돼 403(2026-09-25 9229, 4.5시간)
                pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
            except Exception:
                pass
        try:
            first_run_cleanup(pg)
        except Exception:
            pass
        log(lf, {"port": port, "status": "account", "url": pg.url[-40:]})
        switch = False
        for s in scenes:
          retried = False
          while True:  # '실패'면 같은 포트에서 한 번 더
            result = run_scene(pg, a, s, out, lf, port, spent)
            spent += result.get("spent", 0)
            if result["status"] == "retry" and not retried:
                retried = True; log(lf, {"scene": s["name"], "status": "retry", "why": result["why"], "port": port}); continue
            break
          if result["status"] in ("ok", "skip"):
            continue
          # 무슨 이유든 이 계정에서 멈춘 씬은 다음 포트에서 같은 씬부터 다시(핏 예외표 ①). 설정 불일치만 사람이 볼 차례.
          switch = result["status"] != "mismatch"; break
        else:
            break  # 모든 씬 끝
        if not switch:
            break  # 설정 불일치는 사람·AI가 볼 차례
        log(lf, {"port": port, "status": "switch", "why": "scene stopped, next account"})
    sizes = {}
    for f in sorted(out.glob("*.mp4")):
        sizes.setdefault(f.stat().st_size, []).append(f.name)
    dup = [v for v in sizes.values() if len(v) > 1]
    print("VERIFY", "FAIL duplicate sizes: " + str(dup) if dup else f"OK {sum(len(v) for v in sizes.values())} unique files", f"| credits spent {spent}")
    sys.exit(1 if dup else 0)


if __name__ == "__main__":
    main()
