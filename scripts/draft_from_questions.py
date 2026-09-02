"""
"심플리파이어에게 질문하기" 접수함(Supabase questions 테이블)에서 '대기' 질문을
꺼내 클로드 API로 브랜드 보이스 초안을 쓰고, 초안 브랜치 + PR로 올린다.
정본 설계: docs/질문하기_파이프라인.md (단계 3·4).

흐름 (질문 1건당):
  대기 → [잡기: 상태를 '처리중'으로, 대기였을 때만] → 클로드 초안
      → log_assets/markdown/<제목>.md (published: false) 커밋 → 브랜치 push
      → PR 생성 → 상태 '초안' + PR 번호 기록
  실패하면 상태를 '대기'로 되돌리고 error 기록. 3회째 실패면 '반려'.

설계 원칙 (오늘 SNS 확장에서 겪은 동시 쓰기 사고의 재발 방지):
  - 잡기(claim)는 "현재 상태가 '대기'일 때만 '처리중'으로" 바꾸는 조건부
    갱신(compare-and-set). 두 실행이 겹쳐도 같은 질문을 두 번 쓰지 않는다.
  - 시도 횟수(attempts) 열로 재실행이 무한 반복되지 않게 한다.
  - 브랜드 가이드는 시스템 프롬프트 맨 앞에 고정하고 cache_control을 달아
    매 호출 캐시를 받는다. 질문(매번 다른 것)은 뒤(user)에만 둔다.
  - 질문자 이메일은 절대 파일·PR·로그에 쓰지 않는다 (공개 저장소).

필요한 Secrets (Settings → Secrets and variables → Actions):
  ANTHROPIC_API_KEY      클로드 API 키 (console.anthropic.com)
  SUPABASE_URL           simplifier-agent Supabase 프로젝트 URL (이미 있음)
  SUPABASE_SERVICE_KEY   그 프로젝트의 service_role 키 (이미 있음)
선택 환경변수:
  DRAFT_MODEL            기본 claude-opus-5
  MAX_DRAFTS             한 번 실행에 처리할 최대 건수, 기본 3
  WRITING_GUIDE_PATH     브랜드 가이드 경로, 기본 docs/WRITING_GUIDE.md
  DRY_RUN=1              Supabase·git·PR 없이 초안만 stdout에 출력 (로컬 확인용)
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
sys.stderr.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "log_assets" / "markdown"
GUIDE_PATH = Path(os.environ.get("WRITING_GUIDE_PATH") or ROOT / "docs" / "WRITING_GUIDE.md")
MODEL = os.environ.get("DRAFT_MODEL", "claude-opus-5")
MAX_DRAFTS = int(os.environ.get("MAX_DRAFTS", "3"))
MAX_ATTEMPTS = 3
DRY_RUN = os.environ.get("DRY_RUN") == "1"

# _data/pillars.yml 의 카테고리와 동일해야 필러 페이지에 잡힌다.
CATEGORIES = [
    "스타트업 인사이트", "UX의 언어들", "심플리파이어 라이프", "기획일상", "토크세션",
    "Be the PO", "대한민국 스타트업 미국진출을 묻다", "PO의 프레임웍", "AI의 언어들",
    "기획자의 프레임웍", "코치S", "잉크드인대 기획학과",
]
# 대표 이미지는 사장님이 PR에서 고른다. 그때까지는 파이프라인의 폴백과 같은 로고.
DEFAULT_IMAGE = "/log_assets/images/logo_white.png"
EPISODE_MARK = "[에피소드 필요:"
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

# 브랜드 가이드(문체 교본) 뒤에 붙는 자동화 전용 규칙. 가이드 자체는 사람도
# 세션도 같이 쓰는 순수 문체 문서로 두고, "자동 초안"일 때만 필요한 제약은 여기.
AUTOMATION_RULES = """

---

## 자동 초안 모드 추가 규칙 (사람이 검토하기 전 단계)

이 글은 홈페이지 방문자의 질문에 답하는 글이며, 필자(사장님) 이름으로 나간다.
그래서 아래는 위 가이드보다 우선한다.

1. **에피소드를 지어내지 않는다.** 가이드의 "자동 생성" 모드는 쓰지 않는다. 필자의
   실제 경험이 들어갈 자리에는 그 자리에 어떤 경험이 필요한지 한 줄로 적은
   자리표시자를 남긴다. 형식: `[에피소드 필요: 예) 팀장 첫 해에 겪은 실패담]`.
   자리표시자는 본문에 1~2개.
2. **출처 없는 숫자를 쓰지 않는다.** 연구·통계·수치는 확실한 것만, 그것도
   "무엇의 조사인지"를 문장에 밝힌다. 확신이 없으면 숫자 대신
   `[사실 확인 필요: ...]` 자리표시자.
