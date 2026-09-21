"""진행상황.md 오래된 절의 아카이브 "후보" 분류 (초안, 판정 아님).

무엇인가
--------
docs/진행상황.md를 읽어 절(`## `)마다 줄 수·최근 날짜·열린 표시를 뽑고, 아카이브 후보
목록을 C:\\work\\_ops\\weekly\\archive-candidates-<날짜>.md 로 만든다.
문서는 절대 수정하지 않는다. 실제 이동은 scripts/archive_progress.py의 몫이다.

왜 이렇게 설계했나 (코드로 할 수 있는 것은 코드로, LLM은 꼭 필요한 곳만)
--------------------------------------------------------------------
- 절 파싱, 줄 수, 날짜 추출, "7일 넘게 지남 + 열린 표시 없음" 판별은 전부 결정적 코드.
  같은 파일이면 항상 같은 결과가 나온다.
- 날짜가 없거나 열린 표시("미착수·대기·다음 것" 등)가 있는 애매한 절만 LLM에게
  한 줄 분류와 이유 한 줄을 받는다. LLM은 절 안 문장을 새로 쓰지 않는다.
- 최근 7일 이내 날짜가 있는 절은 LLM 없이 "최근, 유지"로 둔다.
- 출력의 모든 항목에 원문 근거(절 제목, 시작 줄 번호)를 붙인다.
- LLM 호출 실패는 그 항목만 "LLM 실패"로 표기하고 계속한다.
"""
import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_llm  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "docs" / "진행상황.md"
OUT_DIR = Path(r"C:\work\_ops\weekly")
STALE_DAYS = 7          # 이보다 오래되면(초과) 후보 검토 대상
FUTURE_SLACK_DAYS = 14  # 오늘보다 이만큼 넘게 미래인 "날짜"는 날짜로 안 침(11/12 같은 비율 표기 방지)

OPEN_RE = re.compile(r"미착수|대기|다음 것|미확인|미실행|미반영|진행 중|☐")

