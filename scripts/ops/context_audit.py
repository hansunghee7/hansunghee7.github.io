# -*- coding: utf-8 -*-
"""컨텍스트 감수 에이전트 v0(2026-10-15 탐, 사장님: "우리 컨텍스트만 관리하는 전문 에이전트를 두고, 우리 에이전트의 오류·실수를 감지해 문서나 DB를 개선").
하는 일(제안 전용): 최근 N시간의 마찰 기록(훅 차단, 사람 개입 표시, 권한 거절, 목표 재질문 관문)을 모아 집계하고,
Claude API(api_run.py, 프로모션 크레딧)로 '반복되는 실수 → 원인이 된 문서·규칙·DB → 고칠 제안 한 줄'을 뽑아 파일로 남긴다.
하지 않는 일: 문서·DB·훅을 직접 고치지 않는다(덱스·비티 의견 10/15: 제안만 하고 승인 뒤 반영, 근거 표시, 되돌릴 수 있게). 반영은 탐이 PR로.
비밀값 보호: 명령 원문에 key·token·secret·password·Bearer 같은 말이 있으면 그 줄은 보내지 않는다.
산출: C:/work/_ops/context_audit/YYYYMMDD_HHMM.md (집계표 + 모델 제안). 실패하면 종료 코드 1.
2단계(사장님 10/15 "한 곳 고치면 영향 주는 것까지 고려, 사이드 이펙트 없어야, DB 구조화·문서·DB 활용 전략 이해"):
  1차 제안에 나온 파일·훅·표 이름마다 context_graph.json(context_graph.py)으로 '이것을 언급하는 곳'을 찾아 붙이고,
  상위 모델(기본 오퍼스)이 우리 정본 전략(슈퍼프로세스, 문서 다이어트 기준)을 읽은 상태로 영향 범위·부작용·시험 방법까지 다시 검토한다.
사용: python scripts/ops/context_audit.py [--hours 24] [--model claude-sonnet-5-5] [--review-model claude-opus-5-5] [--dry]"""
import collections
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

OPS = Path("C:/work/_ops")
OUT = OPS / "context_audit"
SECRET = re.compile(r"(key|token|secret|password|passwd|bearer|sk-|sb_|apikey)", re.I)
SOURCES = {  # 파일 → (시각 필드, 분류 필드, 예시 필드)
    "human_touch_log.jsonl": ("t", "reason", "line"),
    "db_gate_log.jsonl": ("t", "decision", "why"),
    "denied_log.jsonl": ("t", "reason", "target"),
    "drive_gate_log.jsonl": ("t", "goal", "ask"),
    "save_gate_log.jsonl": ("t", None, None),
    "tami_failures.jsonl": ("t", None, None),
}


def load(name, since):
    p = OPS / name
    rows = []
    if not p.exists():
        return rows
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        t = str(r.get("t") or r.get("time") or "").replace("T", " ")
        if t >= since:
            rows.append(r)
    return rows


def summarize(hours):
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    lines, total = [], 0
    for name, (_, cat, ex) in SOURCES.items():
        rows = load(name, since)
        total += len(rows)
        if not rows:
            continue
        cnt = collections.Counter(str(r.get(cat, "")) for r in rows) if cat else collections.Counter({"(전체)": len(rows)})
        lines.append(f"## {name}: {len(rows)}건")
        for k, v in cnt.most_common(6):
            lines.append(f"- {k[:80]}: {v}건")
        samples = []
        for r in rows[-40:]:
            s = str(r.get(ex, "")) if ex else json.dumps(r, ensure_ascii=False)
            if s and not SECRET.search(s):
                samples.append(s[:160])
        for s in list(dict.fromkeys(samples))[-6:]:
            lines.append(f"  · 예: {s}")
    return since, total, "\n".join(lines)


