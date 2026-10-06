#!/usr/bin/env python3
"""마야 글쓰기 고도화 루프의 도구 한 벌(2026-10-06 사장님 지시: "글로벌 탑급 라이터 되기").

왜: 문서에만 있는 규칙은 세션이 바뀌면 빠진다(CLAUDE#4e7b). 글 종류 판별, 기계가 셀 수 있는 규칙 검사,
독립 평가 기록, 주간 점검을 코드로 두어 같은 루프가 매번 돈다. 정본 데이터는 maya_write_rubrics.json.

하위 명령
  route "<요청 문장>"            글 종류 판별과 작업 순서(가이드, 작성 도구, 검사, 독립 평가, 컨펌)를 출력
  lint  <파일|--text 문자열>      기계 검사(증명 불가 형용사, 문체 혼용, 제품 이름·회사 이름·용어, 길이)
  card  <종류> <파일>             독립 평가자(덱스·비티)에게 줄 채점 카드(마크다운)를 만든다
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
        res["rubric"] = [i["id"] for i in rb["common"]] + [i["id"] for i in rb["types"][res["type"]]["rubric"]]
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
SOURCE_MARK = re.compile(r"(출처|https?://|\(\s*\d{4}|\[\d+\]|참고)")


def unsourced_claims(text):
    """연구·조사 같은 말로 근거를 대면서 같은 문장에 출처 표시가 없는 문장(독립 평가 10/6 카피 '신뢰증거' 2점에서 나온 규칙)."""
    out = []
    for s in sentences(text):
        if CLAIM_WORD.search(s) and CLAIM_NUM.search(s) and not SOURCE_MARK.search(s) and "테크리포트" not in s and "버전" not in s:
            out.append(s[:60])
    return out


def lint(text, context="generic", title=None, sub=None, rb=None):
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

    level = 2 if any(i["level"] == "error" for i in issues) else (1 if issues else 0)
    return {"status": ["pass", "warn", "error"][level], "code": level, "issues": issues,
            "polite": pol, "plain": pla, "chars": len(text)}


def numbers_in(text):
    return sorted(set(re.findall(r"\d[\d,.]*\s?(?:%|건|회|개|명|px|초|분|시간|자|원)?", text)))[:40]


# ---------------------------------------------------------------- card
def make_card(kind, text, rb=None):
    rb = rb or load_rubrics()
    t = rb["types"][kind]
    items = rb["common"] + t["rubric"]
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
    return [i["id"] for i in rb["common"]] + [i["id"] for i in rb["types"][kind]["rubric"]]


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
        f = lambda s: "미측정" if not s else f"좋아요 {s['likes']}·노출 {s['impressions']}"
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
    print(f"route {ok_route}/{len(ROUTE_CASES)}, lint {ok_lint}/{len(LINT_CASES)}, 실험 판정 {ok_exp}/{len(EXP_CASES)}, 가이드 파일 경로 {'정상' if not missing else '문제'}")
    for f in fails:
        print("  실패:", f)
    return 0 if not fails else 1


# ---------------------------------------------------------------- cli
def main(argv=None):
    ap = argparse.ArgumentParser(description="마야 글쓰기 고도화 루프 도구")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("route"); a.add_argument("request")
    a = sp.add_parser("lint"); a.add_argument("file", nargs="?"); a.add_argument("--text"); a.add_argument("--title"); a.add_argument("--sub")
    a.add_argument("--context", choices=["carvit", "home", "generic"], default="generic"); a.add_argument("--json", action="store_true"); a.add_argument("--numbers", action="store_true")
    a = sp.add_parser("card"); a.add_argument("kind"); a.add_argument("file")
    a = sp.add_parser("log"); a.add_argument("action", choices=["add"]); a.add_argument("--type", required=True); a.add_argument("--artifact", required=True)
    a.add_argument("--scores", required=True, help='JSON 문자열 또는 JSON 파일 경로'); a.add_argument("--evaluator", required=True)
    a.add_argument("--kind", choices=["baseline", "production"], default="production"); a.add_argument("--notes", default=""); a.add_argument("--lint-file")
    a.add_argument("--context", default="generic"); a.add_argument("--title"); a.add_argument("--sub")
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
        res = lint(text, args.context, args.title, args.sub, rb)
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
