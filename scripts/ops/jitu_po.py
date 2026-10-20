#!/usr/bin/env python3
"""지투 PO 성장 루프 도구(2026-10-06 사장님 지시: 보강 4·2·3·1을 1회성이 아니라 루프로).

네 루프의 기록장이다. 문서(docs/지투_PO_성장루프.md)가 방법을, 이 도구가 기록과 "기한 지난 것" 판정을, 훅(.claude/hooks/jitu-loop.py)이 상기를 맡는다.
  gap      보강 4  검사 공백 원장: 사고마다 "어떤 검사가 없었나"와 "추가한 검사"를 짝으로 남긴다. 추가한 검사가 비면 열린 건.
  kpi      보강 2  외부 고객 지표 주간 기록(활성 호출자·활성화·유지·찾지 못한 검색률·피드백 수). 7일 넘게 안 재면 기한 지남.
  feedback 보강 3  고객 신호(feedback 호출·찾지 못한 검색·사용 기록 이상)의 수집→분류→백로그→회신 상태.
           개선이 배포되면 `feedback ship`(PR·배포일·안내 내용) → `feedback notice-draft`(안내 초안 출력만) → `feedback notified`(보낸 날).
           배포됐는데 안내 안 한 건은 due에 뜬다. 안내 문안 틀: docs/mailcopy/개선_반영_안내_틀.md
  predict  보강 1  예측과 결과의 짝: 변경마다 "무엇이 얼마나 바뀔지" 한 줄과 점검일, 점검일에 실제 값을 적는다.
  ask      결정 요청 기록(2026-10-06 사장님 지시 ①②): 보스에게 결정을 물을 때 추천·답이 없을 때의 기본값·마감을 같이 적고,
           한 번 물은 결정은 답이 올 때까지 다시 묻지 않고 한 줄 상태만 남긴다. 물어보기 전에 `ask find 낱말`로 이미 물었는지 본다.
  req      요구사항 취합(2026-10-06 사장님 지시): 사장님·고객의 개선 요구를 영역별로 모으고, "빠짐없이 모았다는 확신"이 들 때만 `req ready 영역`을
           기록한 뒤 노트에게 전달한다. 새 항목이 들어오면 확신이 취소된다. 훅(jitu-loop pre-send)이 영역 없는 새 요청과 이득 근거 없는 멈춤·변경 요청을 막는다.
  ut       카빗 UT(유저빌리티테스트, 사장님 2026-10-18 명명): 맥락 없는 새 세션을 깨워 실제 경로를 체험시키고 피드백을 받아 개선한다.
           `ut add`(경로·테스터·과제) → `ut result`(막힌 곳·행동 수·걸린 초, 반영 R-번호) → 개선 배포 뒤 `ut add --retest UT-n`으로 같은 경로 재측정.
           결과 없이 2일 넘은 UT와, 개선을 반영했는데 재측정 안 한 UT는 due에 뜬다. 방법: docs/카빗_UT.md
  lead     사전체험 신청(hello@ 수신함 "[초대 요청]") 미처리 감시. 지투 세션 매 발화마다 훅이 alert를 띄운다.
  due      루프와 결정 요청에서 기한 지난 것만 모아 보인다(훅이 하이~ 때 이걸 부른다).
저장: C:/work/_ops/jitu_po/*.jsonl (저장소 밖. 고객 신호가 들어가므로 공개 저장소에 두지 않는다). JITU_PO_DIR로 바꿀 수 있다.
비밀값·고객 이름 원문은 넣지 않는다(호출자 별칭만).
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.environ.get("JITU_PO_DIR", "C:/work/_ops/jitu_po")
FILES = {"gap": "gaps.jsonl", "kpi": "kpi.jsonl", "feedback": "feedback.jsonl", "predict": "predictions.jsonl", "ask": "asks.jsonl", "req": "requirements.jsonl",
         "lead": "leads.jsonl", "ut": "ut.jsonl"}
UT_RESULT_DAYS = 2
# 사전체험 신청(hello@ 수신함의 "[초대 요청]")은 지투 KPI(고객수)에 바로 닿는 신호라 다른 루프보다 먼저 보인다(사장님 10/18 지적)
MAIL_ENV = os.environ.get("CARVIT_MAIL_ENV", "C:/work/_ops/secrets/carvit_mail_read.env")
INTERNAL_DOMAINS = ("@simplifier.co.kr", "@carvit.ai")
KPI_EVERY_DAYS = 7
FEEDBACK_TRIAGE_DAYS = 1
FEEDBACK_REPLY_DAYS = 7
REQ_COLLECT_DAYS = 1  # 모으기 시작 후 이 날수가 지나도 확신(ready)이 없으면 due에 올린다
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


# ---------------- KPI 연결 관문(슈퍼얼라인, 2026-10-12) ----------------
KPI_WORDS = ("고객수", "획득", "리텐션", "유지", "첫 연결", "가입")


def kpi_gate(kpi: str, what: str) -> None:
    """결정 요청과 예측은 지투 KPI(고객수)와 이어져야 기록된다. '해당없음:이유(10자 이상)'는 통과하되 기록에 남는다.
    실제 저장소(C:/work/_ops/jitu_po)에서만 강제한다(시험용 임시 저장소는 JITU_PO_KPI_GATE=on으로 켠다)."""
    forced = os.environ.get("JITU_PO_KPI_GATE") == "on"
    if os.path.abspath(ROOT) != os.path.abspath("C:/work/_ops/jitu_po") and not forced:
        return
    k = (kpi or "").strip()
    if k.startswith("해당없음:") and len(k.split(":", 1)[1].strip()) >= 10:
        return
    if len(k) >= 8 and any(w in k for w in KPI_WORDS):
        return
    sys.exit(f"[KPI 관문] {what}에는 --kpi가 필요합니다: 지투 KPI(고객수 획득·리텐션)에 어떻게 도움이 되는지 8자 이상(예: '가입 24시간 내 첫 연결을 늘려 고객 획득'). 정말 무관하면 --kpi '해당없음:이유 10자 이상'. 정본 docs/지투_KPI.md")


# ---------------- kpi (보강 2) ----------------
def kpi_add(a):
    rows = load("kpi")
    r = {"id": next_id(rows, "K"), "date": str(today()), "week": a.week or dt.date.today().strftime("%G-W%V"),
         "ext_active_callers_7d": a.active, "ext_views_7d": a.views, "ext_cites_7d": a.cites,
         "ext_misses_7d": a.misses, "ext_feedback_7d": a.feedback,
         "activated": a.activated or "", "retained": a.retained or "", "note": a.note or "",
         # 지투 KPI(사장님 지정 2026-10-12): UX MCP와 Carvit 전체 상품의 고객수. 획득(신규)과 리텐션(이탈)으로 나눠 적는다
         "customers": a.customers, "new_customers": a.new_customers, "lost_customers": a.lost_customers}
    r["miss_rate"] = round(a.misses / a.views, 3) if a.views else None
    rows.append(r)
    save("kpi", rows)
    print(f"{r['id']} 기록: 고객수 {a.customers}(신규 {a.new_customers}, 이탈 {a.lost_customers}), 활성 호출자 {a.active}, 조회 {a.views}, 인용 {a.cites}, 찾지 못한 검색 {a.misses}(비율 {r['miss_rate']}), 피드백 {a.feedback}")
    if a.customers is None:
        print("⚠ 지투 KPI인 고객수(--customers)가 비었습니다. 외부 고객 회사 수를 적어야 이 측정이 KPI 기록으로 칩니다.")


def kpi_list(a):
    rows = load("kpi")
    for r in rows[-(a.last or 8):]:
        print(f"{r['id']} {r['date']} {r['week']} 고객 {r.get('customers', '-')}(신규 {r.get('new_customers', '-')} 이탈 {r.get('lost_customers', '-')}) 활성 {r['ext_active_callers_7d']} 조회 {r['ext_views_7d']} 인용 {r['ext_cites_7d']} "
              f"미스 {r['ext_misses_7d']}({r['miss_rate']}) 피드백 {r['ext_feedback_7d']} | 활성화 {r['activated'] or '-'} 유지 {r['retained'] or '-'} | {r['note']}")


# ---------------- feedback (보강 3) ----------------
# 개선 반영 안내(2026-10-17 사장님 결정): 고객 의견 -> PR·배포 -> 안내 메일을 한 행에서 잇는다.
# customer 칸은 실명 대신 별칭만 받는다. 실명 판정은 어려우므로 허용 형식만 통과시킨다(고객<숫자>|내부|신규가입자).

CUSTOMER_RE = re.compile(r"^(고객\d{1,4}|내부|신규가입자)$")
TEMPLATE_REL = os.path.join("docs", "mailcopy", "개선_반영_안내_틀.md")
# --pr에 쓰는 저장소 별칭 허용 목록. 숫자만 넣으면 예전처럼 정수로 저장한다(기존 기록 호환).
PR_REPOS = {"site": "hansunghee7.github.io", "carvit.ai": "carvit.ai", "saegim": "simplifier-saegim"}
PR_RE = re.compile(r"^(?:([A-Za-z0-9._-]+)#)?(\d{1,6})$")


def parse_pr(v):
    v = (v or "").strip().lstrip("#")
    m = PR_RE.match(v)
    allowed = ", ".join(f"{k}={full}" for k, full in PR_REPOS.items())
    if not m:
        sys.exit(f"--pr 형식이 아닙니다: {v}. 숫자(123) 또는 저장소#번호(carvit.ai#37)로 쓰세요. 허용 저장소: {allowed}")
    repo, num = m.group(1), int(m.group(2))
    if repo is None:
        return num
    for alias, full in PR_REPOS.items():
        if repo.lower() in (alias, full.lower()):
            return f"{alias}#{num}"
    sys.exit(f"허용 목록에 없는 저장소입니다: {repo}. 허용 저장소: {allowed}")


def pr_num(n):
    return n if isinstance(n, int) else int(str(n).rsplit("#", 1)[1])


def merge_pr(prs, n):
    """같은 값은 한 번만 둔다. 저장소#번호가 오면 같은 번호의 숫자만 항목을 그 값으로 바꾼다.
    숫자만 오면 같은 번호의 저장소#번호가 이미 있을 때 덧붙이지 않는다(덜 구체적인 값)."""
    if n in prs:
        return prs
    if isinstance(n, int):
        return prs if any(pr_num(x) == n for x in prs) else prs + [n]
    num = pr_num(n)
    if num in prs:
        return [n if x == num else x for x in prs]
    return prs + [n]