3. 질문자의 상황을 첫 두 줄(후킹)에 직접 인용하거나 장면으로 받는다. 질문 원문을
   그대로 베끼지 말고 필자 문체로 다시 쓴다.
4. 분량 2,000~3,000자. 마크다운 본문만 쓰고 제목(#)은 본문에 넣지 않는다
   (제목은 별도 필드). 소제목은 "1." "2." 식 챕터 번호를 쓴다.
5. 출력은 반드시 지정된 JSON 형식으로만.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "글 제목. 20자 안팎, 따옴표·콜론 없이."},
        "category": {"type": "string", "enum": CATEGORIES},
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 10,
            "description": "검색 키워드. 기존 글과 같은 결(리더십, 커리어 전환 등).",
        },
        "about": {"type": "string", "description": "한 줄 요약(30자 안팎)."},
        "body_markdown": {"type": "string", "description": "본문 마크다운."},
    },
    "required": ["title", "category", "keywords", "about", "body_markdown"],
    "additionalProperties": False,
}


def load_guide() -> str:
    if not GUIDE_PATH.exists():
        sys.exit(f"브랜드 가이드가 없습니다: {GUIDE_PATH} (WRITING_GUIDE_PATH로 지정 가능)")
    return GUIDE_PATH.read_text(encoding="utf-8")


