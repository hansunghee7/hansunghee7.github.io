#!/usr/bin/env python3
"""지원사업 서류 대장(2026-10-14 탐, 사장님 지시: 정보, DB 표, 구글드라이브 공통서류, 지원처별 폴더로 관리).
저장: 운영 DB tasks 표의 section='doc' 행(grants.py·facts.py와 같은 방식, 새 표 없음).
열 대응: no=D번호 · title=서류명 · owner=등급(일반|민감|인증서) · status=보유|만료|발급필요 · source_date=발급일 ·
         result=보관 위치 요약 · evidence=Drive 복사본 URL · next_action=다음 할 일 · raw=JSON(orig=원본 URL, expires=만료일, used_by=쓰는 지원사업)
규칙: 번호류(주민·사업자·법인등록번호)와 비밀값은 거부한다. 만료일이 있으면 expiring 명령이 임박·지난 서류를 보여 준다.

사용:
  python scripts/ops/doc_ledger.py list
  python scripts/ops/doc_ledger.py add --title "..." --grade 일반 --status 보유 [--issued 2026-02-16] [--expires 2026-03-18] [--url ...] [--orig ...] [--used G14,G13] [--next "..."]
  python scripts/ops/doc_ledger.py set D03 --status 만료 --next "..." [--issued ..] [--expires ..] [--url ..]
  python scripts/ops/doc_ledger.py expiring [--days 14]
"""
import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
import opsdb  # noqa: E402

COLS = ("owner", "section", "no", "title", "status", "source_date", "next_action", "evidence", "result", "cost", "decider", "raw", "source")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z]{20,}|xox[bap]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|\b\d{6}-?\d{7}\b|\b\d{3}-\d{2}-\d{5}\b)")
STATUSES = ("보유", "만료", "발급필요")
GRADES = ("일반", "민감", "인증서")


def clean(*texts):
    for t in texts:
        if t and SECRET.search(str(t)):
            sys.exit("번호·비밀값 모양이 들어 있어 거부했습니다(번호는 기록에 쓰지 않습니다)")


def cell(s, n=40):
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def all_rows():
    return opsdb.select("tasks", "*", where={"section": "eq.doc"}, order="no.asc", limit=500)


def next_no(rows):
    n = [int(m.group(1)) for r in rows if (m := re.match(r"D(\d+)$", r.get("no") or ""))]
    return f"D{(max(n) + 1) if n else 1:02d}"


def raw_of(r):
    v = r.get("raw")
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return v or {}


def days_left(expires, today=None):
    """만료일(YYYY-MM-DD)까지 남은 날. 형식이 아니면 None."""
    try:
        d = datetime.date.fromisoformat(expires)
    except Exception:
        return None
    return (d - (today or datetime.date.today())).days


def cmd_list(a):
    rs = all_rows()
    if not rs:
        print("(서류 대장이 비어 있습니다)")
        return
    print(f"## 서류 대장 ({time.strftime('%Y-%m-%d')} 기준, {len(rs)}건)\n")
    print("| 번호 | 서류 | 등급 | 상태 | 발급일 | 만료일 | 쓰는 곳 | 다음 할 일 |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rs:
        w = raw_of(r)
        print(f"| {r['no']} | {cell(r['title'], 34)} | {r['owner']} | {r['status']} | {r['source_date'] or ''} | {w.get('expires') or ''} | {cell(w.get('used_by'), 16)} | {cell(r['next_action'], 40)} |")


def cmd_add(a):
    clean(a.title, a.url, a.orig, a.next)
    if a.grade not in GRADES or a.status not in STATUSES:
        sys.exit(f"등급은 {GRADES}, 상태는 {STATUSES} 중 하나")
    rs = all_rows()
    if any((r["title"] or "").strip() == a.title.strip() for r in rs):
        sys.exit("같은 서류명이 이미 있습니다(set 으로 고치세요)")
    no = next_no(rs)
    raw = {"orig": a.orig, "expires": a.expires, "used_by": a.used}
    row = {c: None for c in COLS}
    row.update(owner=a.grade, section="doc", no=no, title=a.title[:200], status=a.status, source_date=a.issued,
               next_action=(a.next or "")[:400], evidence=a.url, result=(a.url or "")[:300], decider="사장님",
               raw=json.dumps(raw, ensure_ascii=False), source="doc_ledger.py")
    opsdb.insert("tasks", [row])
    print(f"등록: {no} {a.title} ({a.status})")


def cmd_set(a):
    rs = opsdb.select("tasks", "*", where={"section": "eq.doc", "no": f"eq.{a.no}"}, limit=1)
    if not rs:
        sys.exit(f"{a.no} 를 찾지 못했습니다")
    clean(a.next, a.url)
    w = raw_of(rs[0])
    vals = {}
    if a.status:
        if a.status not in STATUSES:
            sys.exit(f"상태는 {STATUSES} 중 하나")
        vals["status"] = a.status
    if a.next is not None:
        vals["next_action"] = a.next[:400]
    if a.issued:
        vals["source_date"] = a.issued
    if a.url:
        vals["evidence"] = a.url
        vals["result"] = a.url[:300]
    if a.expires:
        w["expires"] = a.expires
    if not vals and not a.expires:
        sys.exit("바꿀 값이 없습니다")
    vals["raw"] = json.dumps(w, ensure_ascii=False)
    opsdb.patch("tasks", {"section": "eq.doc", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no}")


def cmd_expiring(a):
    n = 0
    for r in all_rows():
        d = days_left(raw_of(r).get("expires") or "")
        if d is not None and d <= a.days:
            n += 1
            print(f"{r['no']} {r['title']}: " + (f"{-d}일 지남" if d < 0 else f"{d}일 남음"))
    if not n:
        print(f"{a.days}일 안에 만료되는 서류가 없습니다")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list")
    s.set_defaults(f=cmd_list)
    s = sub.add_parser("add")
    for k in ("title", "grade", "status"):
        s.add_argument("--" + k, required=True)
    for k in ("issued", "expires", "url", "orig", "used", "next"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_add)
    s = sub.add_parser("set")
    s.add_argument("no")
    for k in ("status", "next", "issued", "expires", "url"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_set)
    s = sub.add_parser("expiring")
    s.add_argument("--days", type=int, default=14)
    s.set_defaults(f=cmd_expiring)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