def pr_label(n):
    return f"#{n}" if isinstance(n, int) else str(n)


def find_template():
    """틀 찾기 순서: JITU_PO_TEMPLATE(옛 이름 JITU_PO_NOTICE_TEMPLATE) -> 스크립트 기준 -> 현재 폴더 기준."""
    tried = []
    for env in ("JITU_PO_TEMPLATE", "JITU_PO_NOTICE_TEMPLATE"):
        if os.environ.get(env):
            tried.append(os.environ[env])
    tried.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), TEMPLATE_REL))
    tried.append(os.path.join(os.getcwd(), TEMPLATE_REL))
    for p in tried:
        if os.path.isfile(p):
            return p
    print(f"틀 파일을 찾지 못했습니다: {', '.join(tried)}. JITU_PO_TEMPLATE로 경로를 지정하세요.", file=sys.stderr)
    sys.exit(1)


def check_customer(v):
    v = (v or "").strip()
    if v and not CUSTOMER_RE.match(v):
        sys.exit(f"[별칭 관문] --customer는 별칭만 받습니다(고객<숫자>|내부|신규가입자, 예: 고객1). 받은 값은 허용 형식이 아닙니다. 실명·회사명은 넣지 마세요.")
    return v


def check_date(v, what):
    try:
        dt.date.fromisoformat(v)
    except ValueError:
        sys.exit(f"{what}는 YYYY-MM-DD 형식이어야 합니다: {v}")
    return v


