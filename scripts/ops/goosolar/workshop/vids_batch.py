#!/usr/bin/env python3
"""Vids 여러 씬 연속 생성기 (구PC 작업실, 2026-09-24 탐).

씬마다 새 Vids 문서(핏 §3 "씬마다 새 문서" 규칙) → 세로 모드 → AI 동영상 → 영어 프롬프트 → 생성 →
AI 창 안의 글자로 완료 판정 → 삽입 → 제목을 씬 이름으로 → <video> src 직접 저장.
화면 캡처와 AI 호출이 없다. 한도·거부·실패 문구가 AI 창에 뜨면 멈춘다.

사용: python vids_batch.py scenes_en.json out/ep13_vids [--only 씬02] [--timeout 600] [--ports 9226,9222]
      [--download1080]        씬을 만들 때마다 옆 탭에서 "파일 → 다운로드 → MP4"(1080x1920) 렌더링을 걸어 두고
                              다음 씬 생성을 계속한다. 결과는 out/<편>_1080/<씬>.mp4 (2026-09-24 사장님 화질 결정 ③)
      [--download1080-only]   생성 없이, 이 폴더 batch_log.jsonl에 기록된 문서들만 1080으로 받는다
scenes_en.json: [{"name": "씬02", "prompt": "<순수 영어 문장>"}, ...]
  (Vids는 한글·대괄호 프롬프트를 약관 위반으로 거부한다. 핏 GENERATION_PIPELINES §3 4번)
"""
import argparse, json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

STOP_WORDS = ("한도", "위반", "실패", "정책", "다시 시도", "생성할 수 없", "문제가 발생")


def log(f, rec):
    rec["t"] = time.strftime("%H:%M:%S")
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()


def panel_lines(pg):
    """AI 창(heading "AI 동영상 클립") 아래 글자만. 화면 전체를 보면 툴바 "텍스트 삽입"을 완료로 오인한다."""
    lines = [l.strip() for l in pg.locator("body").aria_snapshot().splitlines() if l.strip()]
    i = next((k for k, l in enumerate(lines) if "AI 동영상 클립" in l and "heading" in l), None)
    return [] if i is None else [l for l in lines[i:i + 30] if "배너" not in l and "영어로" not in l]


def one_scene(pg, s, out, timeout):
    t0 = time.time()
    pg.goto("https://docs.google.com/videos/create", wait_until="domcontentloaded", timeout=60000)
    pg.get_by_role("button", name="세로 동영상 만들기").wait_for(timeout=30000)
    pg.get_by_role("button", name="세로 동영상 만들기").click(); pg.wait_for_timeout(600)
    if pg.get_by_role("button", name="세로 동영상 만들기").get_attribute("aria-pressed") != "true":
        return {"status": "STOP", "why": "portrait not pressed"}
    pg.get_by_role("button", name="AI 동영상 만들기", exact=False).first.click()
    box = pg.get_by_role("textbox", name="동영상을 설명하세요", exact=False)
    box.wait_for(timeout=30000)
    setting = pg.get_by_role("button", name="Omni", exact=False).first.inner_text()
    if "세로" not in setting:
        return {"status": "STOP", "why": f"setting not portrait: {setting}"}
    box.click(); pg.keyboard.insert_text(s["prompt"].strip()); pg.wait_for_timeout(700)
    go = pg.get_by_role("button", name="생성", exact=True)
    if go.is_disabled():
        return {"status": "STOP", "why": "생성 disabled"}
    go.click()
    while time.time() - t0 < timeout:
        pg.wait_for_timeout(10000)
        pl = panel_lines(pg); joined = " ".join(pl)
        hit = [w for w in STOP_WORDS if w in joined]
        if hit:
            return {"status": "STOP", "why": f"panel says {hit}: {joined[:200]}"}
        if "progressbar" not in joined and any('button "삽입"' in l for l in pl):
            break
    else:
        return {"status": "STOP", "why": "timeout"}
    pg.get_by_role("button", name="삽입", exact=True).click(); pg.wait_for_timeout(3000)
    t = pg.get_by_role("textbox", name="이름 바꾸기")
    t.click(); t.fill(s["name"]); pg.keyboard.press("Enter"); pg.wait_for_timeout(1500)
    srcs = [v.get_attribute("src") or "" for v in pg.locator("video").all()]
    http = [u for u in srcs if u.startswith("http")]
    if not http:
        return {"status": "STOP", "why": "no downloadable video src"}
    r = pg.context.request.get(http[-1]); dest = out / f"{s['name']}.mp4"; dest.write_bytes(r.body())
    return {"status": "ok", "bytes": dest.stat().st_size, "http": r.status, "sec": round(time.time() - t0),
            "doc": pg.url.split("/d/")[1].split("/")[0], "title": pg.title()}


