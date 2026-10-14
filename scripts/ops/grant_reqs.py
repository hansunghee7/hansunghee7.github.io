#!/usr/bin/env python3
"""지원사업 요건 매핑과 실천항목(2026-10-14 탐, 사장님 지시: 조사 내용을 각 지원사업 요건과 매핑해 DB를 먼저 갱신하고,
우선순위·일정·임팩트로 요건을 채울 실천항목을 정한다).
저장: 운영 DB tasks 표의 section='req'(요건 매핑)와 section='act'(실천항목). grants.py·facts.py·doc_ledger.py와 같은 방식, 새 표 없음.

공통요건(section='creq'): 여러 사업이 같이 묻는 요건(업력·소재지·근로자 수·재무 등)을 한 번만 적고 우리 상태의 정본으로 쓴다.
  no=C번호 · owner=분류(A~E) · title=공통요건명 · status=충족|미충족|확인필요 · result=우리 값 · evidence=출처 · raw=JSON(fact=F번호)
  사업별 요건(req)은 --common C번호로 공통요건에 연결하고, 사업마다 다른 기준값(예: 업력 3~7년)과 판정만 적는다.
req 열 대응: no=Q번호 · owner=지원사업 G번호 · title=요건 · status=충족|미충족|확인필요|해당없음 · source_date=마지막 확인일 ·
             result=우리 사실(F번호 포함) · evidence=근거(공식 URL 또는 출처) · next_action=채우는 방법 · raw=JSON(cat=A~E, fact=F번호, common=C번호)
             분류: A 자격(업력·소재지·법인·업종) / B 고객 실증 / C 기술성 / D 재무 / E 제품 성숙도 (공고표 정본의 5분류와 같다)
act 열 대응: no=A번호 · title=실천항목 · owner=담당(탐|사장님|세무사) · status=대기|진행|완료 · source_date=기한 ·
             result=임팩트 한 줄 · next_action=완료 기준 · raw=JSON(grants=G번호들, fills=Q번호들, priority=1~3, impact=상|중|하)
규칙: 번호류(주민·사업자·법인등록번호)와 비밀값은 거부한다.

사용:
  python scripts/ops/grant_reqs.py req list [--grant G14]
  python scripts/ops/grant_reqs.py req add --grant G14 --cat A --title "업력 3년 초과 7년 이내" --status 충족 --fact F01 --result "..." --evidence "..." --next "..."
  python scripts/ops/grant_reqs.py req set Q03 --status 충족 --result "..." [--next ..] [--evidence ..]
  python scripts/ops/grant_reqs.py common list
  python scripts/ops/grant_reqs.py common add --cat A --title "업력" --status 충족 --fact F01 --result "..." --evidence "..."
  python scripts/ops/grant_reqs.py common set C01 --status 충족 --result "..."
  python scripts/ops/grant_reqs.py matrix
  python scripts/ops/grant_reqs.py act list [--status 대기]
  python scripts/ops/grant_reqs.py act add --title "..." --who 탐 --due 2026-10-21 --priority 1 --impact 상 --grants G14 --fills Q05,Q06 --result "..." --done "..."
  python scripts/ops/grant_reqs.py boss [--days 14]     # 사장님 백로그: 1순위=임팩트 상+긴급, 2순위=긴급, 3순위=나머지
  python scripts/ops/grant_reqs.py act set A02 --status 진행 [--due ..] [--done ..]
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
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z]{20,}|xox[bap]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|\b\d{6}-?\d{7}\b|\b\d{3}-\d{2}-\d{5}\b)")
REQ_STATUS = ("충족", "미충족", "확인필요", "해당없음")
ACT_STATUS = ("대기", "진행", "완료")
CATS = ("A", "B", "C", "D", "E")
WHO = ("탐", "사장님", "세무사")


def clean(*texts):
    for t in texts:
        if t and SECRET.search(str(t)):
            sys.exit("번호·비밀값 모양이 들어 있어 거부했습니다(번호는 기록에 쓰지 않습니다)")


def cell(s, n=40):
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def raw_of(r):
    v = r.get("raw")
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return v or {}


def next_no(rows, prefix):
    n = [int(m.group(1)) for r in rows if (m := re.match(prefix + r"(\d+)$", r.get("no") or ""))]
    return f"{prefix}{(max(n) + 1) if n else 1:02d}"


def rows_of(section):
    return opsdb.select("tasks", "*", where={"section": f"eq.{section}"}, order="no.asc", limit=1000)


def matrix_counts(reqs):
    """지원사업별 요건 상태 집계: {G번호: {상태: 개수}}."""
    out = {}
    for r in reqs:
        g = r.get("owner") or "?"
        out.setdefault(g, {s: 0 for s in REQ_STATUS})
        out[g][r.get("status")] = out[g].get(r.get("status"), 0) + 1
    return out


def act_sort_key(r):
    w = raw_of(r)
    done = 1 if r.get("status") == "완료" else 0
    return (done, int(w.get("priority") or 9), r.get("source_date") or "9999-99-99")


def cmd_req_list(a):
    rs = rows_of("req")
    if a.grant:
        rs = [r for r in rs if r.get("owner") == a.grant]
    if not rs:
        print("(요건 매핑이 비어 있습니다)")
        return
    print(f"## 요건 매핑 ({time.strftime('%Y-%m-%d')} 기준, {len(rs)}건)\n")
    print("| 번호 | 사업 | 분류 | 요건 | 상태 | 우리 사실 | 채우는 방법 |")
    print("|---|---|---|---|---|---|---|")
    for r in rs:
        w = raw_of(r)
        print(f"| {r['no']} | {r['owner']} | {w.get('cat') or ''} | {cell(r['title'], 30)} | {r['status']} | {cell(r['result'], 36)} | {cell(r['next_action'], 36)} |")


def cmd_req_add(a):
    clean(a.title, a.result, a.evidence, a.next)
    if a.cat not in CATS or a.status not in REQ_STATUS:
        sys.exit(f"분류는 {CATS}, 상태는 {REQ_STATUS} 중 하나")
    rs = rows_of("req")
    if any(r.get("owner") == a.grant and (r.get("title") or "").strip() == a.title.strip() for r in rs):
        sys.exit("같은 사업의 같은 요건이 이미 있습니다(set 으로 고치세요)")
    no = next_no(rs, "Q")
    row = {c: None for c in COLS}
    row.update(owner=a.grant, section="req", no=no, title=a.title[:200], status=a.status, source_date=time.strftime("%Y-%m-%d"),
               next_action=(a.next or "")[:400], evidence=(a.evidence or "")[:300], result=(a.result or "")[:400], decider="사장님",
               raw=json.dumps({"cat": a.cat, "fact": a.fact, "common": a.common}, ensure_ascii=False), source="grant_reqs.py")
    opsdb.insert("tasks", [row])
    print(f"등록: {no} {a.grant} {a.title} ({a.status})")


def cmd_req_set(a):
    rs = opsdb.select("tasks", "*", where={"section": "eq.req", "no": f"eq.{a.no}"}, limit=1)
    if not rs:
        sys.exit(f"{a.no} 를 찾지 못했습니다")
    clean(a.result, a.evidence, a.next)
    vals = {}
    if a.status:
        if a.status not in REQ_STATUS:
            sys.exit(f"상태는 {REQ_STATUS} 중 하나")
        vals["status"] = a.status
    if a.result is not None:
        vals["result"] = a.result[:400]
    if a.evidence is not None:
        vals["evidence"] = a.evidence[:300]
    if a.next is not None:
        vals["next_action"] = a.next[:400]
    if not vals:
        sys.exit("바꿀 값이 없습니다")
    vals["source_date"] = time.strftime("%Y-%m-%d")
    opsdb.patch("tasks", {"section": "eq.req", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no}")


def common_usage(reqs):
    """공통요건 번호별로 연결된 사업별 요건 수: {C번호: 개수}."""
    out = {}
    for r in reqs:
        c = raw_of(r).get("common")
        if c:
            out[c] = out.get(c, 0) + 1
    return out


def cmd_common_list(a):
    rs = rows_of("creq")
    if not rs:
        print("(공통요건이 비어 있습니다)")
        return
    use = common_usage(rows_of("req"))
    print(f"## 공통요건 ({time.strftime('%Y-%m-%d')} 기준, {len(rs)}건)\n")
    print("| 번호 | 분류 | 공통요건 | 우리 상태 | 우리 값 | 사실표 | 연결된 사업 요건 |")
    print("|---|---|---|---|---|---|---|")
    for r in rs:
        print(f"| {r['no']} | {r['owner']} | {cell(r['title'], 24)} | {r['status']} | {cell(r['result'], 44)} | {raw_of(r).get('fact') or ''} | {use.get(r['no'], 0)} |")


def cmd_common_add(a):
    clean(a.title, a.result, a.evidence)
    if a.cat not in CATS or a.status not in ("충족", "미충족", "확인필요"):
        sys.exit(f"분류는 {CATS}, 상태는 충족·미충족·확인필요 중 하나")
    rs = rows_of("creq")
    if any((r.get("title") or "").strip() == a.title.strip() for r in rs):
        sys.exit("같은 공통요건이 이미 있습니다(set 으로 고치세요)")
    no = next_no(rs, "C")
    row = {c: None for c in COLS}
    row.update(owner=a.cat, section="creq", no=no, title=a.title[:200], status=a.status, source_date=time.strftime("%Y-%m-%d"),
               evidence=(a.evidence or "")[:300], result=(a.result or "")[:400], decider="사장님",
               raw=json.dumps({"fact": a.fact}, ensure_ascii=False), source="grant_reqs.py")
    opsdb.insert("tasks", [row])
    print(f"등록: {no} {a.title} ({a.status})")


def cmd_common_set(a):
    rs = opsdb.select("tasks", "*", where={"section": "eq.creq", "no": f"eq.{a.no}"}, limit=1)
    if not rs:
        sys.exit(f"{a.no} 를 찾지 못했습니다")
    clean(a.result, a.evidence)
    vals = {}
    if a.status:
        if a.status not in ("충족", "미충족", "확인필요"):
            sys.exit("상태는 충족·미충족·확인필요 중 하나")
        vals["status"] = a.status
    if a.result is not None:
        vals["result"] = a.result[:400]
    if a.evidence is not None:
        vals["evidence"] = a.evidence[:300]
    if not vals:
        sys.exit("바꿀 값이 없습니다")
    vals["source_date"] = time.strftime("%Y-%m-%d")
    opsdb.patch("tasks", {"section": "eq.creq", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no}")


def cmd_matrix(a):
    reqs = rows_of("req")
    mc = matrix_counts(reqs)
    if not mc:
        print("(요건 매핑이 비어 있습니다)")
        return
    print(f"## 사업별 요건 충족 현황 ({time.strftime('%Y-%m-%d')} 기준)\n")
    print("| 사업 | 충족 | 미충족 | 확인필요 | 해당없음 |")
    print("|---|---|---|---|---|")
    for g in sorted(mc):
        c = mc[g]
        print(f"| {g} | {c['충족']} | {c['미충족']} | {c['확인필요']} | {c['해당없음']} |")


def boss_tier(r, days=14, today=None, far=45):
    """사장님 백로그 순위: 1=임팩트 상이면서 긴급, 2=긴급, 3=긴급은 아니지만 far일 이내, 4=far일보다 먼 것.
    긴급 = 기한이 days일 이내(지난 것 포함)."""
    import datetime
    due = r.get("source_date") or ""
    try:
        left = (datetime.date.fromisoformat(due) - (today or datetime.date.today())).days
    except Exception:
        left = None
    urgent = left is not None and left <= days
    if urgent and raw_of(r).get("impact") == "상":
        return 1
    if urgent:
        return 2
    return 4 if left is not None and left > far else 3


def cmd_boss(a):
    rs = [r for r in rows_of("act") if r.get("owner") == "사장님" and r.get("status") != "완료"]
    if not rs:
        print("(사장님 백로그가 비어 있습니다)")
        return
    rs.sort(key=lambda r: (boss_tier(r, a.days), r.get("source_date") or "9999-99-99"))
    print(f"## 지원사업 사장님 백로그 ({time.strftime('%Y-%m-%d')} 기준, 긴급 = 기한 {a.days}일 이내)\n")
    names = {1: "1순위 임팩트 큼 + 긴급", 2: "2순위 긴급", 3: "3순위 한 달 안팎 여유", 4: "4순위 먼 일정(45일 이후)"}
    cur = None
    for r in rs:
        t = boss_tier(r, a.days)
        if t != cur:
            cur = t
            print(f"\n### {names[t]}")
        w = raw_of(r)
        print(f"- {r['no']} {r['source_date'] or ''} {r['title']} [{w.get('impact') or ''}] → {r['next_action'] or ''}")


def cmd_act_list(a):
    rs = rows_of("act")
    if a.status:
        rs = [r for r in rs if r.get("status") == a.status]
    if not rs:
        print("(실천항목이 비어 있습니다)")
        return
    rs.sort(key=act_sort_key)
    print(f"## 실천항목 ({time.strftime('%Y-%m-%d')} 기준, {len(rs)}건, 우선순위·기한 순)\n")
    print("| 번호 | 순위 | 기한 | 담당 | 상태 | 실천항목 | 임팩트 | 채우는 요건 | 완료 기준 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rs:
        w = raw_of(r)
        print(f"| {r['no']} | {w.get('priority') or ''} | {r['source_date'] or ''} | {r['owner']} | {r['status']} | {cell(r['title'], 34)} | {w.get('impact') or ''} {cell(r['result'], 24)} | {cell(w.get('fills'), 16)} | {cell(r['next_action'], 34)} |")


def cmd_act_add(a):
    clean(a.title, a.result, a.done)
    if a.who not in WHO:
        sys.exit(f"담당은 {WHO} 중 하나")
    rs = rows_of("act")
    if any((r.get("title") or "").strip() == a.title.strip() for r in rs):
        sys.exit("같은 실천항목이 이미 있습니다(set 으로 고치세요)")
    no = next_no(rs, "A")
    raw = {"grants": a.grants, "fills": a.fills, "priority": a.priority, "impact": a.impact}
    row = {c: None for c in COLS}
    row.update(owner=a.who, section="act", no=no, title=a.title[:200], status="대기", source_date=a.due,
               next_action=(a.done or "")[:400], result=(a.result or "")[:300], decider="사장님",
               raw=json.dumps(raw, ensure_ascii=False), source="grant_reqs.py")
    opsdb.insert("tasks", [row])
    print(f"등록: {no} {a.title} (기한 {a.due}, 순위 {a.priority})")


def cmd_act_set(a):
    rs = opsdb.select("tasks", "*", where={"section": "eq.act", "no": f"eq.{a.no}"}, limit=1)
    if not rs:
        sys.exit(f"{a.no} 를 찾지 못했습니다")
    clean(a.done, a.result)
    vals = {}
    if a.status:
        if a.status not in ACT_STATUS:
            sys.exit(f"상태는 {ACT_STATUS} 중 하나")
        vals["status"] = a.status
    if a.due:
        vals["source_date"] = a.due
    if a.done is not None:
        vals["next_action"] = a.done[:400]
    if a.result is not None:
        vals["result"] = a.result[:300]
    if not vals:
        sys.exit("바꿀 값이 없습니다")
    opsdb.patch("tasks", {"section": "eq.act", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    top = p.add_subparsers(dest="grp", required=True)
    rq = top.add_parser("req").add_subparsers(dest="cmd", required=True)
    s = rq.add_parser("list")
    s.add_argument("--grant")
    s.set_defaults(f=cmd_req_list)
    s = rq.add_parser("add")
    for k in ("grant", "cat", "title", "status"):
        s.add_argument("--" + k, required=True)
    for k in ("fact", "common", "result", "evidence", "next"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_req_add)
    s = rq.add_parser("set")
    s.add_argument("no")
    for k in ("status", "result", "evidence", "next"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_req_set)
    cm = top.add_parser("common").add_subparsers(dest="cmd", required=True)
    s = cm.add_parser("list")
    s.set_defaults(f=cmd_common_list)
    s = cm.add_parser("add")
    for k in ("cat", "title", "status"):
        s.add_argument("--" + k, required=True)
    for k in ("fact", "result", "evidence"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_common_add)
    s = cm.add_parser("set")
    s.add_argument("no")
    for k in ("status", "result", "evidence"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_common_set)
    s = top.add_parser("matrix")
    s.set_defaults(f=cmd_matrix)
    ac = top.add_parser("act").add_subparsers(dest="cmd", required=True)
    s = top.add_parser("boss")
    s.add_argument("--days", type=int, default=14)
    s.set_defaults(f=cmd_boss)
    s = ac.add_parser("list")
    s.add_argument("--status")
    s.set_defaults(f=cmd_act_list)
    s = ac.add_parser("add")
    for k in ("title", "who", "due", "priority", "impact"):
        s.add_argument("--" + k, required=True)
    for k in ("grants", "fills", "result", "done"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_act_add)
    s = ac.add_parser("set")
    s.add_argument("no")
    for k in ("status", "due", "done", "result"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_act_set)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