def fb_add(a):
    customer = check_customer(getattr(a, "customer", ""))
    rows = load("feedback")
    r = {"id": next_id(rows, "F"), "date": str(today()), "source": a.source, "who": a.who or "", "text": a.text,
         "state": "new", "kind": "", "action": "", "reply": "", "updated": str(today())}
    if customer:
        r["customer"] = customer
    rows.append(r)
    save("feedback", rows)
    print(f"{r['id']} 수집 (state=new, 하루 안에 분류)")


def fb_ship(a):
    rows = load("feedback")
    r = find(rows, a.id)
    if a.customer:
        r["customer"] = check_customer(a.customer)
    prs = [] if a.replace_pr else list(r.get("prs") or [])
    for n in (parse_pr(x) for x in a.pr):
        prs = merge_pr(prs, n)
    r["prs"] = prs
    r["shipped"] = check_date(a.shipped, "--shipped")
    r["notice"] = {"what": a.notice_what, "before": a.notice_before or "", "after": a.notice_after or "", "next": a.notice_next}
    r["updated"] = str(today())
    save("feedback", rows)
    print(f"{a.id} 배포 기록: PR {', '.join(pr_label(n) for n in prs)} / 배포 {r['shipped']} / 안내 아직 안 보냄(notice-draft로 초안)")


def fb_notified(a):
    rows = load("feedback")
    r = find(rows, a.id)
    if not r.get("shipped"):
        sys.exit(f"{a.id}는 배포 기록(ship)이 없습니다. 먼저 fb ship으로 PR·배포일·안내 내용을 채우세요")
    r["notified"] = check_date(a.date, "--date")
    r["updated"] = str(today())
    save("feedback", rows)
    print(f"{a.id} 안내 보낸 날 기록: {r['notified']}")


