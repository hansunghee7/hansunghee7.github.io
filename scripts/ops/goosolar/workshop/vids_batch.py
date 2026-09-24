#!/usr/bin/env python3
"""Vids 여러 씬 연속 생성기 (구PC 작업실, 2026-09-24 탐).

씬마다 새 Vids 문서(핏 §3 "씬마다 새 문서" 규칙) → 세로 모드 → AI 동영상 → 영어 프롬프트 → 생성 →
AI 창 안의 글자로 완료 판정 → 삽입 → 제목을 씬 이름으로 → <video> src 직접 저장.
화면 캡처와 AI 호출이 없다. 한도·거부·실패 문구가 AI 창에 뜨면 멈춘다.

사용: python vids_batch.py scenes_en.json out/ep13_vids [--only 씬02] [--timeout 600]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes"); ap.add_argument("outdir")
    ap.add_argument("--only", default=""); ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    scenes = json.loads(Path(a.scenes).read_text(encoding="utf-8"))
    if a.only:
        keep = set(a.only.split(",")); scenes = [s for s in scenes if s["name"] in keep]
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    with open(out / "batch_log.jsonl", "a", encoding="utf-8") as lf, sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        pg = b.contexts[0].new_page()
        for s in scenes:
            if (out / f"{s['name']}.mp4").exists():
                log(lf, {"scene": s["name"], "status": "skip"}); continue
            rec = {"scene": s["name"], **one_scene(pg, s, out, a.timeout)}
            log(lf, rec)
            if rec["status"] != "ok":
                break
        pg.close()
    sizes = {}
    for f in sorted(out.glob("*.mp4")):
        sizes.setdefault(f.stat().st_size, []).append(f.name)
    dup = [v for v in sizes.values() if len(v) > 1]
    print("VERIFY", ("FAIL duplicate sizes: " + str(dup)) if dup else f"OK {sum(len(v) for v in sizes.values())} unique files")
    sys.exit(1 if dup else 0)


if __name__ == "__main__":
    main()