PROMPT = """너는 AI 에이전트 팀(탐·마야·지투·핏·노트)의 '컨텍스트 감수 에이전트'다. 아래는 최근 {hours}시간 동안 에이전트들이 막히거나 사람에게 물은 기록의 집계다.
할 일: 반복되는 실수·마찰을 찾아, 원인이 된 문서·규칙(훅)·DB 기록을 추정하고, 고칠 제안을 낸다.
규칙: ① 고치지 말고 제안만. ② 근거로 집계 숫자나 예시를 꼭 인용. ③ 확실하지 않으면 '추정'이라고 쓴다. ④ 훅이 잘못 막는 경우(오탐)와 에이전트가 규칙을 어긴 경우를 구분한다.
형식(한국어, 30줄 이내): 상위 5개 항목. 각 항목 = 제목 / 근거(숫자·예시) / 원인 추정(문서·훅·DB 중 어디) / 제안 한 줄 / 오탐인지 위반인지 / 확신(높음·중간·낮음).

집계:
{summary}
"""


REVIEW = """너는 AI 에이전트 팀의 컨텍스트 설계 책임자다. 1차 감수 제안을 받아, 고쳤을 때 다른 곳이 깨지지 않는지(사이드 이펙트) 검토해 최종 제안으로 다듬는다.
원칙: ① 제안만 한다(직접 고치지 않음). ② 각 제안마다 '고칠 곳'과 '영향받는 곳'(아래 연관관계 지도에서 인용)을 적는다. ③ 영향받는 곳이 깨질 위험과 그것을 확인하는 시험(재생할 로그, 돌릴 시험 파일, 확인 명령)을 적는다.
④ 문서와 DB의 역할을 지킨다: 판정 가능한 규칙은 도구 관문(훅·스크립트)에, 왜·예외는 문서에, 상태·기록은 DB에(아래 정본 전략 발췌). ⑤ 근거가 약하면 '추정', 확인할 질문을 낸다. ⑥ 같은 문제를 여러 곳에서 고치면 정본 한 곳을 정하고 나머지는 가리키게 한다.
⑧ 구조 진단(사장님 10/15: "문제를 감지하면 원인을 구조적으로 판단해 문서 정리 방식과 저장 위치, 찾기 어려운 것의 이동 같은 걸 조정"): 원인이 '지식(못 찾음)'이나 '충돌'이면 내용 고치기보다 먼저 위치·형태를 진단한다.
   - 위치 3층: 1차 = 공정 카드(DB)·최신 결정(기억 도우미가 먼저 찾음), 2차 = 정본 문서(제목 단위 색인), 3차 = 히스토리(기본 검색에서 빠짐). 자주 필요한데 2·3차에 묻힌 규칙은 1차 카드로 올리고, 낡은 규칙은 히스토리로 내린다.
   - 형태: 같은 규칙이 여러 곳이면 정본 하나 + 나머지는 가리키는 한 줄. 판정 가능한 규칙은 훅·도구로.
   - 찾기 시험: 그 실수를 한 에이전트가 물었을 질문 한 줄을 적어라(장부의 --query). 고친 뒤 기억 도우미가 그 질문으로 규칙을 찾아내면 성공이다.
⑨ 문서량·구조(사장님 10/16: 위치만이 아니라 구조·내용·문서량까지): 아래 '문서량 점검'에서 상한을 넘은 자동 로드 문서는 에이전트가 끝까지 못 읽고 일하는 원인이다. 넘친 문서마다 무엇을 어디로 옮겨(공정 카드·하위 문서·히스토리) 몇 줄로 줄일지 A에 제안하고, 마찰 기록과 연결되면 그 연결을 적는다.
   - 순서: 자동 로드 문서는 넘치면 뒤가 잘리므로 핵심 규칙(매번 지켜야 하는 것)이 앞에, 이력·예시는 뒤나 하위 문서에 있어야 한다. 순서가 거꾸로면 옮길 절을 제안한다.
   - 구조: 아래 '문서 구조 스캔 발췌'의 같은 사실 여러 곳 묶음과 묻힌 규칙 중 오늘 마찰과 겹치는 것은 정본 하나와 가리키는 줄로 정리하도록 A에 넣는다.
⑦ 너는 전체 판을 보는 판정자다(사장님 10/15: "판정은 전체 판을 바라보는 에이전트가 했으면 좋겠다, 그게 에이전틱 시스템"). 실수한 에이전트나 고친 에이전트가 아니라 네가 아래 수정 경험 장부를 보고 판정한다.
형식(한국어, 50줄 이내):
A. 최종 제안 3~5개. 각각 = 제목 / 문제 근거 / 고칠 곳(정본) / 영향받는 곳 / 부작용 위험과 시험 / 우선순위(효과·위험).
B0. 혼란 정보: 아래 '혼란 정보 후보' 카드마다 숨김(1차에서 내림)·유지·정본 표시 보강 중 하나와 이유. 찾아야 하는 것은 찾기 쉽게, 혼란스럽게 만드는 정보는 찾기 어렵게(사장님 10/15). 숨김은 네 판정대로 실행기(context_apply.py)가 바로 내리므로 '**숨김**' 아래에 "- 카드명#번호[, 카드명#번호]: 이유" 형식으로만 쓰고, 확신 없는 카드는 숨김에 넣지 마라.
B. 장부 판정: 장부의 각 건(CF번호)마다 한 줄 = 판정(채택·기각·보류·다음 수준으로 올림) / 이유 / 재발 신호가 실수를 제대로 잡는지(신호가 틀리면 고칠 신호).
C. 운영 판정 질문이 있으면 답한다: {questions}
D. 실행 지시: 정본 표시 보강처럼 카드 글을 고쳐야 하는 것은 실행 담당(소넷)이 네 지시대로 바로 고친다. 맨 끝에 ```actions 코드 블록 하나로 JSON 배열을 쓴다. 원소 = {{"op":"rewrite","card":"카드명#번호","instruction":"무엇을 어떻게 고칠지 한두 문장(예: 정본 마야#38을 가리키는 한 줄만 남기고 옛 규칙 문장은 뺀다)"}}. 최대 5개, 확신 있는 것만. 사장님 결정의 해석이 갈리는 것(어느 값이 맞는가)은 넣지 말고 C에 질문으로 남겨라. 없으면 [].

[수정 경험 장부(회사 simplifier): 상태·원인·수준·신호·결과]
{ledger}

[1차 제안]
{first}

[연관관계 지도 발췌: 이름 → 이것을 언급하는 곳]
{impacts}

[정본 전략 발췌]
{strategy}

[문서량 점검: 자동으로 읽히는 문서의 길이 / 상한]
{volume}

[문서 구조 스캔 발췌(최근 docscan): 같은 사실이 여러 곳 / 묻혀 있는 규칙]
{structure}
"""