def load_notice_template():
    tpl = find_template()
    with open(tpl, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"<!-- 틀 시작 -->\s*(.*?)\s*<!-- 틀 끝 -->", text, re.S)
    if not m:
        sys.exit(f"안내 틀에서 '<!-- 틀 시작 -->'~'<!-- 틀 끝 -->' 구간을 찾지 못했습니다: {tpl}")
    return m.group(1).replace("\r\n", "\n").strip("`\n")


def fb_notice_draft(a):
    r = find(load("feedback"), a.id)
    n = r.get("notice") or {}
    if not r.get("shipped") or not n:
        sys.exit(f"{a.id}는 배포·안내 내용이 비어 있습니다. 먼저 fb ship으로 채우세요")
    if n.get("before") or n.get("after"):
        screens = f"바뀌기 전: {n.get('before') or '(없음)'}\n바뀐 뒤: {n.get('after') or '(없음)'}"
    else:
        screens = "화면 사진은 따로 없어요. 바로 열어서 보시면 돼요."
    values = {"말씀": (a.quote or r.get("text", "")).strip(), "바뀐것": n.get("what", ""), "화면전후": screens,
              "다음": n.get("next", ""), "배포일": r.get("shipped", "")}
    out = load_notice_template()
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    print(f"[안내 초안] {a.id} 받는 분: {r.get('customer') or '(별칭 없음)'} / PR {', '.join(pr_label(x) for x in r.get('prs') or [])} (출력만 합니다. 발송은 하지 않습니다)")
    print(out)


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
    kpi_gate(a.kpi, "예측")
    rows = load("predict")
    r = {"id": next_id(rows, "P"), "date": str(today()), "change": a.change, "expect": a.expect, "metric": a.metric,
         "check_on": a.check_on, "actual": "", "verdict": "", "lesson": "", "kpi": a.kpi or ""}
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
    kpi_gate(a.kpi, "결정 요청")
    rows = load("ask")
    r = {"id": next_id(rows, "A"), "date": str(today()), "created": a.created or now_iso(), "text": a.text, "rec": a.rec,
         "default": a.default, "due": a.due or "", "answer": "", "answered": "", "kpi": a.kpi or ""}
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


# ---------------- req (요구사항 취합 후 전달, 개발 중 멈춤·변경은 확실한 이득일 때만) ----------------
def req_state(area):
    """영역 상태: 항목 수, 마지막 확신 시각, 확신 뒤 새 항목 여부."""
    items, ready_idx, last_item_idx = [], -1, -1
    rows = [r for r in load("req") if r.get("area") == area]
    dropped = {r.get("target") for r in rows if r["kind"] in ("drop", "done")}
    for i, r in enumerate(rows):
        if r["kind"] == "item" and r["id"] not in dropped:
            items.append(r)
            last_item_idx = i
        elif r["kind"] == "ready":
            ready_idx = i
    return {"items": len(items), "ready": ready_idx >= 0 and last_item_idx < ready_idx, "had_ready": ready_idx >= 0,
            "first": items[0]["date"] if items else "", "rows": rows}


def req_add(a):
    rows = load("req")
    rid = next_id([r for r in rows if r["kind"] == "item"], "R")
    rows.append({"id": rid, "kind": "item", "date": str(today()), "area": a.area, "text": a.text, "source": a.source})
    save("req", rows)
    st = req_state(a.area)
    print(f"{rid} 영역 [{a.area}]에 추가(항목 {st['items']}개)" + (" - 이전 확신이 취소되었습니다. 다시 점검 뒤 ready를 기록하세요" if st["had_ready"] else ""))


def req_ready(a):
    st = req_state(a.area)
    if st["items"] == 0:
        sys.exit("모은 항목이 없는 영역입니다")
    if len(a.note.strip()) < 20:
        sys.exit("확신 근거(note)를 20자 이상 쓰세요: 선행 작업, 서로 충돌하는 요구, 고객·DB 영향, 확인 방법을 점검한 결과")
    rows = load("req")
    rows.append({"id": "", "kind": "ready", "date": str(today()), "area": a.area, "note": a.note})
    save("req", rows)
    print(f"영역 [{a.area}] 확신 기록(항목 {st['items']}개). 이제 노트에게 [영역: {a.area}] 표지를 달아 전달할 수 있습니다")


def req_sent(a):
    rows = load("req")
    rows.append({"id": "", "kind": "sent", "date": str(today()), "area": a.area, "to": a.to, "ref": a.ref})
    save("req", rows)
    print(f"영역 [{a.area}] 전달 기록: {a.to} {a.ref}")


