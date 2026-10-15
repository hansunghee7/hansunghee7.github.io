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
  python scripts/ops/ctxfix.py patterns          공통 패턴별 성공·실패 집계(회사 이름 없이)
  python scripts/ops/ctxfix.py findcheck         --query가 있는 건마다 기억 도우미로 찾기 시험(못 찾으면 위치·형태 조정 필요)
  python scripts/ops/ctxfix.py recheck           반영된 건마다 '재발 신호'를 반영일 이후 기록에서 찾아 성공·재발을 자동 판정

재발 방지 루프(사장님 10/15: "실수 원인을 명확히 진단, 에이전트에게 스스로 재발방지책을 세우게 하면 늘 빈틈이 있고 시간이 지나면 재발, 에이전틱하게 해결"):
  ① 원인 분류를 강제한다(--cause): 지식(규칙을 못 찾음)·충돌(규칙끼리 어긋남)·관문없음(판정 가능한데 문서에만)·모호(지시가 두 뜻)·도구(기능 부족)·능력(모델 한계).
  ② 고침 수준을 기록한다(--level): 문서 < 정본통합 < 훅·관문 < 도구·DB. 원인 분류마다 맞는 수준이 있다(관문없음 → 훅, 지식 → 정본·색인).
  ③ 재발 신호를 적는다(--signal 파일:정규식): 그 실수가 다시 일어나면 남는 로그 한 줄의 모양. 실수한 에이전트가 아니라 기록이 판정한다.
  ④ recheck가 매일 반영일 이후 신호를 센다: 0건이 7일 이어지면 성공, 다시 나오면 재발 → 상태 '실패', 다음 고침 수준을 제안 칸에 올린다(문서로 막았으면 훅으로)."""
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
CAUSES = ("지식", "충돌", "관문없음", "모호", "도구", "능력")
LEVELS = ("문서", "정본통합", "훅·관문", "도구·DB")
OPS = Path("C:/work/_ops")
TS = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?")
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
    if a.cause and a.cause not in CAUSES:
        sys.exit(f"원인 분류는 {CAUSES} 중 하나")
    if a.level and a.level not in LEVELS:
        sys.exit(f"고침 수준은 {LEVELS} 중 하나")
    raw = {"pattern": a.pattern, "cause": a.cause or "", "level": a.level or "", "signal": a.signal or "",
           "impacts": a.impacts or "", "side_effect": a.side_effect or "", "test": a.test or "", "before": a.before or "",
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
        if a.status == "반영":
            raw["applied"] = time.strftime("%Y-%m-%d %H:%M:%S")  # 재발은 이 시각 이후 기록만 센다
    for k in ("cause", "level", "signal", "query"):
        v = getattr(a, k, None)
        if v:
            raw[k] = v
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
        print(f"{r['no']} [{r['owner']}] {r['status']} | {r['title']} | 패턴: {raw.get('pattern', '')} | 원인: {raw.get('cause', '')} | 수준: {raw.get('level', '')} | 신호: {raw.get('signal', '')} | 고칠 곳: {r.get('next_action') or ''} | 전: {raw.get('before', '')} | 결과: {r.get('result') or ''}")


def signal_hits(signal, since):
    """신호 '파일:정규식'으로 C:/work/_ops/<파일>에서 since 이후 줄 수를 센다(시각은 줄 안의 첫 YYYY-MM-DD HH:MM 모양)."""
    if not signal or ":" not in signal:
        return None
    fname, pat = signal.split(":", 1)
    p = OPS / fname
    if not p.exists():
        return None
    rx = re.compile(pat)
    n = 0
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.search(ln)
        if m and m.group(0).replace("T", " ") >= since and rx.search(ln):
            n += 1
    return n


def cmd_recheck(a):
    """반영·성공 상태인 건을 매일 다시 본다. 실수한 에이전트의 자기 평가가 아니라 기록이 판정한다."""
    today = time.strftime("%Y-%m-%d")
    for r in rows():
        if r["status"] not in ("반영", "성공"):
            continue
        raw = raw_of(r)
        since = raw.get("applied") or r.get("source_date") or today
        n = signal_hits(raw.get("signal"), since)
        if n is None:
            print(f"{r['no']} 신호 없음(재발 판정 불가, --signal 필요): {r['title']}")
            continue
        days = (time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(since[:10], "%Y-%m-%d"))) / 86400
        if n > 0:
            lv = raw.get("level") or "문서"
            nxt = LEVELS[min(LEVELS.index(lv) + 1, len(LEVELS) - 1)] if lv in LEVELS else "훅·관문"
            raw.setdefault("history", []).append(f"{today} 재발 {n}건(반영 {since} 이후) → 다음 수준 제안: {nxt}")
            raw["next_level"] = nxt
            opsdb.patch("tasks", {"section": "eq.ctxfix", "no": f"eq.{r['no']}"}, {"status": "실패", "raw": raw, "result": f"재발 {n}건, 다음 고침 수준 {nxt}", "source_date": today})
            print(f"{r['no']} 재발 {n}건 → 실패, 다음 수준 {nxt}: {r['title']}")
        elif days >= 7 and r["status"] != "성공":
            raw.setdefault("history", []).append(f"{today} 7일 재발 0건 → 성공")
            opsdb.patch("tasks", {"section": "eq.ctxfix", "no": f"eq.{r['no']}"}, {"status": "성공", "raw": raw, "result": f"반영 {since} 이후 {int(days)}일 재발 0건", "source_date": today})
            print(f"{r['no']} 7일 재발 0건 → 성공: {r['title']}")
        else:
            print(f"{r['no']} 재발 0건({int(days)}일째, 7일 뒤 성공 판정): {r['title']}")


def cmd_findcheck(a):
    """찾기 시험(사장님 10/15 구조 진단): 장부의 --query(실수한 에이전트가 물었을 질문)로 기억 도우미(recall)를 돌려
    고칠 곳(정본)이나 제목이 1·2차 결과에 나오는지 본다. 안 나오면 '위치·형태 조정 필요'로 표시한다."""
    import recall
    for r in rows():
        raw = raw_of(r)
        q = raw.get("query")
        if not q:
            continue
        res = recall.query(q) or {}
        lines = "\n".join(recall.render(res)) if res else ""
        target = (r.get("next_action") or "").split()[0] if r.get("next_action") else ""
        key = Path(target).name if target else ""
        found = bool(lines) and ((key and key in lines) or (r["title"][:12] in lines) or (r["no"] in lines))
        verdict = "찾음" if found else "못 찾음 → 위치·형태 조정 필요(1차 카드 승격·정본 통합·동의어)"
        raw.setdefault("history", []).append(f"{time.strftime('%Y-%m-%d')} 찾기 시험: {verdict}")
        raw["findable"] = found
        opsdb.patch("tasks", {"section": "eq.ctxfix", "no": f"eq.{r['no']}"}, {"raw": raw})
        print(f"{r['no']} 찾기 시험 '{q}': {verdict}")


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
    p.add_argument("--cause", help="지식|충돌|관문없음|모호|도구|능력")
    p.add_argument("--level", help="문서|정본통합|훅·관문|도구·DB")
    p.add_argument("--signal", help="재발 신호 '로그파일:정규식' (예: save_gate_log.jsonl:cross-session-message)")
    p = sp.add_parser("set")
    p.add_argument("no")
    p.add_argument("--status")
    p.add_argument("--evidence")
    p.add_argument("--after")
    p.add_argument("--note")
    p.add_argument("--cause")
    p.add_argument("--level")
    p.add_argument("--signal")
    p.add_argument("--query", help="찾기 시험 질문(실수한 에이전트가 물었을 말)")
    p = sp.add_parser("list")
    p.add_argument("--company")
    p.add_argument("--status")
    sp.add_parser("patterns")
    sp.add_parser("recheck")
    sp.add_parser("findcheck")
    a = ap.parse_args()
    {"add": cmd_add, "set": cmd_set, "list": cmd_list, "patterns": cmd_patterns, "recheck": cmd_recheck, "findcheck": cmd_findcheck}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
