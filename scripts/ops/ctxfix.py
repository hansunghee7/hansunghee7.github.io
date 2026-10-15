# -*- coding: utf-8 -*-
"""컨텍스트 수정 경험 장부(2026-10-15 탐, 사장님: "중앙에서 컨텍스트 수정에 대한 경험과 성공·실패 DB를 누적해서 가지고 있어야 함.
다양한 회사들이 들어올수록 이 에이전트는 똑똑해짐. 회사별로 컨텍스트는 관리하되, 공통 접점 포인트를 우리는 수집해야 함").

두 층으로 나눈다(고객 데이터 노출 금지 원칙):
  ① 회사별 기록(company=회사 코드): 무엇을 고쳤나, 어디에 영향, 결과. 그 회사 안에서만 본다.
  ② 공통 패턴(pattern=유형 이름): 회사 이름·원문 없이 '어떤 종류의 실수가, 어떤 고침으로, 성공·실패했나'만. 이것이 중앙 지식이다.
저장: 운영 DB tasks 표의 section='ctxfix' 행(새 표 없이, grants.py·proc.py와 같은 방식).
열: owner=회사 코드 · no=CF번호 · title=제안 제목 · status=제안|채택|기각|반영|성공|실패 · next_action=고칠 곳(정본) · evidence=근거·PR · result=결과 지표 · raw=JSON(pattern, impacts, side_effect, test, before, after, history)
사용:
  python scripts/ops/ctxfix.py add --company simplifier --pattern "출처 혼동(타 세션 글을 사람 지시로 기록)" --title "..." --target ".claude/hooks/save-gate.py" [--impacts "..."] [--test "..."] [--before "오기록 7/7건"]
  python scripts/ops/ctxfix.py set CF001 --status 반영 --evidence "PR 1234" [--after "오기록 0/7건"] [--note "..."]
  python scripts/ops/ctxfix.py list [--company simplifier] [--status 채택]
  python scripts/ops/ctxfix.py patterns          공통 패턴별 성공·실패 집계(회사 이름 없이)"""
import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

COLS = ("owner", "section", "no", "title", "status", "source_date", "next_action", "evidence", "result", "cost", "decider", "raw", "source")
STATUSES = ("제안", "채택", "기각", "반영", "성공", "실패")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z]{20,}|xox[bap]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY)")


def clean(*texts):
    for t in texts:
        if t and SECRET.search(str(t)):
            sys.exit("비밀값 모양이 들어 있어 거부했습니다(값은 기록에 쓰지 않습니다)")


def rows(where=None):
    w = {"section": "eq.ctxfix"}
    w.update(where or {})
    return opsdb.select("tasks", "*", where=w, order="no.asc", limit=2000)


def raw_of(r):
    v = r.get("raw") or {}
    return v if isinstance(v, dict) else json.loads(v or "{}")


def cmd_add(a):
    clean(a.title, a.target, a.impacts, a.test, a.before, a.pattern)
    allr = rows()
    n = max([int(r["no"][2:]) for r in allr if (r.get("no") or "").startswith("CF")] + [0]) + 1
    no = f"CF{n:03d}"
    raw = {"pattern": a.pattern, "impacts": a.impacts or "", "side_effect": a.side_effect or "", "test": a.test or "", "before": a.before or "",
           "after": "", "history": [f"{time.strftime('%Y-%m-%d')} 제안"]}
    r = {c: None for c in COLS}
    r.update(owner=a.company, section="ctxfix", no=no, title=a.title[:200], status="제안", source_date=time.strftime("%Y-%m-%d"),
             next_action=(a.target or "")[:400], raw=raw, source="ctxfix.py")
    opsdb.insert("tasks", [r])
    print(f"추가: {no} [{a.company}] {a.title} (패턴: {a.pattern})")


def cmd_set(a):
    clean(a.evidence, a.after, a.note)
    cur = rows({"no": f"eq.{a.no}"})
    if not cur:
        sys.exit(f"{a.no} 없음")
    raw = raw_of(cur[0])
    vals = {}
    if a.status:
        if a.status not in STATUSES:
            sys.exit(f"상태는 {STATUSES} 중 하나")
        vals["status"] = a.status
    if a.evidence:
        vals["evidence"] = a.evidence[:400]
    if a.after:
        raw["after"] = a.after
        vals["result"] = a.after[:400]
    raw.setdefault("history", []).append(f"{time.strftime('%Y-%m-%d')} {a.status or ''} {a.note or ''}".strip())
    vals["raw"] = raw
    vals["source_date"] = time.strftime("%Y-%m-%d")
    opsdb.patch("tasks", {"section": "eq.ctxfix", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no} {vals.get('status', '')}")


def cmd_list(a):
    w = {}
    if a.company:
        w["owner"] = f"eq.{a.company}"
    if a.status:
        w["status"] = f"eq.{a.status}"
    for r in rows(w):
        raw = raw_of(r)
        print(f"{r['no']} [{r['owner']}] {r['status']} | {r['title']} | 패턴: {raw.get('pattern', '')} | 고칠 곳: {r.get('next_action') or ''} | 결과: {r.get('result') or ''}")


def cmd_patterns(a):
    """회사 이름 없이 패턴별 성공·실패만(중앙 지식)."""
    agg = collections.defaultdict(collections.Counter)
    companies = collections.defaultdict(set)
    for r in rows():
        p = raw_of(r).get("pattern") or "(분류 없음)"
        agg[p][r["status"]] += 1
        companies[p].add(r["owner"])
    for p, c in sorted(agg.items(), key=lambda x: -sum(x[1].values())):
        print(f"- {p}: 회사 {len(companies[p])}곳, " + ", ".join(f"{k} {v}" for k, v in c.most_common()))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("--company", required=True)
    p.add_argument("--pattern", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--target")
    p.add_argument("--impacts")
    p.add_argument("--side-effect")
    p.add_argument("--test")
    p.add_argument("--before")
    p = sp.add_parser("set")
    p.add_argument("no")
    p.add_argument("--status")
    p.add_argument("--evidence")
    p.add_argument("--after")
    p.add_argument("--note")
    p = sp.add_parser("list")
    p.add_argument("--company")
    p.add_argument("--status")
    sp.add_parser("patterns")
    a = ap.parse_args()
    {"add": cmd_add, "set": cmd_set, "list": cmd_list, "patterns": cmd_patterns}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