def req_drop(a):
    """항목 하나를 백로그에서 뺀다(사장님 삭제 지시). 원장 줄은 지우지 않고 drop 기록을 더해 이력을 남긴다."""
    rows = load("req")
    item = next((r for r in rows if r["kind"] == "item" and r["id"] == a.id), None)
    if not item:
        sys.exit(f"{a.id} 항목이 없습니다")
    if any(r["kind"] == "drop" and r.get("target") == a.id for r in rows):
        sys.exit(f"{a.id}는 이미 뺀 항목입니다")
    if len(a.reason.strip()) < 8:
        sys.exit("뺀 이유(reason)를 8자 이상 쓰세요(누가 언제 무엇을 근거로 정했는지)")
    rows.append({"id": "", "kind": "drop", "date": str(today()), "area": item["area"], "target": a.id, "reason": a.reason})
    save("req", rows)
    st = req_state(item["area"])
    print(f"{a.id} 백로그에서 뺌: {a.reason} (영역 [{item['area']}] 남은 항목 {st['items']}개)")


def req_done(a):
    """항목 하나가 이미 구현·배포돼 있어 남은 일이 없다고 표시한다(근거 필수). 이력은 남기고 남은 항목 수에서 뺀다."""
    rows = load("req")
    item = next((r for r in rows if r["kind"] == "item" and r["id"] == a.id), None)
    if not item:
        sys.exit(f"{a.id} 항목이 없습니다")
    if any(r["kind"] in ("drop", "done") and r.get("target") == a.id for r in rows):
        sys.exit(f"{a.id}는 이미 뺀 항목입니다")
    if len(a.evidence.strip()) < 8:
        sys.exit("완료 근거(evidence)를 8자 이상 쓰세요(PR 번호·파일·실측)")
    rows.append({"id": "", "kind": "done", "date": str(today()), "area": item["area"], "target": a.id, "reason": a.evidence})
    save("req", rows)
    st = req_state(item["area"])
    print(f"{a.id} 완료 표시: {a.evidence} (영역 [{item['area']}] 남은 항목 {st['items']}개)")


def req_list(a):
    areas = sorted({r["area"] for r in load("req")})
    for ar in areas:
        if a.area and ar != a.area:
            continue
        st = req_state(ar)
        label = "확신 있음" if st["ready"] else ("확신 취소(새 항목)" if st["had_ready"] else "취합 중")
        print(f"[{ar}] {label}, 항목 {st['items']}개, 시작 {st['first']}")
        dropped = {r.get("target"): r for r in st["rows"] if r["kind"] in ("drop", "done")}
        for r in st["rows"]:
            if r["kind"] == "item" and r["id"] in dropped:
                d = dropped[r['id']]
                print(f"   {r['id']} [{'완료' if d['kind'] == 'done' else '뺌'} {d['date']}: {d['reason'][:50]}]")
            elif r["kind"] == "item":
                print(f"   {r['id']} ({r['source']}) {r['text'][:80]}")
            elif r["kind"] == "ready":
                print(f"   - 확신 {r['date']}: {r['note'][:80]}")
            elif r["kind"] == "sent":
                print(f"   - 전달 {r['date']}: {r['to']} {r['ref'][:60]}")


def req_check(a):
    st = req_state(a.area)
    if st["ready"]:
        print("확신 있음")
        return
    sys.exit(f"영역 [{a.area}]은 아직 전달할 수 없습니다(" + ("항목 없음" if not st["items"] else "확신 기록 없음 또는 새 항목으로 취소됨") + ")")


# ---------------- ut (카빗 유저빌리티테스트) ----------------
def ut_add(a):
    rows = load("ut")
    r = {"id": next_id(rows, "UT"), "date": str(today()), "path": a.path, "tester": a.tester, "task": a.task,
         "retest_of": a.retest or "", "result": "", "blocks": "", "actions": None, "seconds": None, "reqs": [], "result_date": ""}
    rows.append(r)
    save("ut", rows)
    print(f"{r['id']} 카빗 UT 기록: 경로 [{a.path}] 테스터 {a.tester}{' (재측정: ' + a.retest + ')' if a.retest else ''}")


def ut_result(a):
    rows = load("ut")
    r = find(rows, a.id)
    r.update({"result": a.text, "blocks": a.blocks or "", "actions": a.actions, "seconds": a.seconds,
              "reqs": [x.strip() for x in (a.reqs or "").split(",") if x.strip()], "result_date": str(today())})
    save("ut", rows)
    print(f"{r['id']} 결과 기록(반영 요구 {', '.join(r['reqs']) or '없음'})")


def ut_list(a):
    for r in load("ut"):
        nums = f" 행동 {r['actions']}·{r['seconds']}초" if r.get("actions") is not None else ""
        print(f"{r['id']} {r['date']} [{r['path']}] {r['tester']}{' 재측정 ' + r['retest_of'] if r.get('retest_of') else ''}: "
              f"{(r['result'] or '결과 대기')[:60]}{nums} 반영 {','.join(r.get('reqs') or []) or '-'}")