class Exporter:
    """Vids "파일 → 다운로드 → MP4"를 옆 탭에서 걸어 두고, 다운로드가 생기면 씬 이름으로 저장한다.
    Vids는 렌더링 중 탭을 열어 두라고 하므로 씬마다 탭 하나를 두고 끝나면 닫는다.
    다운로드는 Playwright의 download 이벤트로 받는다. 브라우저에 CDP로 다운로드 폴더를 따로 지정하면
    Playwright의 다운로드 처리와 충돌해 파일이 어디에도 안 떨어졌다(2026-09-24 첫 시험, Vids는 "다운로드 시작"이라고만 표시)."""

    def __init__(self, browser, outdir, lf):
        self.ctx = browser.contexts[0]
        self.dest = outdir.parent / (outdir.name + "_1080")
        self.dest.mkdir(parents=True, exist_ok=True)
        self.lf = lf
        self.pending, self.ready = {}, {}

    def start(self, name, doc):
        if (self.dest / f"{name}.mp4").exists():
            log(self.lf, {"scene": name, "status": "skip1080"}); return
        pg = self.ctx.new_page()
        pg.on("download", lambda d, n=name: self.ready.__setitem__(n, d))
        pg.goto(f"https://docs.google.com/videos/d/{doc}/edit", wait_until="domcontentloaded", timeout=60000)
        pg.get_by_role("menuitem", name="파일").wait_for(timeout=40000); pg.wait_for_timeout(3000)
        pg.get_by_role("menuitem", name="파일").click(); pg.wait_for_timeout(800)
        pg.get_by_role("menuitem", name="다운로드", exact=False).first.hover(); pg.wait_for_timeout(800)
        pg.get_by_role("menuitem", name="MP4 동영상", exact=False).first.click()
        self.pending[name] = {"page": pg, "t0": time.time(), "doc": doc}
        log(self.lf, {"scene": name, "status": "render1080_started"})

    def reap(self):
        for name, d in list(self.ready.items()):
            dest = self.dest / f"{name}.mp4"
            d.save_as(str(dest))  # 다운로드가 끝날 때까지 기다린 뒤 저장
            self.ready.pop(name)
            info = self.pending.pop(name, None)
            if info:
                info["page"].close()
            log(self.lf, {"scene": name, "status": "ok1080", "bytes": dest.stat().st_size,
                          "sec": round(time.time() - info["t0"]) if info else None})

    def wait_all(self, timeout=900):
        t0 = time.time()
        while self.pending and time.time() - t0 < timeout:
            next(iter(self.pending.values()))["page"].wait_for_timeout(5000)  # 이벤트는 대기 중에 처리된다
            self.reap()
        for name, info in list(self.pending.items()):
            log(self.lf, {"scene": name, "status": "STOP1080", "why": "render/download timeout", "doc": info["doc"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes"); ap.add_argument("outdir")
    ap.add_argument("--only", default=""); ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--download1080", action="store_true")
    ap.add_argument("--download1080-only", action="store_true")
    ap.add_argument("--ports", default="9222",
                    help="쓸 계정 포트 순서(예: 9226,9222). AI 창에 한도 문구가 뜨면 다음 포트로 넘어가 같은 씬부터 이어 한다")
    a = ap.parse_args()
    scenes = json.loads(Path(a.scenes).read_text(encoding="utf-8"))
    if a.only:
        keep = set(a.only.split(",")); scenes = [s for s in scenes if s["name"] in keep]
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    ports = [int(x) for x in a.ports.split(",")]
    if a.download1080_only:
        return export_only(a, out, ports[0])
    with open(out / "batch_log.jsonl", "a", encoding="utf-8") as lf, sync_playwright() as p:
        for port in ports:
            b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
            pg = b.contexts[0].new_page()
            exp = Exporter(b, out, lf) if a.download1080 else None
            log(lf, {"port": port, "status": "account"})
            switch = False
            for s in scenes:
                if (out / f"{s['name']}.mp4").exists():
                    log(lf, {"scene": s["name"], "status": "skip"}); continue
                try:
                    rec = {"scene": s["name"], "port": port, **one_scene(pg, s, out, a.timeout)}
                except Exception as e:
                    rec = {"scene": s["name"], "port": port, "status": "STOP", "why": f"error: {str(e)[:150]}"}
                log(lf, rec)
                if rec["status"] != "ok":
                    switch = "한도" in rec.get("why", "")
                    break
                if exp:
                    try:
                        exp.start(s["name"], rec["doc"]); exp.reap()
                    except Exception as e:
                        log(lf, {"scene": s["name"], "status": "STOP1080", "why": f"start error: {str(e)[:120]}"})
            if exp:
                exp.wait_all()
            pg.close()
            if not switch:
                break
            log(lf, {"port": port, "status": "switch", "why": "limit, next account"})
    sizes = {}
    for f in sorted(out.glob("*.mp4")):
        sizes.setdefault(f.stat().st_size, []).append(f.name)
    dup = [v for v in sizes.values() if len(v) > 1]
    print("VERIFY", ("FAIL duplicate sizes: " + str(dup)) if dup else f"OK {sum(len(v) for v in sizes.values())} unique files")
    sys.exit(1 if dup else 0)


def export_only(a, out, port):
    """생성 없이 batch_log.jsonl에 기록된 문서(status ok, doc 있음)를 1080으로 받는다."""
    recs = {}
    for line in open(out / "batch_log.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("status") == "ok" and r.get("doc"):
            recs[r["scene"]] = r["doc"]
    if a.only:
        keep = set(a.only.split(",")); recs = {k: v for k, v in recs.items() if k in keep}
    with open(out / "batch_log.jsonl", "a", encoding="utf-8") as lf, sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
        exp = Exporter(b, out, lf)
        for name, doc in recs.items():
            try:
                exp.start(name, doc); exp.reap()
            except Exception as e:
                log(lf, {"scene": name, "status": "STOP1080", "why": f"start error: {str(e)[:120]}"})
        exp.wait_all()
    got = sorted(f.name for f in exp.dest.glob("*.mp4"))
    print("1080 files:", len(got), got[:5])
    return 0


if __name__ == "__main__":
    main()
