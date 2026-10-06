#!/usr/bin/env python3
"""지투 PO 성장 루프 도구(2026-10-06 사장님 지시: 보강 4·2·3·1을 1회성이 아니라 루프로).

네 루프의 기록장이다. 문서(docs/지투_PO_성장루프.md)가 방법을, 이 도구가 기록과 "기한 지난 것" 판정을, 훅(.claude/hooks/jitu-loop.py)이 상기를 맡는다.
  gap      보강 4  검사 공백 원장: 사고마다 "어떤 검사가 없었나"와 "추가한 검사"를 짝으로 남긴다. 추가한 검사가 비면 열린 건.
  kpi      보강 2  외부 고객 지표 주간 기록(활성 호출자·활성화·유지·찾지 못한 검색률·피드백 수). 7일 넘게 안 재면 기한 지남.
  feedback 보강 3  고객 신호(feedback 호출·찾지 못한 검색·사용 기록 이상)의 수집→분류→백로그→회신 상태.
  predict  보강 1  예측과 결과의 짝: 변경마다 "무엇이 얼마나 바뀔지" 한 줄과 점검일, 점검일에 실제 값을 적는다.
  ask      결정 요청 기록(2026-10-06 사장님 지시 ①②): 보스에게 결정을 물을 때 추천·답이 없을 때의 기본값·마감을 같이 적고,
           한 번 물은 결정은 답이 올 때까지 다시 묻지 않고 한 줄 상태만 남긴다. 물어보기 전에 `ask find 낱말`로 이미 물었는지 본다.
  due      루프와 결정 요청에서 기한 지난 것만 모아 보인다(훅이 하이~ 때 이걸 부른다).
저장: C:/work/_ops/jitu_po/*.jsonl (저장소 밖. 고객 신호가 들어가므로 공개 저장소에 두지 않는다). JITU_PO_DIR로 바꿀 수 있다.
비밀값·고객 이름 원문은 넣지 않는다(호출자 별칭만).
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.environ.get("JITU_PO_DIR", "C:/work/_ops/jitu_po")
FILES = {"gap": "gaps.jsonl", "kpi": "kpi.jsonl", "feedback": "feedback.jsonl", "predict": "predictions.jsonl", "ask": "asks.jsonl"}
KPI_EVERY_DAYS = 7
FEEDBACK_TRIAGE_DAYS = 1
FEEDBACK_REPLY_DAYS = 7
ASK_STATUS_DAYS = 1  # 이 날수가 지나도 답이 없으면 due에 올려 '다시 묻지 말고 상태 한 줄만'을 상기
FB_STATES = ["new", "triaged", "backlog", "replied", "dropped"]


def today():
    return dt.date.fromisoformat(os.environ["JITU_PO_TODAY"]) if os.environ.get("JITU_PO_TODAY") else dt.date.today()


def path(kind):
    os.makedirs(ROOT, exist_ok=True)
    return os.path.join(ROOT, FILES[kind])


def load(kind):
    p = path(kind)
    if not os.path.exists(p):
        return []
    rows = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def save(kind, rows):
    p = path(kind)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def next_id(rows, prefix):
    n = 0
    for r in rows:
        try:
            n = max(n, int(str(r.get("id", "")).split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}-{n + 1}"


def days_since(date_str):
    try:
        return (today() - dt.date.fromisoformat(date_str[:10])).days
    except Exception:
        return 0


def find(rows, rid):
    for r in rows:
        if r["id"] == rid:
            return r
    sys.exit(f"없는 번호: {rid}")


# ---------------- gap (보강 4) ----------------
def gap_add(a):
    rows = load("gap")
    r = {"id": next_id(rows, "G"), "date": str(today()), "what": a.what, "missing": a.missing,
         "added": a.added or "", "ref": a.ref or "", "closed": str(today()) if a.added else ""}
    rows.append(r)
    save("gap", rows)
    print(f"{r['id']} 기록{' (추가한 검사까지 있어 닫힘)' if a.added else ' (열림: 추가한 검사가 아직 없다)'}")


def gap_close(a):
    rows = load("gap")
    r = find(rows, a.id)
    r["added"] = a.added
    r["closed"] = str(today())
    if a.ref:
        r["ref"] = a.ref
    save("gap", rows)
    print(f"{a.id} 닫음")


def gap_list(a):
    for r in load("gap"):
        if a.open and r.get("added"):
            continue
        state = "닫힘" if r.get("added") else "열림"
        print(f"{r['id']} [{state}] {r['date']} {r['what']} | 없던 검사: {r['missing']} | 추가: {r.get('added') or '-'}")


# ---------------- kpi (보강 2) ----------------
def kpi_add(a):
    rows = load("kpi")
    r = {"id": next_id(rows, "K"), "date": str(today()), "week": a.week or dt.date.today().strftime("%G-W%V"),
         "ext_active_callers_7d": a.active, "ext_views_7d": a.views, "ext_cites_7d": a.cites,
         "ext_misses_7d": a.misses, "ext_feedback_7d": a.feedback,
         "activated": a.activated or "", "retained": a.retained or "", "note": a.note or ""}
    r["miss_rate"] = round(a.misses / a.views, 3) if a.views else None
    rows.append(r)
    save("kpi", rows)
    print(f"{r['id']} 기록: 활성 호출자 {a.active}, 조회 {a.views}, 인용 {a.cites}, 찾지 못한 검색 {a.misses}(비율 {r['miss_rate']}), 피드백 {a.feedback}")


def kpi_list(a):
    rows = load("kpi")
    for r in rows[-(a.last or 8):]:
        print(f"{r['id']} {r['date']} {r['week']} 활성 {r['ext_active_callers_7d']} 조회 {r['ext_views_7d']} 인용 {r['ext_cites_7d']} "
              f"미스 {r['ext_misses_7d']}({r['miss_rate']}) 피드백 {r['ext_feedback_7d']} | 활성화 {r['activated'] or '-'} 유지 {r['retained'] or '-'} | {r['note']}")


# ---------------- feedback (보강 3) ----------------
def fb_add(a):
    rows = load("feedback")
    r = {"id": next_id(rows, "F"), "date": str(today()), "source": a.source, "who": a.who or "", "text": a.text,
         "state": "new", "kind": "", "action": "", "reply": "", "updated": str(today())}
    rows.append(r)
    save("feedback", rows)
    print(f"{r['id']} 수집 (state=new, 하루 안에 분류)")


def fb_triage(a):
    rows = load("feedback")
    r = find(rows, a.id)
    r["kind"] = a.kind
    r["action"] = a.action or r["action"]
    r["state"] = a.state
    r["updated"] = str(today())
    if a.reply:
        r["reply"] = a.reply
    save("feedback", rows)
    print(f"{a.id} -> {a.state} ({a.kind}) {a.action or ''}")


def fb_list(a):
    for r in load("feedback"):
        if a.open and r["state"] in ("replied", "dropped"):
            continue
        print(f"{r['id']} [{r['state']}] {r['date']} {r['source']}/{r['who']} {r['kind'] or '-'} | {r['text'][:90]} | 조치: {r['action'] or '-'}")


# ---------------- predict (보강 1) ----------------
def pr_add(a):
    rows = load("predict")
    r = {"id": next_id(rows, "P"), "date": str(today()), "change": a.change, "expect": a.expect, "metric": a.metric,
         "check_on": a.check_on, "actual": "", "verdict": "", "lesson": ""}
    rows.append(r)
    save("predict", rows)
    print(f"{r['id']} 예측 기록: 점검일 {a.check_on}")


def pr_check(a):
    rows = load("predict")
    r = find(rows, a.id)
    r["actual"] = a.actual
    r["verdict"] = a.verdict
    r["lesson"] = a.lesson or ""
    save("predict", rows)
    print(f"{a.id} 결과 기록: {a.verdict} (실제 {a.actual})")


def pr_list(a):
    rows = load("predict")
    for r in rows:
        if a.open and r["verdict"]:
            continue
        v = r["verdict"] or ("점검일 지남" if r["check_on"] <= str(today()) else "대기")
        print(f"{r['id']} [{v}] {r['date']} {r['change']} | 예측: {r['expect']} ({r['metric']}) | 점검일 {r['check_on']} | 실제 {r['actual'] or '-'}")
    done = [r for r in rows if r["verdict"]]
    if done:
        hit = sum(1 for r in done if r["verdict"] == "적중")
        print(f"적중률: {hit}/{len(done)}")


# ---------------- ask (결정 요청: 추천 + 기본값 + 마감, 한 번만 묻기) ----------------
def now_iso():
    return os.environ.get("JITU_PO_NOW") or dt.datetime.now().strftime("%Y-%m-%dT%H:%M")


def tokens(text):
    import re
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", text.lower())}


def similar(a, b, floor=0.6, minshared=4):
    """두 글의 낱말 겹침(작은 쪽 기준). 같은 결정을 다시 묻는지 거칠게 판정한다."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    shared = len(ta & tb)
    return shared >= minshared and shared / min(len(ta), len(tb)) >= floor


