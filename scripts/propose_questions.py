"""
"심플리파이어에게 질문하기" — 질문 후보 제안 (주 1회).
정본 설계: docs/질문하기_파이프라인.md (단계 1·2, 계단 4).

방문자 질문이 없는 주에도 글이 나오도록, 클로드가 "독자가 실제로 궁금해할
질문" 10개를 제안해 GitHub 이슈 하나에 체크박스로 올린다. 사장님은 폰
GitHub 앱에서 마음에 드는 것만 체크(=픽)하고, pick_questions.py 가 체크된
것을 접수함('대기')에 넣는다.

근거 자료(전부 저장소에 이미 있는 것 — 새로 모으지 않는다):
  - assets/data/search-console.json  top_queries_90d  : 사람들이 실제로 치고
    들어온 검색어 — 가장 좋은 질문 후보
  - assets/data/search-console.json  top_pages_90d    : 많이 읽힌 글
  - assets/data/posts.json                            : 기존 글 제목·카테고리
    (이미 쓴 주제와 겹치지 않게, 또는 후속편이 될 수 있게)
  - assets/data/newsletter_research.json              : 최근 리서치 주제

필요한 Secrets: ANTHROPIC_API_KEY. 이슈 생성은 GH_TOKEN(GITHUB_TOKEN).
선택: DRAFT_MODEL(기본 claude-opus-5), DRY_RUN=1 이면 이슈를 만들지 않고 출력만.
"""
import datetime as dt
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data"
MODEL = os.environ.get("DRAFT_MODEL", "claude-opus-5")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
LABEL = "question-candidates"
MARK = "<!-- question-candidates -->"

CATEGORIES = [
    "스타트업 인사이트", "UX의 언어들", "심플리파이어 라이프", "기획일상", "토크세션",
    "Be the PO", "대한민국 스타트업 미국진출을 묻다", "PO의 프레임웍", "AI의 언어들",
    "기획자의 프레임웍", "코치S", "잉크드인대 기획학과",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "minItems": 8,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "독자가 실제로 쓸 법한 1~2문장 질문. 존댓말."},
                    "why": {"type": "string", "description": "왜 이 질문인지 한 줄(근거 자료를 구체적으로)."},
                    "source_type": {"type": "string", "enum": ["검색어", "많이 읽힌 글", "기존 글 후속", "리서치 주제", "조합"]},
                    "category": {"type": "string", "enum": CATEGORIES},
                },
                "required": ["question", "why", "source_type", "category"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["candidates"],
    "additionalProperties": False,
}

SYSTEM = """당신은 홈페이지 simplifier.co.kr의 편집자다. 필자는 30년 경력의 전직 프로덕트 총괄(CPO)·
스타트업 코치이며, 후배들에게 불편한 진실을 따뜻하게 건네는 멘토형 글을 쓴다.

아래 자료를 보고, 독자(기획자·PM·PO·스타트업 리더·커리어 전환자)가 필자에게 실제로
물어볼 법한 질문 후보 10개를 만든다. 규칙:
- 검색어 자료를 가장 무겁게 본다: 사람들이 이미 치고 들어온 말이 곧 질문이다.
- 기존 글과 똑같은 주제는 피하되, "그 다음 질문"(후속편)은 좋다.
- 질문은 독자의 상황이 보이게 구체적으로("팀장 2년 차인데…"). 추상적 대주제 금지.
- 필자가 경험으로 답할 수 있는 것만. 필자가 모르는 분야(세무·법률 등)는 제외.
- why 칸에는 어떤 검색어/글/리서치에서 왔는지 실제 값을 적는다. 지어내지 않는다.
- 출력은 지정된 JSON 형식으로만."""