def ut_due():
    rows = load("ut")
    retested = {r["retest_of"] for r in rows if r.get("retest_of")}
    out = []
    for r in rows:
        if not r["result"] and days_since(r["date"]) >= UT_RESULT_DAYS:
            out.append(f"{r['id']} 결과 없이 {days_since(r['date'])}일: [{r['path']}] {r['tester']}")
        elif r["result"] and r.get("reqs") and r["id"] not in retested and days_since(r["result_date"]) >= 7:
            out.append(f"{r['id']} 개선 요구 {','.join(r['reqs'])} 반영 뒤 재측정 안 함(배포됐으면 ut add --retest {r['id']})")
    return out


# ---------------- lead (사전체험 신청) ----------------
def fetch_invite_requests():
    """hello@ 수신함에서 외부 사전체험 신청만. 읽기 실패면 None(없음과 구분)."""
    import urllib.request
    env = {}
    try:
        with open(MAIL_ENV, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env[k] = v.strip().strip('"')
        req = urllib.request.Request(env["MAIL_URL"].rstrip("/") + "/mail",
                                     headers={"Authorization": "Bearer " + env["MAIL_READ_KEY"], "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    items = data if isinstance(data, list) else data.get("mails") or data.get("items") or []
    out = []
    for m in items:
        if "[초대 요청]" not in str(m.get("subject") or ""):
            continue
        found = re.search(r"초대 요청 이메일:\s*(\S+)", str(m.get("preview") or ""))
        email = found.group(1) if found else ""
        if not email or any(d in email for d in INTERNAL_DOMAINS):
            continue
        out.append({"mail_id": str(m.get("id")), "email": email, "at": str(m.get("received_at") or "")})
    return out


def open_leads():
    reqs = fetch_invite_requests()
    if reqs is None:
        return None
    done = {r["mail_id"] for r in load("lead")}
    return [r for r in reqs if r["mail_id"] not in done]


def lead_list(a):
    reqs = fetch_invite_requests()
    if reqs is None:
        sys.exit("수신함을 읽지 못했습니다(키 파일·네트워크 확인)")
    st = {r["mail_id"]: r for r in load("lead")}
    for r in reqs:
        s = st.get(r["mail_id"])
        print(f"{r['at'][:16]} {r['email']} 메일 {r['mail_id']} 상태: {(s['state'] + ' ' + s.get('note', '')) if s else '미처리'}")


def lead_mark(a):
    rows = [r for r in load("lead") if r["mail_id"] != a.mail_id]
    rows.append({"mail_id": a.mail_id, "state": a.state, "note": a.note, "date": str(today())})
    save("lead", rows)
    print(f"신청 {a.mail_id} → {a.state}")


def lead_alert(a):
    """훅용: 미처리 신청이 있을 때만 한 줄(주소는 쓰지 않고 개수만)."""
    ol = open_leads()
    if ol:
        print(f"🚨 사전체험 신청 미처리 {len(ol)}건(고객 획득 최우선, 하던 일보다 먼저): `python scripts/ops/jitu_po.py lead list`로 보고 "
              "사장님께 신청자와 초대 추천을 올린 뒤 `lead mark <메일 id> asked|invited|dropped --note ...`")


# ---------------- due ----------------
def due_items():
    out = {"lead": [], "gap": [], "kpi": [], "feedback": [], "predict": [], "ask": [], "req": [], "notice": [], "ut": ut_due()}
    ol = open_leads()
    if ol:
        out["lead"].append(f"미처리 {len(ol)}건(가장 오래된 것 {min(r['at'] for r in ol)[:16]}), `jitu_po.py lead list`")
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
        if kpis[-1].get("customers") is None:
            out["kpi"].append("지투 KPI인 고객수가 마지막 측정에 기록되지 않았다(--customers)")
    for r in load("feedback"):
        age = days_since(r["updated"])
        if r["state"] == "new" and age >= FEEDBACK_TRIAGE_DAYS:
            out["feedback"].append(f"{r['id']} 분류 안 함 {age}일: {r['text'][:50]}")
        elif r["state"] in ("triaged", "backlog") and days_since(r["date"]) >= FEEDBACK_REPLY_DAYS and not r["reply"]:
            out["feedback"].append(f"{r['id']} 회신 안 함 {days_since(r['date'])}일: {r['text'][:50]}")
        if r.get("shipped") and not r.get("notified"):
            out["notice"].append(f"{r['id']} 배포 {r['shipped']}, 안내 안 함({r.get('customer') or '별칭 없음'}) PR {', '.join(pr_label(x) for x in r.get('prs') or []) or '-'}: {r['text'][:50]} (fb notice-draft {r['id']})")
    for r in load("ask"):
        if not r["answer"]:
            age = days_since(r["date"])
            overdue = bool(r["due"]) and r["due"] < str(today())
            if age >= ASK_STATUS_DAYS or overdue:
                out["ask"].append(f"{r['id']} 답 대기 {age}일{'(마감 지남)' if overdue else ''}: {r['text'][:50]} (다시 묻지 말고 한 줄 상태만, 기본값: {r['default'][:30]})")
    for ar in sorted({r["area"] for r in load("req")}):
        st = req_state(ar)
        if not st["ready"] and st["items"] and days_since(st["first"]) >= REQ_COLLECT_DAYS:
            out["req"].append(f"영역 [{ar}] 취합 {days_since(st['first'])}일째, 항목 {st['items']}개, 확신 미기록(빠진 것 점검 뒤 req ready, 서두르지 말고 완벽히)")
    for r in load("predict"):
        if not r["verdict"] and r["check_on"] <= str(today()):
            out["predict"].append(f"{r['id']} 점검일 {r['check_on']} 지남: {r['change'][:50]}")
    return out


def due(a):
    d = due_items()
    n = sum(len(v) for v in d.values())
    if a.quiet and n == 0:
        return
    names = {"gap": "검사 공백(보강 4)", "kpi": "지표 측정(보강 2)", "feedback": "고객 신호(보강 3)", "predict": "예측 점검(보강 1)", "ask": "결정 요청(답 대기)", "req": "요구사항 취합 중",
             "notice": "개선 반영 안내(배포됐는데 안내 안 함)", "lead": "🚨 사전체험 신청(고객 획득 최우선)", "ut": "카빗 UT"}
    print(f"🔁 지투 루프 점검: 기한 지난 것 {n}건")
    for k in ("lead", "ut", "gap", "kpi", "feedback", "predict", "ask", "req", "notice"):
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
    for name in ("customers", "new-customers", "lost-customers"):  # 지투 KPI: 고객수(외부 고객 회사 수), 이번 주 신규, 이번 주 이탈
        x.add_argument(f"--{name}", type=int, default=None)
    x.set_defaults(fn=kpi_add)
    x = k.add_parser("list"); x.add_argument("--last", type=int, default=8); x.set_defaults(fn=kpi_list)

    f = sub.add_parser("feedback", aliases=["fb"]).add_subparsers(dest="sub", required=True)
    x = f.add_parser("add"); x.add_argument("--source", required=True, help="feedback도구|찾지못한검색|사용기록|면담")
    x.add_argument("--who", default=""); x.add_argument("--text", required=True)
    x.add_argument("--customer", default="", help="별칭만: 고객<숫자>|내부|신규가입자 (실명 금지)"); x.set_defaults(fn=fb_add)
    x = f.add_parser("ship", help="개선이 배포되면 PR·배포일·안내 내용을 채운다")
    x.add_argument("id"); x.add_argument("--pr", action="append", required=True, help="PR 번호 123 또는 저장소#번호 carvit.ai#37(별칭 site·carvit.ai·saegim, 여러 번 가능)")
    x.add_argument("--shipped", required=True, help="배포일 YYYY-MM-DD"); x.add_argument("--notice-what", required=True, dest="notice_what", help="바뀐 것 한 줄")
    x.add_argument("--notice-before", default="", dest="notice_before", help="바뀌기 전 화면 링크")
    x.add_argument("--notice-after", default="", dest="notice_after", help="바뀐 뒤 화면 링크")
    x.add_argument("--notice-next", required=True, dest="notice_next", help="고객이 다음에 해 볼 일 한 줄")
    x.add_argument("--replace-pr", action="store_true", dest="replace_pr", help="기존 prs를 이번에 넣은 --pr 값으로 통째로 바꾼다")
    x.add_argument("--customer", default="", help="별칭을 이때 채워도 된다"); x.set_defaults(fn=fb_ship)
    x = f.add_parser("notified", help="안내 메일을 보낸 날을 기록한다"); x.add_argument("id"); x.add_argument("--date", required=True)
    x.set_defaults(fn=fb_notified)
    x = f.add_parser("notice-draft", help="고정 틀로 안내 메일 초안을 화면에 출력만 한다(발송 없음)"); x.add_argument("id")
    x.add_argument("--quote", default="", help="첫 줄에 인용할 고객 말씀(비우면 text 칸)"); x.set_defaults(fn=fb_notice_draft)
    x = f.add_parser("triage"); x.add_argument("id"); x.add_argument("--kind", required=True, help="버그|UX|요청|내용공백|칭찬|잡음")
    x.add_argument("--state", choices=FB_STATES[1:], default="triaged"); x.add_argument("--action", default="")
    x.add_argument("--reply", default=""); x.set_defaults(fn=fb_triage)
    x = f.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=fb_list)

    r = sub.add_parser("predict").add_subparsers(dest="sub", required=True)
    x = r.add_parser("add"); x.add_argument("--change", required=True); x.add_argument("--expect", required=True)
    x.add_argument("--metric", required=True); x.add_argument("--check-on", required=True, dest="check_on")
    x.add_argument("--kpi", default="", help="지투 KPI(고객수)와의 연결 한 줄. 정말 무관하면 '해당없음:이유'"); x.set_defaults(fn=pr_add)
    x = r.add_parser("check"); x.add_argument("id"); x.add_argument("--actual", required=True)
    x.add_argument("--verdict", required=True, choices=["적중", "빗나감", "판정불가"]); x.add_argument("--lesson", default="")
    x.set_defaults(fn=pr_check)
    x = r.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=pr_list)

    q = sub.add_parser("ask").add_subparsers(dest="sub", required=True)
    x = q.add_parser("add"); x.add_argument("--text", required=True, help="무엇을 정해 달라는지 한 줄")
    x.add_argument("--rec", required=True, help="추천과 한 줄 이유"); x.add_argument("--default", required=True, help="답이 없을 때 어떻게 되는지(기본값)")
    x.add_argument("--due", default="", help="마감 YYYY-MM-DD(선택)"); x.add_argument("--created", default="")
    x.add_argument("--kpi", default="", help="지투 KPI(고객수)와의 연결 한 줄. 정말 무관하면 '해당없음:이유'"); x.set_defaults(fn=ask_add)
    x = q.add_parser("find"); x.add_argument("words", nargs="+"); x.set_defaults(fn=ask_find)
    x = q.add_parser("answer"); x.add_argument("id"); x.add_argument("--answer", required=True); x.set_defaults(fn=ask_answer)
    x = q.add_parser("list"); x.add_argument("--open", action="store_true"); x.set_defaults(fn=ask_list)

    rq = sub.add_parser("req").add_subparsers(dest="sub", required=True)
    x = rq.add_parser("add"); x.add_argument("--area", required=True); x.add_argument("--text", required=True)
    x.add_argument("--source", default="사장님"); x.set_defaults(fn=req_add)
    x = rq.add_parser("ready"); x.add_argument("area"); x.add_argument("--note", required=True, help="빠진 것 점검 결과(선행·충돌·고객/DB 영향·확인 방법) 20자 이상")
    x.set_defaults(fn=req_ready)
    x = rq.add_parser("sent"); x.add_argument("area"); x.add_argument("--to", default="노트"); x.add_argument("--ref", default=""); x.set_defaults(fn=req_sent)
    x = rq.add_parser("done"); x.add_argument("id"); x.add_argument("--evidence", required=True); x.set_defaults(fn=req_done)
    x = rq.add_parser("drop"); x.add_argument("id"); x.add_argument("--reason", required=True); x.set_defaults(fn=req_drop)
    x = rq.add_parser("list"); x.add_argument("--area", default=""); x.set_defaults(fn=req_list)
    x = rq.add_parser("check-send"); x.add_argument("area"); x.set_defaults(fn=req_check)

    x = sub.add_parser("due"); x.add_argument("--quiet", action="store_true"); x.set_defaults(fn=due)

    u = sub.add_parser("ut").add_subparsers(dest="sub", required=True)
    x = u.add_parser("add"); x.add_argument("--path", required=True, help="체험 경로(예: 초대메일→가입→첫 DM)")
    x.add_argument("--tester", required=True, help="테스터 세션 이름(맥락 없는 새 세션)"); x.add_argument("--task", required=True)
    x.add_argument("--retest", default="", help="재측정이면 원래 UT 번호"); x.set_defaults(fn=ut_add)
    x = u.add_parser("result"); x.add_argument("id"); x.add_argument("--text", required=True)
    x.add_argument("--blocks", default=""); x.add_argument("--actions", type=int, default=None); x.add_argument("--seconds", type=int, default=None)
    x.add_argument("--reqs", default="", help="반영한 요구 번호(쉼표)"); x.set_defaults(fn=ut_result)
    x = u.add_parser("list"); x.set_defaults(fn=ut_list)

    ld = sub.add_parser("lead").add_subparsers(dest="sub", required=True)
    x = ld.add_parser("list"); x.set_defaults(fn=lead_list)
    x = ld.add_parser("mark"); x.add_argument("mail_id"); x.add_argument("state", choices=["asked", "invited", "dropped"])
    x.add_argument("--note", default=""); x.set_defaults(fn=lead_mark)
    x = ld.add_parser("alert"); x.set_defaults(fn=lead_alert)
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