def impacts_for(text, limit=10):
    try:
        g = json.loads(Path("C:/work/_ops/context_graph.json").read_text(encoding="utf-8"))["edges"]
    except (OSError, ValueError, KeyError):
        return "(연관관계 지도 없음: python scripts/ops/context_graph.py build)"
    nodes = set(g) | {t for v in g.values() for t in v}
    hits = []
    for n in sorted(nodes, key=len, reverse=True):
        base = n.split("/")[-1]
        stem = base.rsplit(".", 1)[0]
        alt = {base, stem, stem.replace("-", "_"), stem.replace("_", "-")}  # save-gate.py ↔ save_gate 표기 차이(10/15 2단계 검토가 지도에서 못 찾음)
        if len(stem) >= 5 and any(x in text for x in alt) and n not in hits:
            hits.append(n)
    out = []
    for n in hits[:limit]:
        used_by = sorted(k for k, v in g.items() if n in v)
        out.append(f"- {n}: {len(used_by)}곳 → " + ", ".join(used_by[:12]) + (" ..." if len(used_by) > 12 else ""))
    return "\n".join(out) or "(1차 제안에 지도와 겹치는 이름 없음)"


def strategy_excerpt():
    repo = Path(__file__).resolve().parents[2]
    parts = []
    for f, n in (("docs/슈퍼프로세스.md", 40), ("docs/문서_다이어트_기준.md", 30)):
        r = subprocess.run(["git", "-c", "core.quotepath=false", "-C", "C:/work/hansunghee7.github.io", "show", f"origin/main:{f}"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        parts.append(f"## {f}\n" + "\n".join(r.stdout.splitlines()[:n]))
    return "\n\n".join(parts)


def ledger_view():
    """수정 경험 장부(ctxfix, 운영 DB) 현황을 판정 재료로 붙인다. 실패하면 비운다(1차·영향 검토는 그대로 진행)."""
    try:
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "ctxfix.py"), "list"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        rows = r.stdout.strip().splitlines()
        rc = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "ctxfix.py"), "recheck"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        # 혼란 정보 후보(사장님 10/15 "혼란스럽게 만드는 정보는 찾기 어렵게"): 폐기·대체 표시가 있는데 1차 자리에 남은 카드
        cs = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "confusion_scan.py"), "--top", "25"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        cf = Path("C:/work/_ops/context_audit") / f"confusion_{datetime.now():%Y%m%d}.md"
        conf = ("\n[혼란 정보 후보]\n" + cf.read_text(encoding="utf-8")[:2500]) if cs.returncode == 0 and cf.exists() else ""
        return "\n".join(rows[:30]) + "\n[오늘 재발 판정]\n" + rc.stdout.strip()[:2000] + conf
    except Exception as e:  # noqa: BLE001
        return f"(장부 읽기 실패: {e})"