def ask_add(a):
    rows = load("ask")
    r = {"id": next_id(rows, "A"), "date": str(today()), "created": a.created or now_iso(), "text": a.text, "rec": a.rec,
         "default": a.default, "due": a.due or "", "answer": "", "answered": ""}
    rows.append(r)
    save("ask", rows)
    print(f"{r['id']} 결정 요청 기록: 추천 [{a.rec}] / 답이 없으면 [{a.default}]" + (f" / 마감 {a.due}" if a.due else ""))


def ask_find(a):
    hit = False
    for r in load("ask"):
        hay = r["text"] + " " + r["rec"]
        if all(w in hay for w in a.words):  # 조사(메일을·메일은)에 흔들리지 않게 낱말이 글 안에 들어 있는지로 본다
            hit = True
            state = f"답 {r['answer']}" if r["answer"] else f"답 대기({days_since(r['date'])}일)"
            print(f"{r['id']} [{state}] {r['date']} {r['text'][:80]} | 추천: {r['rec'][:40]} | 기본값: {r['default'][:40]}")
    if not hit:
        print("이미 물은 비슷한 결정 없음")


def ask_answer(a):
    rows = load("ask")
    r = find(rows, a.id)
    r["answer"] = a.answer
    r["answered"] = str(today())
    save("ask", rows)
    print(f"{a.id} 답 기록: {a.answer}")