ISO_RE = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
MD_RE = re.compile(r"(?<![\d/.\-])(\d{1,2})/(\d{1,2})(?![\d/])")
KO_RE = re.compile(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일")


def parse_sections(text: str) -> list[dict]:
    """`## ` 절 목록. 코드펜스 안의 `## `는 제목으로 보지 않는다."""
    lines = text.split("\n")
    heads, in_fence = [], False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and ln.startswith("## "):
            heads.append(i)
    out = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        out.append({
            "title": lines[i][3:].strip(),
            "start": i + 1,                       # 1부터 시작하는 줄 번호
            "line_count": end - i,
            "body": "\n".join(lines[i + 1:end]),
        })
    return out


def extract_dates(text: str, today: date) -> list[date]:
    """YYYY-MM-DD, M/D, M월 D일 표기의 날짜. M/D는 올해로 본다."""
    found = []
    limit = today + timedelta(days=FUTURE_SLACK_DAYS)

    def add(y, m, d):
        try:
            dt = date(int(y), int(m), int(d))
        except ValueError:
            return
        if dt <= limit:
            found.append(dt)

    for m in ISO_RE.finditer(text):
        add(*m.groups())
    for rx in (MD_RE, KO_RE):
        for m in rx.finditer(text):
            add(today.year, *m.groups())
    return found


def open_markers(text: str) -> list[str]:
    return sorted(set(OPEN_RE.findall(text)))


def classify(section: dict, today: date) -> dict:
    """결정적 분류. bucket: recent | candidate | ambiguous."""
    full = section["title"] + "\n" + section["body"]
    dates = extract_dates(full, today)
    latest = max(dates) if dates else None
    marks = open_markers(full)
    if latest is None:
        bucket, why = "ambiguous", "날짜 없음"
    elif (today - latest).days <= STALE_DAYS:
        bucket, why = "recent", f"최근 날짜 {latest} (7일 이내)"
    elif marks:
        bucket, why = "ambiguous", f"열린 표시 있음({', '.join(marks)})"
    else:
        bucket, why = "candidate", f"최근 날짜 {latest}, 열린 표시 없음"
    return {**section, "latest": latest, "markers": marks, "bucket": bucket, "why": why}


SYSTEM = ("당신은 문서 정리 보조자다. 판정하지 않고 분류 초안만 낸다. "
          "주어진 발췌 밖의 내용을 지어내지 않는다. 한국어로 답한다.")


def _cut(s: str) -> str:
    return s if len(s) <= 160 else s[:160] + "..."


def build_prompt(sec: dict, today: date) -> str:
    body_lines = [l.strip() for l in sec["body"].split("\n") if l.strip()]
    marked = [l for l in body_lines if OPEN_RE.search(l)][:6]
    head = body_lines[:8]
    return (
        f"오늘은 {today}이다. 아래는 진행상황 문서의 한 절이다. 이 절을 아카이브(옛 기록 보관함)로 "
        f"옮겨도 되는 후보인지 분류하라.\n"
        f"기준: 오래됐고 일이 끝났으면 후보, 아직 할 일·대기·열린 요청이 남아 있으면 유지, 발췌만으로 "
        f"알 수 없으면 모름.\n\n"
        f"절 제목: {sec['title']}\n줄 수: {sec['line_count']}\n"
        f"본문에서 찾은 가장 최근 날짜: {sec['latest'] or '없음'}\n"
        f"본문 첫 줄들:\n" + "\n".join("  " + _cut(l) for l in head) + "\n"
        f"열린 표시가 들어간 줄:\n" + ("\n".join("  " + _cut(l) for l in marked) or "  (없음)") + "\n\n"
        f"정확히 두 줄로만 답하라.\n분류: 아카이브 후보 또는 유지 또는 모름 중 하나\n이유: 한 줄"
    )


VERDICT_RE = re.compile(r"분류\s*[:：]\s*(아카이브 후보|유지|모름)")
REASON_RE = re.compile(r"이유\s*[:：]\s*(.+)")


def parse_verdict(text: str) -> tuple[str, str]:
    v = VERDICT_RE.search(text)
    r = REASON_RE.search(text)
    if not v:
        return "형식 오류", text.strip().replace("\n", " ")[:120]
    return v.group(1), (r.group(1).strip() if r else "")


def esc(s: str) -> str:
    return s.replace("|", "\\|")


def render(model: str, today: date, results: list[dict], llm_rows: list[dict]) -> str:
    cand = [r for r in results if r["bucket"] == "candidate"]
    recent = [r for r in results if r["bucket"] == "recent"]
    amb = [r for r in results if r["bucket"] == "ambiguous"]
    L = [
        f"# 진행상황.md 아카이브 후보 ({today})", "",
        "- **초안, 판정 아님.** 사람이 확인하기 전에는 어떤 절도 옮기지 않는다. 원문은 수정하지 않았다.",
        f"- 생성 시각: {local_llm.now_kst()}",
        f"- 사용 모델: {model}",
        f"- LLM 호출 횟수: {local_llm.stats_line()}",
        f"- 원문: docs/진행상황.md (절 {len(results)}개, 절 줄 수 합계 {sum(r['line_count'] for r in results)}), 기준일 {today}, 오래됨 기준 {STALE_DAYS}일 초과",
        f"- 결정적 후보 {len(cand)}개 / 최근 유지 {len(recent)}개 / 애매(LLM 분류) {len(amb)}개", "",
        "## 1. 결정적 후보 (코드 판별: 7일 넘게 지남 + 열린 표시 없음)", "",
        "| 시작 줄 | 줄 수 | 최근 날짜 | 절 제목(원문) |", "|---|---|---|---|",
    ]
    for r in cand:
        L.append(f"| {r['start']} | {r['line_count']} | {r['latest']} | {esc(r['title'])} |")
    if not cand:
        L.append("| - | - | - | (없음) |")
    L += ["", "## 2. 애매한 절의 LLM 분류 (초안)", "",
          "| 시작 줄 | 줄 수 | 결정적 사유 | LLM 분류 | LLM 이유 | 절 제목(원문) |", "|---|---|---|---|---|---|"]
    for r in llm_rows:
        L.append(f"| {r['start']} | {r['line_count']} | {esc(r['why'])} | {r['verdict']} | {esc(r['reason'])} | {esc(r['title'])} |")
    if not llm_rows:
        L.append("| - | - | - | - | - | (없음) |")
    skipped = [r for r in amb if "verdict" not in r]
    if skipped:
        L += ["", f"LLM 호출 상한으로 분류하지 않은 애매한 절 {len(skipped)}개:", ""]
        L += [f"- 줄 {r['start']}: {r['title']} ({r['why']})" for r in skipped]
    L += ["", "## 3. 최근 7일 이내라 유지 (LLM 미호출)", ""]
    L += [f"- 줄 {r['start']} ({r['latest']}): {r['title']}" for r in recent] or ["- (없음)"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=None, help="기준일 YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--source", default=str(SOURCE))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--max-llm", type=int, default=80, help="LLM 호출 상한(절 수)")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(local_llm.KST).date()

    text = Path(a.source).read_text(encoding="utf-8")
    results = [classify(s, today) for s in parse_sections(text)]
    amb = [r for r in results if r["bucket"] == "ambiguous"]

    model = local_llm.pick_model()
    llm_rows = []
    for n, r in enumerate(amb[:a.max_llm], 1):
        try:
            verdict, reason = parse_verdict(local_llm.chat(build_prompt(r, today), SYSTEM, model=model))
        except local_llm.LLMError as e:
            verdict, reason = "LLM 실패", str(e)[:100]
        r["verdict"], r["reason"] = verdict, reason
        llm_rows.append(r)
        print(f"[{n}/{min(len(amb), a.max_llm)}] {verdict}: {r['title'][:40]}", flush=True)

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"archive-candidates-{today}.md"
    path.write_text(render(model, today, results, llm_rows), encoding="utf-8")
    print(f"저장: {path} ({path.stat().st_size} bytes), LLM 호출 {local_llm.stats_line()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