# 문서량 점검(사장님 10/16: "사서가 문서 위치뿐 아니라 문서 구조·내용·문서량까지 봐서 에이전트 문제 원인을 해결").
# 사고: 탐 기억 색인 MEMORY.md가 211줄이라 200줄 뒤가 안 읽힌 채 일했다. 자동으로 읽히는 문서는 넘치면 조용히 잘린다.
# (경로 또는 glob, 상한 줄 수, 근거). 저장소 파일은 origin/main 기준, 기억 색인은 최근 30일 안에 바뀐 것만.
VOLUME_RULES = (
    ("CLAUDE.md", 250, "CI 상한(목표 200), CLAUDE#a18e"),
    ("docs/역할노트-*.md", 80, "역할 노트 상한, CLAUDE#a18e"),
    ("docs/세션카드/*.md", 80, "세션 시작 때 통째로 읽음(역할 노트와 같은 기준)"),
    (".claude/skills/*/SKILL.md", 500, "스킬 본문은 열 때 통째로 읽음"),
    (".claude/rules/*.md", 150, "경로별 규칙은 자동 로드"),
)
MEMORY_LIMIT = 200  # Claude Code 기억 색인 읽기 한도(넘는 줄은 조용히 버려짐)


def volume_view():
    import fnmatch
    repo = "C:/work/hansunghee7.github.io"
    out = []
    try:
        ls = subprocess.run(["git", "-c", "core.quotepath=false", "-C", repo, "ls-tree", "-r", "--name-only", "origin/main"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout.splitlines()
        for pat, limit, why in VOLUME_RULES:
            for f in [x for x in ls if fnmatch.fnmatch(x, pat)]:
                n = len(subprocess.run(["git", "-C", repo, "show", f"origin/main:{f}"], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=30).stdout.splitlines())
                if n > limit * 0.9:
                    out.append(f"- {f}: {n}줄 / 상한 {limit} ({'넘침' if n > limit else '90% 이상'}, {why})")
        cutoff = datetime.now().timestamp() - 30 * 86400
        for m in Path("C:/Users/PC/.claude/projects").glob("*/memory/MEMORY.md"):
            if m.stat().st_mtime < cutoff:
                continue
            n = len(m.read_text(encoding="utf-8", errors="replace").splitlines())
            if n > MEMORY_LIMIT * 0.9:
                out.append(f"- 기억 색인 {m.parent.parent.name}: {n}줄 / 읽기 한도 {MEMORY_LIMIT} ({'넘침: 뒤쪽이 안 읽힘' if n > MEMORY_LIMIT else '90% 이상'})")
    except Exception as e:  # noqa: BLE001
        return f"(문서량 점검 실패: {e})"
    return "\n".join(out) or "(상한 90%를 넘은 자동 로드 문서 없음)"


def structure_view(limit=2500):
    """가장 최근 문서 구조 스캔(doc_structure_scan.py 결과 docscan_YYYYMMDD_HHMM.md)에서 3절(같은 사실 여러 곳)·5절(묻힌 규칙)만 붙인다."""
    try:
        files = sorted(p for p in OUT.glob("docscan_2*.md"))
        if not files:
            return "(문서 구조 스캔 결과 없음: python scripts/ops/doc_structure_scan.py)"
        text = files[-1].read_text(encoding="utf-8", errors="replace")
        parts = re.split(r"(?m)^## ", text)
        keep = [p for p in parts if p.startswith("3.") or p.startswith("5.")]
        return f"({files[-1].name})\n" + "\n".join("## " + p.strip() for p in keep)[:limit]
    except Exception as e:  # noqa: BLE001
        return f"(구조 스캔 읽기 실패: {e})"


# 날짜가 오면 판정자가 답할 운영 질문(사람이 아니라 전체 판을 보는 감수 에이전트가 판정, 사장님 10/15)
JUDGE_QUESTIONS = (
    ("2026-10-22", "슈퍼프로세스 ⑦ 사고 회수 루프 자동판(원인 분류·고침 수준·재발 신호·매일 재판정)을 전 에이전트 정본 방식으로 채택할지: 지난 1주 장부의 성공·실패·신호 품질을 근거로 채택/보완 후 재판정/폐기 중 하나와 이유 3줄."),
)


def judge_questions():
    today = datetime.now().strftime("%Y-%m-%d")
    qs = [q for d, q in JUDGE_QUESTIONS if today >= d]
    return " / ".join(qs) if qs else "(오늘 판정할 운영 질문 없음)"


def review(first, summary, a, stamp, api):
    model = a[a.index("--review-model") + 1] if "--review-model" in a else "claude-opus-5-5"
    q = OUT / f"q2_{stamp}.md"
    q.write_text(REVIEW.format(first=first, impacts=impacts_for(first), strategy=strategy_excerpt(), ledger=ledger_view(), questions=judge_questions(), volume=volume_view(), structure=structure_view()), encoding="utf-8")
    o = OUT / f"a2_{stamp}.md"
    r = subprocess.run([sys.executable, str(api), "--who", "컨텍스트감수", "--model", model, "--prompt-file", str(q), "--max-tokens", "12000", "--out", str(o)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not o.exists() or not o.read_text(encoding="utf-8").strip():
        return "(2단계 검토 실패, 1차 제안만 사용: " + ((r.stderr or r.stdout).strip().splitlines() or ["원인 불명"])[-1][:160] + ")"
    return o.read_text(encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    hours = int(a[a.index("--hours") + 1]) if "--hours" in a else 24
    model = a[a.index("--model") + 1] if "--model" in a else "claude-sonnet-5-5"
    since, total, summary = summarize(hours)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    qf, af, rf = OUT / f"q_{stamp}.md", OUT / f"a_{stamp}.md", OUT / f"{stamp}.md"
    qf.write_text(PROMPT.format(hours=hours, summary=summary), encoding="utf-8")
    if "--dry" in a:
        print(qf.read_text(encoding="utf-8"))
        return 0
    api = Path(__file__).resolve().parent / "api_run.py"
    r = subprocess.run([sys.executable, str(api), "--who", "컨텍스트감수", "--model", model, "--prompt-file", str(qf), "--max-tokens", "8000", "--out", str(af)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not af.exists():
        print("컨텍스트 감수 실패: " + ((r.stderr or r.stdout).strip().splitlines() or ["원인 불명"])[-1][:200])
        return 1
    first = af.read_text(encoding="utf-8")
    final = review(first, summary, a, stamp, api)
    rf.write_text(f"# 컨텍스트 감수 {stamp} (최근 {hours}시간, 기록 {total}건, 제안 전용)\n\n## 최종 제안(영향 검토 반영)\n{final}\n\n## 1차 제안\n{first}\n\n## 집계\n{summary}\n", encoding="utf-8")
    print(f"컨텍스트 감수 완료: {rf} (기록 {total}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