def ask_claude(client, system_text: str, question: str, page: str | None) -> tuple[dict, dict]:
    """초안 JSON과 usage를 돌려준다. 가이드는 캐시, 질문만 매번 바뀐다."""
    import anthropic

    user_text = f"방문자 질문:\n{question.strip()}"
    if page:
        user_text += f"\n\n(질문을 남긴 글: {page})"

    kwargs = dict(
        model=MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_text}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    # 정책상 거절(refusal)이 나면 같은 호출 안에서 폴백 모델이 이어받도록
    # 서버측 폴백을 기본으로 켠다. 이 베타가 거부되는 환경이면 일반 호출로.
    try:
        with client.beta.messages.stream(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.BadRequestError as e:
        print(f"  폴백 옵션 없이 재시도 ({e.__class__.__name__})")
        with client.messages.stream(**kwargs) as stream:
            msg = stream.get_final_message()

    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답변을 거절했습니다 (stop_reason=refusal)")
    text = next(b.text for b in msg.content if b.type == "text")
    data = json.loads(text)
    usage = {
        "input": msg.usage.input_tokens,
        "cache_write": getattr(msg.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
        "output": msg.usage.output_tokens,
        "model": getattr(msg, "model", MODEL),
    }
    return data, usage


def yaml_scalar(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def build_markdown(draft: dict, question_id: str, now: dt.datetime) -> str:
    keywords = ", ".join(k.strip() for k in draft["keywords"] if k.strip())
    fm = "\n".join([
        "---",
        "layout: default",
        f"title: {yaml_scalar(draft['title'])}",
        f"category: {yaml_scalar(draft['category'])}",
        f"image: {DEFAULT_IMAGE}",
        f"date: {now.strftime('%Y-%m-%dT%H:%M:00Z')}",
        f"keywords: {keywords}",
        f"about: {yaml_scalar(draft['about'])}",
        "published: false",
        "channel_variants:",
        "  linkedin_threads: ''",
        "  instagram_caption: ''",
        "  manual_copy_block: ''",
        f"question_id: {question_id}",
        "---",
        "",
    ])
    body = draft["body_markdown"].strip() + "\n"
    return fm + body


def safe_filename(title: str, question_id: str) -> Path:
    base = INVALID_FILENAME_CHARS.sub("", title).strip().strip(".")
    base = re.sub(r"\s+", " ", base)[:60] or "untitled"
    path = MD_DIR / f"{base}.md"
    if path.exists() or list(MD_DIR.glob(f"[0-9][0-9][0-9]_{base}.md")):
        path = MD_DIR / f"{base} ({question_id[:8]}).md"
    return path


def run(*args: str, check: bool = True, capture: bool = False) -> str:
    r = subprocess.run(args, cwd=ROOT, check=check, text=True, capture_output=capture)
    return (r.stdout or "").strip() if capture else ""


def open_pr(branch: str, path: Path, draft: dict, question: str, usage: dict, source: str = "visitor") -> int:
    n_ep = draft["body_markdown"].count(EPISODE_MARK)
    n_fact = draft["body_markdown"].count("[사실 확인 필요:")
    if source == "pick":
        head = "## 사장님이 픽한 질문 (후보 이슈에서 체크)"
        note = "(회신할 사람 없음 — 발행만 하면 됩니다.)"
        reply_item = ""
    else:
        head = "## 방문자 질문"
        note = "(질문자 이메일은 접수함에만 있습니다 — 여기엔 적지 않습니다.)"
        reply_item = "- [ ] 병합 후 질문자에게 링크 회신 (지금은 수동)\n"
    body = f"""{head}
> {question.strip()}

{note}

## 사장님 체크리스트 (이 PR 안에서 파일을 직접 고치세요)
- [ ] `{EPISODE_MARK} ...]` 자리 {n_ep}곳에 실제 경험 채우기
- [ ] `[사실 확인 필요: ...]` 자리 {n_fact}곳 확인
- [ ] 제목·카테고리·키워드 확인
- [ ] 대표 이미지(`image:`) 고르기 — 지금은 로고 폴백
- [ ] 다 됐으면 `published: false` → `published: true` 로 바꾸고 **병합** → 기존 발행 파이프라인이 라이브로 올립니다
{reply_item}
파일: `{path.relative_to(ROOT)}`
모델: `{usage['model']}` · 토큰 입력 {usage['input']} / 캐시 읽기 {usage['cache_read']} / 캐시 쓰기 {usage['cache_write']} / 출력 {usage['output']}

🤖 Generated with [Claude Code](https://claude.com/claude-code) — docs/질문하기_파이프라인.md 단계 3·4
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        body_file = f.name
    url = run(
        "gh", "pr", "create", "--base", "main", "--head", branch,
        "--title", f"초안: {draft['title']}", "--body-file", body_file, capture=True,
    )
    m = re.search(r"/pull/(\d+)", url)
    return int(m.group(1)) if m else 0


def main() -> None:
    guide = load_guide()
    system_text = guide + AUTOMATION_RULES

    import anthropic
    client = anthropic.Anthropic()

    if DRY_RUN:
        q = os.environ.get("DRY_RUN_QUESTION", "CPO가 되려면 어떻게 준비해야 하나요?")
        draft, usage = ask_claude(client, system_text, q, None)
        print(build_markdown(draft, "dry-run", dt.datetime.now(dt.timezone.utc)))
        print("usage:", usage)
        return

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    rows = (
        sb.table("questions").select("id, question, page, attempts, source")
        .eq("status", "대기").lt("attempts", MAX_ATTEMPTS)
        .order("created_at").limit(MAX_DRAFTS).execute().data
    )
    if not rows:
        print("대기 중인 질문 없음")
        return

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "github-actions[bot]@users.noreply.github.com")
    run("git", "fetch", "-q", "origin", "main")

    for row in rows:
        qid = row["id"]
        attempts = int(row.get("attempts") or 0) + 1
        # 잡기: '대기'일 때만 '처리중'으로 (compare-and-set). 겹친 실행은 여기서 빈손.
        claimed = (
            sb.table("questions").update({"status": "처리중", "attempts": attempts, "error": None})
            .eq("id", qid).eq("status", "대기").execute().data
        )
        if not claimed:
            print(f"[{qid[:8]}] 다른 실행이 먼저 잡음 — 건너뜀")
            continue

        print(f"[{qid[:8]}] 초안 생성 (시도 {attempts}/{MAX_ATTEMPTS})")
        branch = f"draft/q-{qid[:8]}"
        try:
            draft, usage = ask_claude(client, system_text, row["question"], row.get("page"))
            now = dt.datetime.now(dt.timezone.utc)
            path = safe_filename(draft["title"], qid)

            run("git", "checkout", "-q", "-B", branch, "origin/main")
            path.write_text(build_markdown(draft, qid, now), encoding="utf-8")
            run("git", "add", str(path))
            run("git", "commit", "-q", "-m", f"draft: 질문 초안 — {draft['title']}")
            run("git", "push", "-q", "-u", "origin", branch, "--force-with-lease")
            pr = open_pr(branch, path, draft, row["question"], usage, row.get("source") or "visitor")

            sb.table("questions").update({
                "status": "초안", "draft_branch": branch, "draft_pr": pr or None,
                "draft_path": str(path.relative_to(ROOT)), "error": None,
            }).eq("id", qid).execute()
            print(f"[{qid[:8]}] PR #{pr} — {path.name} · 캐시읽기 {usage['cache_read']} 토큰")
        except Exception as e:  # noqa: BLE001 — 한 건 실패가 나머지를 막으면 안 된다
            err = f"{e.__class__.__name__}: {e}"[:500]
            status = "반려" if attempts >= MAX_ATTEMPTS else "대기"
            sb.table("questions").update({"status": status, "error": err}).eq("id", qid).execute()
            print(f"[{qid[:8]}] 실패 → {status}: {err}")
        finally:
            run("git", "checkout", "-q", "--detach", "origin/main", check=False)


if __name__ == "__main__":
    main()
