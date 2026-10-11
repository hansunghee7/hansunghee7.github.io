# -*- coding: utf-8 -*-
"""마야 제안 관문(2026-10-11 사장님 지시: KPI에 도움이 되는지 보고 마야가 판단해 사장님께 제안한다, 기본 프로세스).
사장님께 주제·제목·글·초안을 올리기 전에 이 도구로 제안문을 만든다. 아래 네 칸이 비면 만들지 않는다(종료 코드 2).
  1) --kpi    KPI 근거 한 줄: 기준선 대비 어떤 수치 때문에 이 제안이 KPI(링크드인 12시간 좋아요·노출, 홈페이지 유입)에 도움이 되는가
  2) --hyp    가설 id (assets/data/maya_hypotheses.jsonl 의 H1·H2 …) 또는 none(가설 밖 제안이면 이유를 --kpi에 적는다)
  3) --verdict 진행 | 보류 | 폐기  (마야의 판정, 사장님 주관 판단은 그 위에서 덧붙이는 것)
  4) --why    판정 이유 한 줄(약점 포함)
기록: assets/data/maya_proposals.jsonl 에 한 줄 추가(나중에 '제안→사장님 결정→성과'를 주 1회 점검한다).
사용: python scripts/ops/maya_propose.py "<글을 제목으로 부른 이름>" --kpi "..." --hyp H2 --verdict 진행 --why "..." [--send]
--send 이면 텔레그램 신솔라 방에 마야 형식(제목·본문 한 줄·할 일 한 줄)으로 보낸다. 번호로 부르지 않는다(사장님은 번호를 모른다).
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "assets" / "data" / "maya_proposals.jsonl"
HYP = ROOT / "assets" / "data" / "maya_hypotheses.jsonl"


def hyp_ids():
    if not HYP.exists():
        return set()
    return {json.loads(l)["id"] for l in HYP.read_text(encoding="utf-8").splitlines() if l.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title", help="글·주제를 제목으로 부른 이름(번호 금지)")
    ap.add_argument("--kpi", default="")
    ap.add_argument("--hyp", default="")
    ap.add_argument("--verdict", default="", choices=["", "진행", "보류", "폐기"])
    ap.add_argument("--why", default="")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--kind", default="post", choices=["post", "image", "other"],
                    help="image면 후보 11장을 던지지 않고 추천 1장+대안 1장만 올린다(--rec, --alt, --scores 필수)")
    ap.add_argument("--rec", default="", help="image: 추천 이미지 이름(어느 출처의 어떤 장면인지)")
    ap.add_argument("--alt", default="", help="image: 대안 이미지 이름")
    ap.add_argument("--scores", default="", help="image: 이미지 조건 8개 채점 '추천점수,대안점수' 예 7/8,7/8")
    a = ap.parse_args()
    miss = [n for n, v in (("--kpi", a.kpi.strip()), ("--hyp", a.hyp.strip()), ("--verdict", a.verdict), ("--why", a.why.strip())) if not v]
    if miss:
        print("제안 관문 거부: 빈 칸", ", ".join(miss), "(KPI 근거·가설 id·판정·이유가 있어야 사장님께 올린다)")
        return 2
    if re.fullmatch(r"[#N]?\d{3,4}번?", a.title.strip()):
        print("제안 관문 거부: 제목 자리에 글 번호만 있다. 사장님은 번호를 모른다. 글 제목으로 쓴다")
        return 2
    if a.hyp != "none" and a.hyp not in hyp_ids():
        print(f"제안 관문 거부: 가설 id {a.hyp} 가 가설대장에 없다(있는 것: {sorted(hyp_ids())} 또는 none)")
        return 2
    if a.kind == "image":
        sc = a.scores.split(",")
        if not (a.rec.strip() and a.alt.strip() and len(sc) == 2 and all(re.fullmatch(r"[6-8]/8", x.strip()) for x in sc)):
            print("제안 관문 거부: 이미지 제안은 --rec(추천 1장), --alt(대안 1장), --scores 6/8 이상 두 개가 필요하다(후보를 여러 장 던지지 않는다)")
            return 2
        if not re.search(r"좋아요|노출|조회|유입", a.kpi):
            print("제안 관문 거부: 이미지 제안의 KPI 근거에 좋아요·노출·조회·유입 중 어떤 지표를 올리는지 적어야 한다")
            return 2
        a.title = f"{a.title} (추천: {a.rec}, 대안: {a.alt}, 채점 {a.scores})"
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    rec = {"at": now, "title": a.title, "kpi": a.kpi, "hyp": a.hyp, "verdict": a.verdict, "why": a.why, "boss": "대기"}
    with LEDGER.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    msg = (f"[마야 제안] {a.title}\n마야 판정: {a.verdict}. KPI 근거: {a.kpi} (가설 {a.hyp}). 이유와 약점: {a.why}\n"
           f"👉 진행/보류/폐기 중 정해 주세요(마야 판정과 다르면 이유 한 줄).")
    print(msg)
    if a.send:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "ops" / "tg_boss.py"), "text", msg, "--persona", "마야"],
                           capture_output=True, text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print((r.stdout or r.stderr).strip()[-120:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
