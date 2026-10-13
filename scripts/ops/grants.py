#!/usr/bin/env python3
"""지원사업 현황표(국가·지자체·기업·VC) 관리 도구(2026-10-14 탐, 사장님 지시: "테이블 DB 형태로 관리, 사장이 지원현황표 보여주세요 하면 표로").

저장: 운영 DB tasks 표의 section='grant' 행(새 표를 만들지 않아 DDL 승인이 필요 없다, proc.py가 section='step'을 쓰는 것과 같은 방식).
열 대응: owner=구분(국가|지자체|기업|VC) · no=G번호 · title=사업명 · status=우리 상태 · source_date=마지막 확인일 · next_action=다음 할 일 ·
         evidence=공식 URL · result=지원규모·마감 요약 · decider=결정자 · raw=세부(JSON: org, window, amount, fit, memo, history)
상태 값: 후보(조사만) · 요건확인(사장님 확인 대기) · 준비중 · 지원함 · 대기(접수 전/결과 대기) · 탈락 · 제외(안 맞음)
값 규칙: 공고문에서 확인한 값만 쓴다. 모르면 '미확인'. 비밀값은 거부한다.

사용:
  python scripts/ops/grants.py list [--kind 국가] [--status 준비중] [--md]      지원현황표(사장님이 보는 표)
  python scripts/ops/grants.py show G03                                       한 건 상세
  python scripts/ops/grants.py add --kind 지자체 --title "…" --org "…" --url "…" --window "…" --amount "…" [--status 후보] [--next "…"] [--memo "…"]
  python scripts/ops/grants.py set G03 --status 준비중 --next "…" [--window …] [--amount …] [--memo …] [--checked]
  python scripts/ops/grants.py seed-md <공고표.md>                             비공개 저장소의 공고표.md 표를 한 번 옮긴다(이미 있는 제목은 건너뜀)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
import opsdb  # noqa: E402

COLS = ("owner", "section", "no", "title", "status", "source_date", "next_action", "evidence", "result", "cost", "decider", "raw", "source")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z]{20,}|xox[bap]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY)")
STATUSES = ("후보", "요건확인", "준비중", "지원함", "대기", "탈락", "제외")
KINDS = ("국가", "지자체", "기업", "VC")


def today():
    return time.strftime("%Y-%m-%d")


def row(**kw):
    r = {c: None for c in COLS}
    r.update(kw)
    return r


def clean(*texts):
    for t in texts:
        if t and SECRET.search(str(t)):
            sys.exit("비밀값 모양이 들어 있어 거부했습니다(값은 기록에 쓰지 않습니다)")


def all_rows():
    return opsdb.select("tasks", "*", where={"section": "eq.grant"}, order="no.asc", limit=1000)


def raw_of(r):
    v = r.get("raw")
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return v or {}


def next_no(rows):
    n = [int(m.group(1)) for r in rows if (m := re.match(r"G(\d+)$", r.get("no") or ""))]
    return f"G{(max(n) + 1) if n else 1:02d}"


def cell(s, n=60):
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_list(a):
    rs = all_rows()
    if a.kind:
        rs = [r for r in rs if r["owner"] == a.kind]
    if a.status:
        rs = [r for r in rs if r["status"] == a.status]
    if not rs:
        print("(지원현황이 비어 있습니다)")
        return
    print(f"## 지원현황표 ({today()} 기준, {len(rs)}건)\n")
    print("| 번호 | 구분 | 사업명 | 기관 | 접수·마감 | 지원규모 | 우리 상태 | 다음 할 일 |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rs:
        w = raw_of(r)
        print(f"| {r['no']} | {r['owner']} | {cell(r['title'], 40)} | {cell(w.get('org'), 24)} | {cell(w.get('window'), 34)} | {cell(w.get('amount'), 30)} | {r['status']} | {cell(r['next_action'], 40)} |")
    c = {}
    for r in rs:
        c[r["status"]] = c.get(r["status"], 0) + 1
    print("\n상태별: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))


def find(no):
    rs = opsdb.select("tasks", "*", where={"section": "eq.grant", "no": f"eq.{no}"}, limit=1)
    if not rs:
        sys.exit(f"{no} 를 찾지 못했습니다(grants.py list 로 번호 확인)")
    return rs[0]


def cmd_show(a):
    r = find(a.no)
    w = raw_of(r)
    print(f"{r['no']} [{r['owner']}] {r['title']}  (상태 {r['status']}, 마지막 확인 {r['source_date']})")
    for k, label in (("org", "기관"), ("window", "접수·마감"), ("amount", "지원규모"), ("fit", "우리 충족"), ("memo", "메모")):
        if w.get(k):
            print(f"- {label}: {w[k]}")
    print(f"- 공식 URL: {r['evidence']}")
    print(f"- 다음 할 일: {r['next_action']}")
    for h in w.get("history", [])[-5:]:
        print(f"  · {h}")


def cmd_add(a):
    clean(a.title, a.org, a.url, a.window, a.amount, a.next, a.memo)
    if a.kind not in KINDS:
        sys.exit(f"구분은 {KINDS} 중 하나")
    st = a.status or "후보"
    if st not in STATUSES:
        sys.exit(f"상태는 {STATUSES} 중 하나")
    rs = all_rows()
    if any((r["title"] or "").strip() == a.title.strip() for r in rs):
        sys.exit("같은 사업명이 이미 있습니다(set 으로 고치세요)")
    no = next_no(rs)
    raw = {"org": a.org, "window": a.window, "amount": a.amount, "memo": a.memo, "history": [f"{today()} 등록({st})"]}
    opsdb.insert("tasks", [row(owner=a.kind, section="grant", no=no, title=a.title[:200], status=st, source_date=today(), next_action=(a.next or "")[:400],
                                evidence=a.url, result=((a.amount or "") + " / " + (a.window or ""))[:300], decider="사장님", raw=json.dumps(raw, ensure_ascii=False), source="grants.py")])
    print(f"등록: {no} [{a.kind}] {a.title} ({st})")


def cmd_set(a):
    r = find(a.no)
    clean(a.next, a.window, a.amount, a.memo, a.url)
    w = raw_of(r)
    vals = {}
    note = []
    if a.status:
        if a.status not in STATUSES:
            sys.exit(f"상태는 {STATUSES} 중 하나")
        note.append(f"상태 {r['status']}→{a.status}")
        vals["status"] = a.status
    if a.next is not None:
        vals["next_action"] = a.next[:400]
        note.append("다음 할 일 변경")
    for k, v, label in (("window", a.window, "접수·마감"), ("amount", a.amount, "지원규모"), ("memo", a.memo, "메모"), ("fit", a.fit, "우리 충족")):
        if v is not None:
            w[k] = v
            note.append(f"{label} 변경")
    if a.url:
        vals["evidence"] = a.url
        note.append("URL 변경")
    if a.checked or note:
        vals["source_date"] = today()
    if not note and not a.checked:
        sys.exit("바꿀 값이 없습니다")
    w.setdefault("history", []).append(f"{today()} " + (", ".join(note) if note else "확인만"))
    vals["raw"] = json.dumps(w, ensure_ascii=False)
    vals["result"] = ((w.get("amount") or "") + " / " + (w.get("window") or ""))[:300]
    opsdb.patch("tasks", {"section": "eq.grant", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no} " + (", ".join(note) if note else "확인일만"))


def kind_of(org):
    if re.search(r"서울|경기|부산|인천|대구|광주|대전|울산|세종|강원|충청|충북|충남|전북|전남|경북|경남|제주|지역지식재산", org or ""):
        return "지자체"
    if re.search(r"Google|Amazon|AWS|Microsoft|NVIDIA|OpenAI|Anthropic|Claude|민간", org or "", re.I):
        return "기업"
    return "국가"


def cmd_seed(a):
    text = Path(a.md).read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.startswith("|")]
    head = next((l for l in lines if "사업명" in l and "주관기관" in l), None)
    if not head:
        sys.exit("표 머리줄을 못 찾음")
    cols = [c.strip() for c in head.strip("|").split("|")]
    idx = {c: i for i, c in enumerate(cols)}
    existing = {(r["title"] or "").strip() for r in all_rows()}
    rs = all_rows()
    new = []
    for l in lines:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) != len(cols) or not cells[0].isdigit():
            continue
        g = lambda name: cells[idx[name]] if name in idx else ""
        title = g("사업명")
        if title in existing:
            continue
        org = g("주관기관")
        kind = kind_of(org + " " + title)
        raw = {"org": org, "window": g("공고일·접수마감"), "amount": g("지원규모(공고문 값)"), "fit": g("우리 충족 상태"), "source_row": f"공고표 {cells[0]}번",
               "history": [f"{today()} 비공개 저장소 공고표.md {cells[0]}번에서 옮김"]}
        no = f"G{len(rs) + len(new) + 1:02d}"
        new.append(row(owner=kind, section="grant", no=no, title=title[:200], status="요건확인", source_date="2026-10-12", next_action="사장님 확인: 우리 충족 상태",
                       evidence=g("공식 공고 URL"), result=(g("지원규모(공고문 값)") + " / " + g("공고일·접수마감"))[:300], decider="사장님", raw=json.dumps(raw, ensure_ascii=False), source="grants.py seed-md"))
    if not new:
        print("옮길 새 행이 없습니다")
        return
    clean(*[json.dumps(r, ensure_ascii=False) for r in new])
    opsdb.insert("tasks", new)
    print(f"{len(new)}건 옮김")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--kind"); s.add_argument("--status"); s.add_argument("--md", action="store_true"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("show"); s.add_argument("no"); s.set_defaults(f=cmd_show)
    s = sub.add_parser("add")
    for k in ("kind", "title"):
        s.add_argument("--" + k, required=True)
    for k in ("org", "url", "window", "amount", "status", "next", "memo"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_add)
    s = sub.add_parser("set"); s.add_argument("no")
    for k in ("status", "next", "window", "amount", "memo", "fit", "url"):
        s.add_argument("--" + k)
    s.add_argument("--checked", action="store_true"); s.set_defaults(f=cmd_set)
    s = sub.add_parser("seed-md"); s.add_argument("md"); s.set_defaults(f=cmd_seed)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
