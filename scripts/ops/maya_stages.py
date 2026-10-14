# -*- coding: utf-8 -*-
"""마야 자동 단계표(슈퍼프로세스 5부품, 2026-10-11). 증거 파일을 읽어 글 한 편의 단계별 빈칸('-')을 보여 준다.
사람이 '했다'고 쓰는 표가 아니다. 증거가 있어야 채워진다. 읽기 전용.

단계(홈페이지 글 한 편): 카드(작업 카드 파일) → 경험(카드의 경험 칸 또는 다이얼로그 요약) → 예약(발행 계획 상태) → 글번호(url) → SNS(링크드인·인스타 큐 항목) → 반응수집(post_reactions) → 실험(링크드인 A/B 기록)
증거: assets/data/publish_plan.json, sns_publish_queue.json, post_reactions.json, linkedin_experiment.json, simplifier-cxo-db/ink/카드/<날짜>-*.md

사용: python scripts/ops/maya_stages.py [--from 2026-10-01] [--md 출력경로]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "assets" / "data"
CARDS = Path("C:/work/simplifier-cxo-db/ink/카드")


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="since", default="2026-10-01")
    ap.add_argument("--md")
    a = ap.parse_args()
    plan = [p for p in load("publish_plan.json") if p["date"] >= a.since and p["track"].startswith("홈페이지")]
    queue = load("sns_publish_queue.json")
    react = load("post_reactions.json")
    # 링크드인·리멤버는 구PC 무인 프로필이 매일 읽은 결과(maya_linkedin_pull.py가 가져옴)도 반응수집 증거로 본다(2026-10-13)
    auto_heads = []
    for fn in ("C:/work/_ops/maya_linkedin_latest.json",):
        try:
            auto_heads += [q.get("title") or "" for q in json.loads(Path(fn).read_text(encoding="utf-8")).get("posts", [])]
        except Exception:
            pass
    exp = {e["post"]: e for e in load("linkedin_experiment.json")["posts"]}
    titles = [t for t in load("posts.json") if t["id"] >= 600]
    cards = [c.name for c in CARDS.glob("*.md")] if CARDS.exists() else []
    rows, blanks = [], 0
    for p in sorted(plan, key=lambda x: x["date"]):
        m = re.search(r"/logs/(\d+)/", p.get("url") or "")
        post = m.group(1) if m else None
        if not post:  # 계획에 url이 없으면 posts.json 제목(앞 10자)으로 찾는다
            for t in titles:
                if t["title"][:10] == p["topic"][:10]:
                    post = str(t["id"])
        cf = next((c for c in cards if c.startswith(p["date"])), None)
        card = "OK" if cf else "-"
        # 경험 칸: 카드 머리말에 '경험:' 항목이 있고 비어 있지 않아야 OK(사장님 직접 겪은 장면, 2026-10-11 지적: 트렌드 글에 경험 없음)
        exp_ok = "-"
        if cf:
            head = (CARDS / cf).read_text(encoding="utf-8").split("---")[1] if (CARDS / cf).read_text(encoding="utf-8").startswith("---") else ""
            m2 = re.search(r"^경험:\s*(.+)$", head, re.M)
            # 심플리파이어 다이얼로그 답변은 사장님 쓴 글 400여 편·책 2권 기반이라 사장님 경험·글로 취급(사장님 지시 2026-10-11)
            m3 = re.search(r"요약_경로:\s*\"?(\S.+)", head)
            exp_ok = "OK" if (m2 and m2.group(1).strip().strip('"')) or m3 else "-"
        # 방향·글감 수집 칸(N31, 2026-10-14): 카드 머리말에 '방향:' 항목이 있어야 OK. 기존 카드엔 없어서 빈칸 집계에서는 뺀다(새 카드부터 채움)
        dir_ok = "-"
        if cf:
            txt = (CARDS / cf).read_text(encoding="utf-8")
            hd = txt.split("---")[1] if txt.startswith("---") else ""
            m4 = re.search(r"^방향:\s*(.+)$", hd, re.M)
            dir_ok = "OK" if m4 and m4.group(1).strip().strip('"') else "-"
        resv = "OK" if re.search(r"예약|완료", p["status"]) else "-"
        qs = [q for q in queue if post and q["post_ref"] == post and q["status"] != "cancelled"]
        sns = ",".join(sorted({q["platform"][:2] for q in qs})) or "-"
        rc = "OK" if post and (any(r["post"] == post for r in react) or any(p["topic"][:10] and p["topic"][:10] in h for h in auto_heads)) else "-"
        ex = "OK" if post in exp and any(exp[post]["snaps"].values()) else ("등록만" if post in exp else "-")
        cells = [card, exp_ok, dir_ok, resv, post or "-", sns, rc, ex]
        blanks += sum(1 for c in (card, exp_ok, resv, sns, rc, ex) if c == "-")
        rows.append((p["date"], p["topic"][:28], *cells))
    head = "| 날짜 | 주제 | 카드 | 경험 | 방향 | 예약 | 글번호 | SNS큐 | 반응수집 | 실험 |\n|---|---|---|---|---|---|---|---|---|\n"
    out = head + "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    out += f"\n\n글 {len(rows)}편, 빈칸 {blanks}개 (빈칸 '-' = 증거 파일에 없음)"
    print(out)
    if a.md:
        Path(a.md).write_text("# 마야 단계표(자동 생성, maya_stages.py)\n\n" + out + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