def load_json(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def build_material() -> str:
    sc = load_json("search-console.json")
    posts = load_json("posts.json") or []
    research = load_json("newsletter_research.json") or {}

    queries = sc.get("top_queries_90d", [])[:40]
    q_lines = [f"- {q.get('query')} (노출 {q.get('impressions', 0)}, 클릭 {q.get('clicks', 0)})" for q in queries]

    by_url = {p.get("url"): p for p in posts if isinstance(p, dict)}
    pages = []
    for pg in sc.get("top_pages_90d", [])[:15]:
        url = pg.get("page", "")
        path = url.replace("https://simplifier.co.kr", "")
        title = (by_url.get(path) or {}).get("title") or path
        pages.append(f"- {title} (노출 {pg.get('impressions', 0)})")

    recent = sorted([p for p in posts if isinstance(p, dict)], key=lambda p: p.get("date_sort", ""), reverse=True)[:40]
    recent_lines = [f"- [{p.get('category', '')}] {p.get('title', '')}" for p in recent]

    topics = [t.get("topic") for t in research.get("topics", []) if t.get("topic")][:15]

    return "\n".join([
        "## 최근 90일 검색 유입 검색어", *q_lines,
        "", "## 많이 읽힌 글", *pages,
        "", "## 최근 발행 글 40편 (겹치지 않게, 또는 후속편 힌트)", *recent_lines,
        "", "## 최근 리서치 주제", *[f"- {t}" for t in topics],
    ])


def ask_claude(material: str) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic()
    week = dt.date.today().isocalendar()
    user = f"이번 주: {week[0]}-W{week[1]:02d}\n\n{material}\n\n위 자료로 질문 후보 10개."
    kwargs = dict(
        model=MODEL, max_tokens=8000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    try:
        with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs) as s:
            msg = s.get_final_message()
    except anthropic.BadRequestError:
        with client.messages.stream(**kwargs) as s:
            msg = s.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 거절함")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)["candidates"]


def run(*args, capture=False, check=True):
    r = subprocess.run(args, cwd=ROOT, text=True, capture_output=capture, check=check)
    return (r.stdout or "").strip() if capture else ""


def issue_body(cands: list[dict]) -> str:
    lines = [
        MARK,
        "마음에 드는 질문의 체크박스를 켜 주세요. 켜는 순간 접수함에 '대기'로 들어가고, 다음 실행(2시간 이내)에 초안 PR이 생깁니다. ",
        "체크한 줄에는 자동으로 `✅ 접수됨` 표시가 붙습니다. 나머지는 그냥 두면 됩니다(다음 주 새 이슈가 열리며 이 이슈는 닫힘).",
        "",
    ]
    for c in cands:
        q = c["question"].replace("\n", " ").strip()
        lines.append(f"- [ ] {q}  \n  근거: {c['source_type']} — {c['why']} · 카테고리 후보: {c['category']}")
    lines += ["", "정본 설계: docs/질문하기_파이프라인.md (단계 1·2)"]
    return "\n".join(lines)


def main():
    material = build_material()
    cands = ask_claude(material)
    body = issue_body(cands)
    week = dt.date.today().isocalendar()
    title = f"질문 후보 — {week[0]}-W{week[1]:02d}"
    if DRY_RUN:
        print(title); print(body); return

    run("gh", "label", "create", LABEL, "--color", "6f6a61", "--description", "질문 후보 (체크=픽)", "--force", check=False)
    # 지난주 후보 이슈는 닫는다 — 열린 후보 이슈는 항상 하나만.
    old = run("gh", "issue", "list", "--label", LABEL, "--state", "open", "--json", "number", capture=True)
    for it in json.loads(old or "[]"):
        run("gh", "issue", "close", str(it["number"]), "--comment", "새 주 후보 이슈로 대체", check=False)

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body); path = f.name
    url = run("gh", "issue", "create", "--title", title, "--label", LABEL, "--body-file", path, capture=True)
    print("후보 이슈:", url, f"({len(cands)}개)")
    if len(cands) < 5:
        print("::warning::후보가 5개 미만")


if __name__ == "__main__":
    main()