def ask_list(a):
    for r in load("ask"):
        if a.open and r["answer"]:
            continue
        state = f"답 {r['answer']}" if r["answer"] else "답 대기"
        print(f"{r['id']} [{state}] {r['date']} {r['text'][:70]} | 추천 {r['rec'][:30]} | 기본값 {r['default'][:30]}" + (f" | 마감 {r['due']}" if r["due"] else ""))


# ---------------- due ----------------
def due_items():
    out = {"gap": [], "kpi": [], "feedback": [], "predict": [], "ask": []}
    for r in load("gap"):
        if not r.get("added"):
            out["gap"].append(f"{r['id']} {r['what']}(없던 검사: {r['missing']})")
    kpis = load("kpi")
    if not kpis:
        out["kpi"].append("지표를 한 번도 안 쟀다")
    else:
        d = days_since(kpis[-1]["date"])
        if d >= KPI_EVERY_DAYS:
            out["kpi"].append(f"마지막 측정 {d}일 전({kpis[-1]['date']})")
    for r in load("feedback"):
        age = days_since(r["updated"])
        if r["state"] == "new" and age >= FEEDBACK_TRIAGE_DAYS:
            out["feedback"].append(f"{r['id']} 분류 안 함 {age}일: {r['text'][:50]}")
        elif r["state"] in ("triaged", "backlog") and days_since(r["date"]) >= FEEDBACK_REPLY_DAYS and not r["reply"]:
            out["feedback"].append(f"{r['id']} 회신 안 함 {days_since(r['date'])}일: {r['text'][:50]}")
    for r in load("ask"):
        if not r["answer"]:
            age = days_since(r["date"])
            overdue = bool(r["due"]) and r["due"] < str(today())
            if age >= ASK_STATUS_DAYS or overdue:
                out["ask"].append(f"{r['id']} 답 대기 {age}일{'(마감 지남)' if overdue else ''}: {r['text'][:50]} (다시 묻지 말고 한 줄 상태만, 기본값: {r['default'][:30]})")
    for r in load("predict"):
        if not r["verdict"] and r["check_on"] <= str(today()):
            out["predict"].append(f"{r['id']} 점검일 {r['check_on']} 지남: {r['change'][:50]}")
    return out


