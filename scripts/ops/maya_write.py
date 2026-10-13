#!/usr/bin/env python3
"""마야 글쓰기 고도화 루프의 도구 한 벌(2026-10-06 사장님 지시: "글로벌 탑급 라이터 되기").

왜: 문서에만 있는 규칙은 세션이 바뀌면 빠진다(CLAUDE#4e7b). 글 종류 판별, 기계가 셀 수 있는 규칙 검사,
독립 평가 기록, 주간 점검을 코드로 두어 같은 루프가 매번 돈다. 정본 데이터는 maya_write_rubrics.json.

하위 명령
  route "<요청 문장>"            글 종류 판별과 작업 순서(가이드, 작성 도구, 검사, 독립 평가, 컨펌)를 출력
  lint  <파일|--text 문자열>      기계 검사(증명 불가 형용사, 문체 혼용, 제품 이름·회사 이름·용어, 길이)
  card  <종류> <파일>             독립 평가용 채점 카드(마크다운)를 만든다(평가자는 제미나이 블라인드 호출, 덱스·비티는 글 평가에서 제외, 사장님 2026-10-12)
  log   add ...                  평가 기록 한 건을 쌓는다(점수 검증, 독립 평가 여부 자동 표시)
  exp add|snap|report            링크드인 A/B 실험 등록·12h/24h 측정·사전 약속 규칙 판정
  routecase "<발화>" <종류|none>  실제 발화와 정답을 쌓는다(고치기 전에 먼저 맞는지 보고 기록 = 보류 시험)
  report [--days N]              종류별 평균, 가장 낮은 항목, 린트 통과율, 다음 개선 후보 3개
  selftest                       라우터·린트 시험 묶음을 돌려 통과 여부를 출력

종료 코드: lint는 0 통과, 1 경고만, 2 오류. 그 밖은 0 정상, 2 입력 오류.
평가 기록 위치: C:/work/_ops/maya_writing/eval_log.jsonl (환경변수 MAYA_WRITE_LOG로 바꿀 수 있음).
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
RUBRICS_PATH = HERE / "maya_write_rubrics.json"
LOG_PATH = Path(os.environ.get("MAYA_WRITE_LOG", "C:/work/_ops/maya_writing/eval_log.jsonl"))
KST = timezone(timedelta(hours=9))


def load_rubrics():
    return json.loads(RUBRICS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- route
def route(request, rb=None):
    """키워드 점수로 글 종류를 정한다. 긴 문구(공백 포함)는 2점, 한 단어는 1점. 사람이 읽을 근거를 같이 돌려준다."""
    rb = rb or load_rubrics()
    scores, hits = {}, {}
    low = request.lower()
    for t, d in rb["types"].items():
        s, h = 0, []
        for kw in d["route_keywords"]:
            if kw.lower() in low:
                w = 2 if (" " in kw or len(kw) >= 4) else 1
                s += w
                h.append(kw)
        scores[t], hits[t] = s, h
    order = sorted(scores, key=lambda k: (-scores[k], k))
    top, second = order[0], order[1]
    res = {"request": request, "scores": scores, "hits": hits}
    if scores[top] == 0:
        res.update(type=None, status="ask", reason="어느 종류의 글인지 단서가 없다. 독자와 쓰이는 곳(화면·광고·문서·이름)을 한 줄 물어본다.")
    elif scores[top] == scores[second]:
        res.update(type=None, status="ask", candidates=[top, second],
                   reason=f"{rb['types'][top]['name']}와 {rb['types'][second]['name']}가 같은 점수다. 쓰이는 곳을 한 줄 물어본다.")
    else:
        res.update(type=top, status="ok", runner_up=second if scores[second] else None,
                   reason=f"{rb['types'][top]['name']} 단서: {', '.join(hits[top])}")
    if res["type"]:
        res["playbook"] = rb["types"][res["type"]]["playbook"]
        res["rubric"] = ([] if rb["types"][res["type"]].get("no_common") else [i["id"] for i in rb["common"]]) + [i["id"] for i in rb["types"][res["type"]]["rubric"]]
    return res


# ---------------------------------------------------------------- lint
POLITE_END = re.compile(r"(니다|세요|예요|에요|어요|아요|해요|죠|까요|네요|습니다)$")
PLAIN_END = re.compile(r"[가-힣]다$")
QUOTED = re.compile(r"[“\"「『][^”\"」』\n]{0,200}[”\"」』]")


def sentences(text):
    text = QUOTED.sub(" ", text)
    out = []
    for line in text.splitlines():
        for s in re.split(r"(?<=[.!?])\s+|(?<=[.!?])$", line.strip()):
            s = s.strip().rstrip(".!?").strip()
            if len(s) >= 8:
                out.append(s)
    return out


CLAIM_WORD = re.compile(r"(연구|조사|논문|통계)")
CLAIM_NUM = re.compile(r"(\d|에 따르면|결과)")
SOURCE_MARK = re.compile(r"(출처|https?://|\(\s*\d{4}|\[\d+\]|참고|Science Advances|Nature|학술지|저널|Journal)")


def unsourced_claims(text):
    """연구·조사 같은 말로 근거를 대면서 같은 문장에 출처 표시가 없는 문장(독립 평가 10/6 카피 '신뢰증거' 2점에서 나온 규칙)."""
    out = []
    for s in sentences(text):
        if CLAIM_WORD.search(s) and CLAIM_NUM.search(s) and not SOURCE_MARK.search(s) and "테크리포트" not in s and "버전" not in s:
            out.append(s[:60])
    return out


def lint(text, context="generic", title=None, sub=None, rb=None, body=False):
    """기계가 셀 수 있는 규칙만 검사한다. 판단이 필요한 품질은 독립 평가자가 한다."""
    rb = rb or load_rubrics()
    cfg = rb["lint"]
    issues = []  # (level, rule, message)

    def add(level, rule, msg):
        issues.append({"level": level, "rule": rule, "message": msg})

    scopes = [("title", title), ("sub", sub)] if (title or sub) else []
    for scope, s in scopes:
        if not s:
            continue
        for w in cfg["hype_words"]:
            if w in s:
                add("error", "증명불가어", f"{scope}에 '{w}': 근거로 보일 수 없는 형용사·유행어(가이드 1.47)")
    for w in cfg["hype_words"]:
        n = text.count(w)
        if n:
            add("warn", "증명불가어", f"본문에 '{w}' {n}회: 증명할 수 있는 구체적 사실로 바꿀 수 있는지 본다")
    if title and len(title) > cfg["title_max"]:
        add("warn", "길이", f"제목 {len(title)}자: 20자 안팎(가이드 1.47)")
    if sub and len(sub) > cfg["sub_max"]:
        add("warn", "길이", f"부제 {len(sub)}자: 40자 안팎(가이드 1.47)")

    if context == "carvit":
        for w, why in cfg["forbidden_in_carvit"].items():
            n = (title or "").count(w) + (sub or "").count(w) + text.count(w)
            if n:
                add("error", "이름·노출", f"'{w}' {n}회: {why}")
        for w, why in cfg["term_warn_in_carvit"].items():
            n = text.count(w)
            if n:
                add("warn", "용어", f"'{w}' {n}회: {why}")

    if body:
        # 홈페이지 글 본문 분량(WRITING_GUIDE 5-2절: 목표 1,000자 안팎, 상한 1,500자, 공백 포함). 2026-10-13 사장님 "글이 너무 짧은데" 재발 방지:
        # 초안이 716자·691자로 컨펌까지 올라간 일. 상한만 있고 하한이 없던 것이 원인이었다.
        bc = cfg["body_chars"]
        n = len(text.strip())
        if n < bc["min"]:
            add("warn", "분량부족", f"본문 {n}자: 목표 {bc['target']}자 안팎(하한 {bc['min']}자, WRITING_GUIDE 5-2절). 재료(사실 목록)가 모자란 것이므로 늘려 쓰지 말고 다이얼로그·원문 대조로 재료부터 더한다")
        elif n > bc["max"]:
            add("error", "분량초과", f"본문 {n}자: 상한 {bc['max']}자(WRITING_GUIDE 5-2절). 주제에서 벗어난 문단부터 뺀다")

    uc = unsourced_claims(text)
    if uc:
        add("warn", "출처없는근거", f"근거로 든 문장 {len(uc)}개에 출처 표시가 없다(링크·출처·연도 중 하나를 같은 문장에): " + " / ".join(uc[:2]))

    pol, pla, pla_ex = 0, 0, []
    for s in sentences(text):
        if POLITE_END.search(s):
            pol += 1
        elif PLAIN_END.search(s):
            pla += 1
            if len(pla_ex) < 2:
                pla_ex.append(s[-40:])
    if pol and pla:
        add("warn", "문체혼용", f"합니다체 {pol}문장과 평어체 {pla}문장이 섞임. 평어체 예: {' / '.join(pla_ex)}")

    # 시점 표현이 글 안에서 되풀이되면 독자는 사건이 언제 몇 번 일어났는지 헷갈린다(2026-10-13 사장님 지적: A형 글에 '얼마 전'이 흩어져 시점이 뒤죽박죽).
    # 같은 표현의 반복과, 서로 다른 시점 표현이 3개 이상 섞인 것을 경고한다.
    anchors = re.findall(r"얼마 전|지난 (?:주|달|해|금요일|월요일|화요일|수요일|목요일|토요일|일요일)|최근|이번 주|이번 달|며칠 전|어제|오늘 아침|작년|올해 초", text)
    rep = sorted({a for a in anchors if anchors.count(a) >= 2})
    if rep:
        add("warn", "시점반복", "시점 표현이 되풀이된다: " + ", ".join(f"'{a}' {anchors.count(a)}회" for a in rep) + ". 시점은 한 곳에서 한 번 밝히고 뒤는 '그날'·'그 뒤'로 잇는다")
    elif len(set(anchors)) >= 3:
        add("warn", "시점혼재", "서로 다른 시점 표현이 " + str(len(set(anchors))) + "개: " + ", ".join(sorted(set(anchors))) + ". 사건 순서가 헷갈리지 않는지 처음부터 소리 내어 읽어 본다")
    level = 2 if any(i["level"] == "error" for i in issues) else (1 if issues else 0)
    return {"status": ["pass", "warn", "error"][level], "code": level, "issues": issues,
            "polite": pol, "plain": pla, "chars": len(text)}


def numbers_in(text):
    return sorted(set(re.findall(r"\d[\d,.]*\s?(?:%|건|회|개|명|px|초|분|시간|자|원)?", text)))[:40]


# ---------------------------------------------------------------- card
def make_card(kind, text, rb=None):
    rb = rb or load_rubrics()
    t = rb["types"][kind]
    items = ([] if t.get("no_common") else rb["common"]) + t["rubric"]
    lines = [f"# 글 평가 카드: {t['name']}", "",
             "너는 글 맥락을 모르는 독립 평가자다. 아래 글을 아래 항목 각각에 1~5점으로 채점한다. 쓴 사람을 봐주지 않는다.",
             "근거 없이 높은 점수를 주지 않는다. 해당 없는 항목은 3점으로 두고 이유에 '해당 없음'이라고 쓴다.", "",
             "## 점수 기준"]
    lines += [f"- {k}점: {v}" for k, v in rb["scale"].items()]
    lines += ["", "## 항목"]
    lines += [f"- {i['id']} ({i['name']}): {i['desc']}" for i in items]
    lines += ["", "## 출력 형식(이것만 출력, JSON 한 개)",
              '{"scores": {"항목id": 점수, ...}, "reasons": {"항목id": "한 줄 이유(본문 인용)", ...}, "top_fix": "가장 먼저 고칠 한 가지"}',
              "", "## 글", "```text", text.strip(), "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- log
def rubric_ids(kind, rb):
    base = [] if rb["types"][kind].get("no_common") else [i["id"] for i in rb["common"]]
    return base + [i["id"] for i in rb["types"][kind]["rubric"]]


def log_add(kind, artifact, scores, evaluator, entry_kind="production", notes="", lint_summary=None, rb=None, path=None):
    rb = rb or load_rubrics()
    path = Path(path or LOG_PATH)
    if kind not in rb["types"]:
        raise ValueError(f"알 수 없는 종류: {kind}")
    valid = set(rubric_ids(kind, rb))
    bad = [k for k in scores if k not in valid]
    if bad:
        raise ValueError(f"이 종류에 없는 항목: {bad}. 가능한 항목: {sorted(valid)}")
    for k, v in scores.items():
        if not isinstance(v, int) or not 1 <= v <= 5:
            raise ValueError(f"점수는 1~5 정수: {k}={v}")
    rec = {"ts": datetime.now(KST).isoformat(timespec="seconds"), "type": kind, "kind": entry_kind,
           "artifact": artifact, "evaluator": evaluator, "independent": evaluator not in ("마야", "self"),
           "scores": scores, "notes": notes, "lint": lint_summary, "rubric_version": rb["version"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_log(path=None):
    path = Path(path or LOG_PATH)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# ---------------------------------------------------------------- report
def report(days=None, rb=None, path=None):
    rb = rb or load_rubrics()
    recs = read_log(path)
    if days:
        cut = datetime.now(KST) - timedelta(days=days)
        recs = [r for r in recs if datetime.fromisoformat(r["ts"]) >= cut]
    lines = [f"# 마야 글쓰기 주간 점검 (기록 {len(recs)}건, 기준 버전 {rb['version']})", ""]
    if not recs:
        lines += ["기록이 없다. 첫 기준선부터 쌓는다: maya_write.py card → 독립 평가 → log add."]
        return "\n".join(lines), []
    by_type = defaultdict(list)
    for r in recs:
        by_type[r["type"]].append(r)
    cands = []
    for t, d in rb["types"].items():
        rs = by_type.get(t, [])
        if not rs:
            lines.append(f"- {d['name']}: 기록 없음(기준선 미측정)")
            cands.append((0.0, f"{d['name']} 기준선 측정(기록 0건)"))
            continue
        indep = [r for r in rs if r.get("independent")]
        lines.append(f"- {d['name']}: {len(rs)}건(독립 평가 {len(indep)}건, 기준선 {sum(1 for r in rs if r['kind']=='baseline')}건)")
        agg = defaultdict(list)
        for r in indep:
            for k, v in r["scores"].items():
                agg[k].append(v)
        if not agg:
            cands.append((0.5, f"{d['name']} 독립 평가 점수 없음(자기 평가만 있음)"))
            continue
        means = {k: sum(v) / len(v) for k, v in agg.items()}
        low = sorted(means.items(), key=lambda kv: kv[1])[:2]
        lines.append("    평균 낮은 항목: " + ", ".join(f"{k} {m:.1f}({len(agg[k])}건)" for k, m in low))
        for k, m in low:
            cands.append((m, f"{d['name']} '{k}' 평균 {m:.1f}"))
    lint_recs = [r["lint"] for r in recs if r.get("lint")]
    if lint_recs:
        ok = sum(1 for l in lint_recs if l.get("status") == "pass")
        lines.append(f"- 린트: {len(lint_recs)}건 중 통과 {ok}건({ok*100//len(lint_recs)}%), 오류 {sum(1 for l in lint_recs if l.get('status')=='error')}건")
    selfonly = sum(1 for r in recs if not r.get("independent"))
    if selfonly:
        lines.append(f"- 주의: 자기 평가 {selfonly}건은 평균에서 뺐다(독립 평가만 센다)")
    cands.sort()
    top = cands[:3]
    lines += ["", "## 다음 개선 후보(점수가 낮은 순, 기록 없는 영역 우선)"] + [f"{i+1}. {t}" for i, (_, t) in enumerate(top)]
    return "\n".join(lines), [t for _, t in top]


# ---------------------------------------------------------------- exp (링크드인 A/B 실험, 2026-10-06)
EXP_PATH = HERE.parent.parent / "assets" / "data" / "linkedin_experiment.json"
EXP_RULE = {
    "min_per_group": 4,
    "likes_ratio": 1.5,
    "impressions_floor": 0.8,
    "text": "각 그룹 4건 이상이 모이면 12시간 시점 좋아요 중앙값을 비교한다. A(직접 해 본 경험담) 중앙값이 B(일반 고민 칼럼)의 1.5배 이상이고 A의 노출 중앙값이 B의 0.8배 이상이면 'A 우위', B가 A의 1.5배 이상이면 'B 우위', 그 밖은 '차이 불분명'. 4건씩이라 결과는 방향으로만 쓰고 다음 4주에 같은 기준으로 반복해 확인한다.",
}


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return None if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


def exp_load(path=None):
    path = Path(path or EXP_PATH)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"rule": EXP_RULE, "posts": []}


def exp_save(d, path=None):
    path = Path(path or EXP_PATH)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def exp_add(post, group, title, planned, note="", path=None):
    if group not in ("A", "B"):
        raise ValueError("그룹은 A 또는 B")
    d = exp_load(path)
    if any(p["post"] == post for p in d["posts"]):
        raise ValueError(f"이미 있는 글: {post}")
    d["posts"].append({"post": post, "group": group, "title": title, "planned": planned, "note": note, "snaps": {}})
    exp_save(d, path)
    return d


def exp_snap(post, when, likes, impressions, comments=None, path=None):
    if when not in ("12h", "24h"):
        raise ValueError("시점은 12h 또는 24h")
    d = exp_load(path)
    for p in d["posts"]:
        if p["post"] == post:
            p["snaps"][when] = {"likes": likes, "impressions": impressions, "comments": comments,
                                "at": datetime.now(KST).isoformat(timespec="minutes")}
            exp_save(d, path)
            return p
    raise ValueError(f"등록되지 않은 글: {post}")


def exp_verdict(posts, rule=None):
    """사전 약속한 규칙으로만 판정한다(결과를 보고 기준을 바꾸지 않는다)."""
    rule = rule or EXP_RULE
    g = {"A": [], "B": []}
    for p in posts:
        s = p.get("snaps", {}).get("12h")
        if s and s.get("likes") is not None and s.get("impressions") is not None:
            g[p["group"]].append((s["likes"], s["impressions"]))
    nA, nB = len(g["A"]), len(g["B"])
    res = {"nA": nA, "nB": nB}
    if nA < rule["min_per_group"] or nB < rule["min_per_group"]:
        res["verdict"] = f"표본 부족(A {nA}건, B {nB}건, 각 {rule['min_per_group']}건 필요)"
        return res
    lA, lB = _median([x[0] for x in g["A"]]), _median([x[0] for x in g["B"]])
    iA, iB = _median([x[1] for x in g["A"]]), _median([x[1] for x in g["B"]])
    res.update(likes_A=lA, likes_B=lB, imp_A=iA, imp_B=iB)
    if lB and lA >= rule["likes_ratio"] * lB and iA >= rule["impressions_floor"] * iB:
        res["verdict"] = "A 우위(방향)"
    elif lA and lB >= rule["likes_ratio"] * lA and iB >= rule["impressions_floor"] * iA:
        res["verdict"] = "B 우위(방향)"
    else:
        res["verdict"] = "차이 불분명"
    return res


def exp_report(path=None):
    d = exp_load(path)
    lines = ["# 링크드인 A/B 실험 점검", "", "사전 약속: " + d.get("rule", EXP_RULE)["text"], ""]
    for p in sorted(d["posts"], key=lambda x: x["planned"]):
        s12, s24 = p["snaps"].get("12h"), p["snaps"].get("24h")
        f = lambda s: "미측정" if not s else ("측정 못함(사유 기록)" if s.get("missed") else f"좋아요 {s['likes']}·노출 {s['impressions']}")
        lines.append(f"- [{p['group']}] {p['planned']} {p['post']} {p['title'][:22]} | 12h {f(s12)} | 24h {f(s24)}")
    v = exp_verdict(d["posts"], d.get("rule"))
    lines += ["", f"판정: {v['verdict']}"]
    if "likes_A" in v:
        lines.append(f"  12h 좋아요 중앙값 A {v['likes_A']} / B {v['likes_B']}, 노출 중앙값 A {v['imp_A']} / B {v['imp_B']}")
    return "\n".join(lines)


EXP_CASES = [
    ("표본 부족", [{"group": "A", "snaps": {"12h": {"likes": 20, "impressions": 900}}}] * 3 + [{"group": "B", "snaps": {"12h": {"likes": 5, "impressions": 800}}}] * 4, "표본 부족"),
    ("A 우위", [{"group": "A", "snaps": {"12h": {"likes": 20, "impressions": 900}}}] * 4 + [{"group": "B", "snaps": {"12h": {"likes": 10, "impressions": 900}}}] * 4, "A 우위"),
    ("B 우위", [{"group": "A", "snaps": {"12h": {"likes": 5, "impressions": 900}}}] * 4 + [{"group": "B", "snaps": {"12h": {"likes": 12, "impressions": 900}}}] * 4, "B 우위"),
    ("차이 불분명(1.5배 미만)", [{"group": "A", "snaps": {"12h": {"likes": 12, "impressions": 900}}}] * 4 + [{"group": "B", "snaps": {"12h": {"likes": 10, "impressions": 900}}}] * 4, "차이 불분명"),
    ("노출이 너무 작으면 A 우위가 아님", [{"group": "A", "snaps": {"12h": {"likes": 20, "impressions": 300}}}] * 4 + [{"group": "B", "snaps": {"12h": {"likes": 10, "impressions": 900}}}] * 4, "차이 불분명"),
]


# ---------------------------------------------------------------- draft (오케스트레이션: 마야는 쓰지 않고 지시와 판정만)
import subprocess
import concurrent.futures as _cf

STRATEGIES = {
    "scene": "첫 문장은 글쓴이가 한 일의 장면(사실 1번)으로 시작한다. 구조: 장면, 처방, 우리 팀 링크 실패, 평준화 이유와 연구, 마무리.",
    "fail": "첫 문장은 우리 팀이 AI가 준 링크를 열어 본 실패(사실 5번)로 시작한다. 구조: 실패, 그래서 코칭 현장에서 한 처방(장면), 평준화 이유와 연구, 마무리.",
    "order": "첫 문장은 글쓴이가 코칭 현장에서 한 말(사실 1번의 대사)을 그대로 인용하며 시작한다. 구조: 대사, 처방(질문 예), 평준화 이유, 우리 팀 링크 실패로 반전, 마무리.",
}
_TOKEN = re.compile(r"[0-9]+[0-9,.]*%?|[A-Za-z][A-Za-z-]{2,}")


# 사장님 2026-10-12: 글을 쓸 때 제미나이 3.8에게 "재미있게" 써 달라고 항상 요청한다. 재미는 사실을 늘려서가 아니라 말맛으로 만든다.
FUN = ("[재미 요청] 읽다가 피식 웃게 재미있게 써 주세요. 장면과 대사의 말맛, 자기 자신을 향한 가벼운 자조, 뜻밖의 비유로 재미를 만듭니다. "
       "단, 지시서에 없는 사실·숫자·인물·연구를 지어내서 웃기지 않고, 허세나 과장 형용사로 웃기지 않습니다. ")


def new_tokens(brief_text, out_text):
    """지시서(사실 목록)에 없던 숫자·영문 단어. 모델이 지어낸 사실을 잡는 1차 관문(완전하지 않다)."""
    known = {t.lower() for t in _TOKEN.findall(brief_text)}
    return sorted({t for t in _TOKEN.findall(out_text) if t.lower() not in known})


def _run_variant(name, instr, brief_text, outdir, model, rb):
    bc = rb["lint"]["body_chars"]
    # 분량은 지시서에 적혀 있든 말든 도구가 항상 붙인다(문서 기억에 맡기지 않는다, CLAUDE#4e7b)
    prompt = (brief_text.rstrip() + "\n\n[이 버전의 전략]\n" + instr + "\n제목은 쓰지 않는다. 본문만 쓴다.\n"
              + f"[분량] 공백 포함 {bc['target']}~{bc['target'] + 300}자로 쓴다(상한 {bc['max']}자). 사실 목록이 모자라 분량이 안 나오면 지어내지 말고 짧게 끝낸다.\n")
    pf, of = Path(outdir) / f"{name}.prompt.txt", Path(outdir) / f"{name}.md"
    pf.write_text(prompt, encoding="utf-8", newline="\n")
    script = HERE / "ask_vertex.py"
    r = subprocess.run([sys.executable, str(script), str(pf), str(of), "--who", "마야", "--model", model],
                       capture_output=True, text=True, encoding="utf-8", timeout=280,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not of.exists():
        return {"name": name, "error": (r.stderr or r.stdout)[-200:]}
    text = of.read_text(encoding="utf-8").strip()
    lr = lint(text, "home", rb=rb, body=True)
    return {"name": name, "instr": instr, "file": str(of), "chars": len(text), "lint": lr["status"],
            "issues": [i["message"][:70] for i in lr["issues"]], "new": new_tokens(brief_text, text), "text": text}


def brief_problem(brief_text, rb):
    """사실 재료가 모자란 지시서는 초안을 만들지 않는다(2026-10-13: 사실 6줄로 쓴 초안이 700자라 사장님이 '너무 짧다'고 지적).
    [사실 목록] 블록의 글자 수를 센다. 블록이 없으면 지시서 전체를 센다."""
    m = re.search(r"\[사실 목록.*?(?=\n\[문체 규칙|\Z)", brief_text, re.S)
    facts = (m.group(0) if m else brief_text)
    need = rb["lint"]["body_chars"]["brief_facts_min"]
    n = len(facts.strip())
    if n < need:
        return f"사실 목록이 {n}자로 모자랍니다(최소 {need}자). 다이얼로그·원문 대조로 재료를 먼저 더하세요(분량은 재료에서 나옵니다)"
    return None


def draft(brief_path, outdir, strategies, model="gemini-3.8-flash", rb=None, allow_thin=False):
    rb = rb or load_rubrics()
    if not allow_thin:
        bp = brief_problem(Path(brief_path).read_text(encoding="utf-8"), rb)
        if bp:
            raise SystemExit("초안 중단: " + bp + " (그래도 쓰려면 --allow-thin-brief)")
    Path(outdir).mkdir(parents=True, exist_ok=True)
    brief_text = Path(brief_path).read_text(encoding="utf-8")
    with _cf.ThreadPoolExecutor(len(strategies)) as ex:
        res = list(ex.map(lambda kv: _run_variant(kv[0], kv[1], brief_text, outdir, model, rb), strategies))
    lines = [f"[마야] 제미나이 {model} 작성 비교 ({len(res)}개 버전, 같은 사실 목록·같은 규칙, 전략만 다름)", ""]
    for r in res:
        if "error" in r:
            lines += [f"## {r['name']}: 작성 실패 ({r['error']})", ""]
            continue
        flag = ("지시서에 없던 숫자·영문: " + ", ".join(r["new"])) if r["new"] else "지시서에 없던 숫자·영문 없음"
        lines += [f"## 버전 {r['name']} ({r['chars']}자, 린트 {r['lint']}, {flag})", f"전략: {r['instr']}", "", r["text"], "", "---", ""]
    out = Path(outdir) / "compare.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return res, out


# ---------------------------------------------------------------- selftest
ROUTE_CASES = [
    ("홈 제목과 부제를 써 줘", "ux"), ("확인 창 버튼 문구 정해 줘", "ux"), ("오류 문구가 불친절하다 고쳐 줘", "ux"),
    ("테크리포트 3편 고쳐 줘", "tech"), ("README 쓰고 한계 절 넣어 줘", "tech"), ("실험 보고서 요약을 써 줘", "tech"),
    ("인스타 게시글 후킹 있게 써 줘", "copy"), ("뉴스레터 메일 제목 후보", "copy"), ("광고 슬로건 만들어 줘", "copy"),
    ("브랜드 톤앤매너 정리해 줘", "brand"), ("회사 소개 문구와 미션 써 줘", "brand"),
    ("새 서비스 이름 후보를 네이밍해 줘", "naming"), ("제품명 도메인 상표 확인하면서 이름 짓기", "naming"),
    ("글 하나 써 줘", None),
    # 2026-10-06 사장님의 실제 발화. 고치기 전 정확도 2/6, 키워드를 고친 뒤 포함(학습에 쓴 시험이라 보류 시험이 아니다).
    ("홈 타이틀과 부제를 달아야 비전문가가 봐도 이해가 되지 않을까요", "ux"),
    ("테크리포트 4편의 제목이 내용을 잘 대변하는지 내용이 좋은 테크니컬 라이팅인지 분석해주세요", "tech"),
    ("나머지 페이지도 타이틀의 맥락에 맞추고 ux라이팅 원칙에 맞춰 업데이트 해주세요", "ux"),
    ("카빗 테크니컬&UX라이팅 가이드 문서를 mcp에 업데이트 해주세요", "tech"),
    ("인스타 글 주제와 후킹 문구 후보를 뽑아 주세요", "copy"),
    ("새 서비스 이름을 지어야 하는데 후보 좀 뽑아 주세요", "naming"),
]
CASES_PATH = LOG_PATH.parent / "route_cases.jsonl"  # 앞으로 쌓이는 실제 발화(보류 시험)
LINT_CASES = [
    ("원안 제목은 걸린다", dict(text="", title="디자이너와 개발자가 일하는 방식을 혁신합니다", sub="에이전틱 UX가이드, 카빗UX MCP", context="carvit"), 2),
    ("확정 제목은 통과, 확정 부제 49자는 길이 경고(2026-10-06 실측)", dict(text="", title="디자이너와 개발자의 기준을 하나로 맞춥니다", sub="AI가 화면을 만들 때도 팀의 UX 가이드를 찾아 따르고, 쓴 기준을 기록으로 남깁니다.", context="carvit"), 1),
    ("제목과 짧은 부제는 통과한다", dict(text="", title="디자이너와 개발자의 기준을 하나로 맞춥니다", sub="AI가 화면을 만들 때도 팀의 UX 가이드를 따르고, 쓴 기준을 남깁니다.", context="carvit"), 0),
    ("문체 혼용은 경고", dict(text="이 글은 실험 결과를 정리합니다. 표본이 작았고 범위도 좁았다. 그래서 일반화하지 않습니다.", context="generic"), 1),
    ("인용 안의 평어체는 세지 않는다", dict(text="사장님은 “이건 아직 부족하다 그래서 다시 한다”고 말씀하셨습니다. 그대로 반영했습니다.", context="generic"), 0),
    ("출처 없는 연구 문장은 경고(독립 평가에서 나온 규칙)", dict(text="하루 20분이 넘게 걸린다는 연구가 있습니다. 그래서 순서를 바꿨습니다.", context="generic"), 1),
    ("출처가 같은 문장에 있으면 통과", dict(text="하루 20분이 걸린다는 연구가 있습니다(출처: 2024 업무 시간 조사). 그래서 순서를 바꿨습니다.", context="generic"), 0),
    ("학술지 이름이 같은 문장에 있으면 출처로 인정", dict(text="Science Advances에 실린 연구에서는 개인 창의성은 오르지만 집단 참신함은 줄었다고 합니다. 그래서 순서를 바꿨습니다.", context="generic"), 0),
    ("시점 표현이 되풀이되면 경고(A형 글 v7 사고, 2026-10-13)", dict(text="얼마 전 회의에서 말씀드렸습니다. 그런데 얼마 전 저희 팀도 같은 일을 겪었습니다. 그래서 순서를 바꿨습니다.", context="generic"), 1),
    ("시점 표현이 한 번이면 통과", dict(text="얼마 전 회의에서 말씀드렸습니다. 그런데 저희 팀도 같은 일을 겪었습니다. 그래서 순서를 바꿨습니다.", context="generic"), 0),
    ("본문 분량 하한 미만은 경고(716자 초안 사고, 2026-10-13)", dict(text="이 글은 실험 결과를 정리합니다. " * 30, context="home", body=True), 1),
    ("본문 분량 범위 안은 통과", dict(text="이 글은 실험 결과를 정리합니다. " * 62, context="home", body=True), 0),
    ("본문 분량 상한 초과는 오류", dict(text="이 글은 실험 결과를 정리합니다. " * 110, context="home", body=True), 2),
    ("회사 이름 노출은 오류", dict(text="Carvit은 Simplifier가 만들었습니다.", context="carvit"), 2),
    ("홈페이지 맥락에서는 회사 이름 허용", dict(text="심플리파이어는 강연과 코칭을 합니다.", context="home"), 0),
]


def selftest():
    rb = load_rubrics()
    fails = []
    ok_route = 0
    for req, exp in ROUTE_CASES:
        got = route(req, rb)["type"]
        if got == exp:
            ok_route += 1
        else:
            fails.append(f"route '{req}': 기대 {exp}, 결과 {got}")
    ok_lint = 0
    for name, kw, exp in LINT_CASES:
        got = lint(rb=rb, **kw)["code"]
        if got == exp:
            ok_lint += 1
        else:
            fails.append(f"lint {name}: 기대 {exp}, 결과 {got}")
    ok_exp = 0
    for name, posts, exp_word in EXP_CASES:
        got = exp_verdict(posts)["verdict"]
        if got.startswith(exp_word):
            ok_exp += 1
        else:
            fails.append(f"exp {name}: 기대 {exp_word}, 결과 {got}")
    ok_new = 0
    nt = new_tokens("열세 개 중 두 개 Science Advances", "열세 개 중 두 개 Science Advances 94% 그리고 ChatGPT")
    if nt == ["94%", "ChatGPT"]:
        ok_new = 1
    else:
        fails.append(f"new_tokens: 기대 ['94%', 'ChatGPT'], 결과 {nt}")
    held = []
    if CASES_PATH.exists():
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                held.append(json.loads(line))
    held_new = [c for c in held if not c.get("tuned")]
    if held_new:
        okh = sum(1 for c in held_new if route(c["request"], rb)["type"] == c["expected"])
        print(f"보류 시험(키워드를 고치기 전에 모은 실제 발화) {okh}/{len(held_new)}")
    missing = []
    for t, d in rb["types"].items():
        for g in d["playbook"]["guides"]:
            if g.startswith("file:") and not (HERE.parent.parent / g[5:]).exists():
                missing.append(g)
    if missing:
        fails.append(f"플레이북이 가리키는 파일 없음: {missing}")
    # 사장님 2026-10-12·13: 덱스·비티는 기술 전문가라 글 평가에서 제외한다. 평가표가 이 둘을 평가자로 다시 가리키면 막는다(CLAUDE#4e7b).
    raw = json.dumps(rb, ensure_ascii=False).replace("덱스·비티 제외", "").replace("덱스·비티는 글 평가에서 제외", "")
    if "덱스" in raw or "비티" in raw:
        fails.append("평가표(maya_write_rubrics.json)가 덱스·비티를 글 평가자로 가리킨다(사장님 2026-10-12: 글 평가 제외)")
    print(f"route {ok_route}/{len(ROUTE_CASES)}, lint {ok_lint}/{len(LINT_CASES)}, 실험 판정 {ok_exp}/{len(EXP_CASES)}, 새사실검사 {ok_new}/1, 가이드 파일 경로 {'정상' if not missing else '문제'}")
    for f in fails:
        print("  실패:", f)
    return 0 if not fails else 1


# ---------------------------------------------------------------- cli
def main(argv=None):
    ap = argparse.ArgumentParser(description="마야 글쓰기 고도화 루프 도구")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("route"); a.add_argument("request")
    a = sp.add_parser("lint"); a.add_argument("file", nargs="?"); a.add_argument("--text"); a.add_argument("--title"); a.add_argument("--sub")
    a.add_argument("--context", choices=["carvit", "home", "generic"], default="generic"); a.add_argument("--json", action="store_true"); a.add_argument("--numbers", action="store_true"); a.add_argument("--body", action="store_true", help="홈페이지 글 본문 분량(900~1,500자)도 검사")
    a = sp.add_parser("card"); a.add_argument("kind"); a.add_argument("file")
    a = sp.add_parser("log"); a.add_argument("action", choices=["add"]); a.add_argument("--type", required=True); a.add_argument("--artifact", required=True)
    a.add_argument("--scores", required=True, help='JSON 문자열 또는 JSON 파일 경로'); a.add_argument("--evaluator", required=True)
    a.add_argument("--kind", choices=["baseline", "production"], default="production"); a.add_argument("--notes", default=""); a.add_argument("--lint-file")
    a.add_argument("--context", default="generic"); a.add_argument("--title"); a.add_argument("--sub")
    a = sp.add_parser("draft"); a.add_argument("--brief", required=True); a.add_argument("--out", required=True); a.add_argument("--allow-thin-brief", action="store_true")
    a.add_argument("--strategies", default="scene,fail,order", help="이름 목록(scene,fail,order) 또는 '이름=지시문' 여러 개를 세미콜론으로")
    a.add_argument("--model", default="gemini-3.8-flash"); a.add_argument("--send", action="store_true", help="비교 문서를 텔레그램 컨펌 방으로 보낸다")
    a = sp.add_parser("routecase"); a.add_argument("request"); a.add_argument("expected", help="ux|copy|tech|brand|naming|none")
    a.add_argument("--tuned", action="store_true", help="이 발화를 보고 키워드를 고쳤으면 표시(보류 시험에서 빠진다)")
    a = sp.add_parser("exp"); a.add_argument("action", choices=["add", "snap", "report"])
    a.add_argument("--post"); a.add_argument("--group"); a.add_argument("--title", default=""); a.add_argument("--planned"); a.add_argument("--note", default="")
    a.add_argument("--when"); a.add_argument("--likes", type=int); a.add_argument("--impressions", type=int); a.add_argument("--comments", type=int)
    a = sp.add_parser("report"); a.add_argument("--days", type=int)
    sp.add_parser("selftest")
    args = ap.parse_args(argv)
    rb = load_rubrics()

    if args.cmd == "route":
        r = route(args.request, rb)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "lint":
        text = args.text if args.text is not None else (Path(args.file).read_text(encoding="utf-8") if args.file else "")
        res = lint(text, args.context, args.title, args.sub, rb, body=args.body)
        if args.numbers:
            res["numbers"] = numbers_in(text)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"린트 {res['status']} (합니다체 {res['polite']} / 평어체 {res['plain']}, {res['chars']}자)")
            for i in res["issues"]:
                print(f"  [{i['level']}] {i['rule']}: {i['message']}")
            if args.numbers:
                print("  수치(사람이 요약·표와 대조):", ", ".join(res["numbers"]))
        return res["code"]
    if args.cmd == "card":
        if args.kind not in rb["types"]:
            print(f"종류는 {list(rb['types'])} 중 하나", file=sys.stderr); return 2
        print(make_card(args.kind, Path(args.file).read_text(encoding="utf-8"), rb))
        return 0
    if args.cmd == "log":
        raw = args.scores
        scores = json.loads(Path(raw).read_text(encoding="utf-8")) if Path(raw).exists() else json.loads(raw)
        if "scores" in scores:
            scores = scores["scores"]
        lsum = None
        if args.lint_file or args.title or args.sub:
            body = Path(args.lint_file).read_text(encoding="utf-8") if args.lint_file else ""
            lr = lint(body, args.context, args.title, args.sub, rb)
            lsum = {"status": lr["status"], "errors": sum(1 for i in lr["issues"] if i["level"] == "error"), "warns": sum(1 for i in lr["issues"] if i["level"] == "warn")}
        try:
            rec = log_add(args.type, args.artifact, scores, args.evaluator, args.kind, args.notes, lsum, rb)
        except ValueError as e:
            print(f"기록 거부: {e}", file=sys.stderr); return 2
        print("기록함:", json.dumps({k: rec[k] for k in ("ts", "type", "kind", "evaluator", "independent")}, ensure_ascii=False), "→", LOG_PATH)
        return 0
    if args.cmd == "draft":
        raw = args.strategies
        parts = [x.strip() for x in (raw.split(";") if "=" in raw else raw.split(",")) if x.strip()]
        strat = []
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                strat.append((k.strip(), v.strip()))
            elif part in STRATEGIES:
                strat.append((part, STRATEGIES[part]))
            else:
                print(f"알 수 없는 전략: {part} (가능: {list(STRATEGIES)})", file=sys.stderr)
                return 2
        res, out = draft(args.brief, args.out, strat, args.model, rb, allow_thin=args.allow_thin_brief)
        for r in res:
            print(r["name"], ("실패:" + r["error"]) if "error" in r else f"{r['chars']}자 린트 {r['lint']} 새사실 {r['new'] or '없음'} 경고 {r['issues'] or '없음'}")
        print("비교 문서:", out)
        if args.send:
            tg = HERE / "tg_boss.py"
            r = subprocess.run([sys.executable, str(tg), "text", "--file", str(out), "--persona", "마야"], capture_output=True,
                               text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            print("텔레그램:", (r.stdout or r.stderr).strip()[-80:])
        return 0
    if args.cmd == "routecase":
        exp = None if args.expected == "none" else args.expected
        if exp and exp not in rb["types"]:
            print("expected는 종류 이름 또는 none", file=sys.stderr); return 2
        got = route(args.request, rb)["type"]
        CASES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CASES_PATH.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ts": datetime.now(KST).isoformat(timespec="seconds"), "request": args.request, "expected": exp, "got": got, "tuned": args.tuned}, ensure_ascii=False) + "\n")
        print("기록함:", "맞음" if got == exp else f"틀림(결과 {got})", "→", CASES_PATH)
        return 0
    if args.cmd == "exp":
        try:
            if args.action == "add":
                exp_add(args.post, args.group, args.title, args.planned, args.note); print("등록함:", args.post, args.group)
            elif args.action == "snap":
                exp_snap(args.post, args.when, args.likes, args.impressions, args.comments); print("측정 기록:", args.post, args.when)
            else:
                print(exp_report())
        except (ValueError, TypeError) as e:
            print(f"거부: {e}", file=sys.stderr); return 2
        return 0
    if args.cmd == "report":
        text, _ = report(args.days, rb)
        print(text)
        return 0
    if args.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    sys.exit(main())