def due(a):
    d = due_items()
    n = sum(len(v) for v in d.values())
    if a.quiet and n == 0:
        return
    names = {"gap": "검사 공백(보강 4)", "kpi": "지표 측정(보강 2)", "feedback": "고객 신호(보강 3)", "predict": "예측 점검(보강 1)", "ask": "결정 요청(답 대기)"}
    print(f"🔁 지투 루프 점검: 기한 지난 것 {n}건")
    for k in ("gap", "kpi", "feedback", "predict", "ask"):
        for line in d[k]:
            print(f"  - {names[k]}: {line}")
    if n:
        print("  방법: docs/지투_PO_성장루프.md, 기록 도구: python scripts/ops/jitu_po.py <gap|kpi|feedback|predict> ...")


def build():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gap").add_subparsers(dest="sub", required=True)
    x = g.add_parser("add"); x.add_argument("--what", required=True); x.add_argument("--missing", required=True)
    x.add_argument("--added", default=""); x.add_argument("--ref", default=""); x.set_defaults(fn=gap_add)
    x = g.add_parser("close"); x.add_argument("id"); x.add_argument("--added", required=True); x.add_argument("--ref", default="")
    x.set_defaults(fn=gap_close)
    x = g.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=gap_list)

    k = sub.add_parser("kpi").add_subparsers(dest="sub", required=True)
    x = k.add_parser("add"); x.add_argument("--week", default="")
    for name in ("active", "views", "cites", "misses", "feedback"):
        x.add_argument(f"--{name}", type=int, required=True)
    x.add_argument("--activated", default=""); x.add_argument("--retained", default=""); x.add_argument("--note", default="")
    x.set_defaults(fn=kpi_add)
    x = k.add_parser("list"); x.add_argument("--last", type=int, default=8); x.set_defaults(fn=kpi_list)

    f = sub.add_parser("feedback").add_subparsers(dest="sub", required=True)
    x = f.add_parser("add"); x.add_argument("--source", required=True, help="feedback도구|찾지못한검색|사용기록|면담")
    x.add_argument("--who", default=""); x.add_argument("--text", required=True); x.set_defaults(fn=fb_add)
    x = f.add_parser("triage"); x.add_argument("id"); x.add_argument("--kind", required=True, help="버그|UX|요청|내용공백|칭찬|잡음")
    x.add_argument("--state", choices=FB_STATES[1:], default="triaged"); x.add_argument("--action", default="")
    x.add_argument("--reply", default=""); x.set_defaults(fn=fb_triage)
    x = f.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=fb_list)

    r = sub.add_parser("predict").add_subparsers(dest="sub", required=True)
    x = r.add_parser("add"); x.add_argument("--change", required=True); x.add_argument("--expect", required=True)
    x.add_argument("--metric", required=True); x.add_argument("--check-on", required=True, dest="check_on"); x.set_defaults(fn=pr_add)
    x = r.add_parser("check"); x.add_argument("id"); x.add_argument("--actual", required=True)
    x.add_argument("--verdict", required=True, choices=["적중", "빗나감", "판정불가"]); x.add_argument("--lesson", default="")
    x.set_defaults(fn=pr_check)
    x = r.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=pr_list)

    q = sub.add_parser("ask").add_subparsers(dest="sub", required=True)
    x = q.add_parser("add"); x.add_argument("--text", required=True, help="무엇을 정해 달라는지 한 줄")
    x.add_argument("--rec", required=True, help="추천과 한 줄 이유"); x.add_argument("--default", required=True, help="답이 없을 때 어떻게 되는지(기본값)")
    x.add_argument("--due", default="", help="마감 YYYY-MM-DD(선택)"); x.add_argument("--created", default=""); x.set_defaults(fn=ask_add)
    x = q.add_parser("find"); x.add_argument("words", nargs="+"); x.set_defaults(fn=ask_find)
    x = q.add_parser("answer"); x.add_argument("id"); x.add_argument("--answer", required=True); x.set_defaults(fn=ask_answer)
    x = q.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=ask_list)

    x = sub.add_parser("due"); x.add_argument("--quiet", action="store_true"); x.set_defaults(fn=due)
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = build().parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
