"""주간 변경 요약 초안 (초안, 판정 아님).

무엇인가
--------
최근 7일 커밋 제목(PR 번호 포함)을 접두어(feat, fix, docs, chore...)로 묶고, 묶음별 한두 문장
요약과 감시 상태판(C:\\work\\_ops\\STATUS.md)의 현재 상태 요약을
C:\\work\\_ops\\weekly\\change-summary-<날짜>.md 로 만든다.

왜 이렇게 설계했나 (코드로 할 수 있는 것은 코드로, LLM은 꼭 필요한 곳만)
--------------------------------------------------------------------
- 커밋 수집(git log), 접두어 묶기, 봇 커밋 분리·집계, PR 번호 추출, 상태판 표 파싱은 결정적 코드.
- LLM은 "이 커밋 제목 묶음이 무엇을 바꿨나"를 한두 문장으로 옮겨 쓰는 일과, 상태판의
  문제 행을 두 문장으로 옮겨 쓰는 일만 한다. 제목에 없는 내용을 추측하지 않게 지시한다.
- 근거 해시와 PR 번호는 LLM이 아니라 코드가 각 요약 끝에 그대로 붙인다(없는 해시를 지어낼 수 없다).
  LLM 답에 묶음에 없는 해시 모양 문자열이 있으면 지운다.
- 봇 커밋("자동 수집/기록", [skip ci])은 요약하지 않고 개수만 센다.
- LLM 실패는 그 묶음만 "LLM 실패"로 표기하고 해시 목록은 그대로 남긴다.
- 인터넷(gh 등)은 쓰지 않는다. PR 제목은 커밋 제목의 (#번호)로만 안다.
"""
import argparse
import re
import subprocess
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_llm  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = Path(r"C:\work\_ops\weekly")
STATUS = Path(r"C:\work\_ops\STATUS.md")
CHUNK = 25          # 한 번에 LLM에 보내는 커밋 제목 수
SUBJECT_MAX = 140   # 제목 길이 상한(프롬프트 크기 제한)

# 영문(feat, fix, docs)뿐 아니라 이 저장소가 쓰는 한글·파일명 접두어("마야:", "진행상황:")도 묶음 이름으로 쓴다
PREFIX_RE = re.compile(r"^([^\s:(]{1,20})(\([^)]*\))?!?:")
BOT_RE = re.compile(r"\[skip ci\]|자동 (수집|기록)")
PR_RE = re.compile(r"\(#(\d+)\)")
HASH_RE = re.compile(r"\b[0-9a-f]{7,10}\b")


def git_log(days: int = 7, repo: Path = REPO) -> list[str]:
    r = subprocess.run(
        ["git", "-c", "core.quotepath=off", "log", f"--since={days} days ago",
         "--pretty=format:%h %s"],
        cwd=repo, capture_output=True, encoding="utf-8", errors="replace", check=True)
    return [l for l in r.stdout.split("\n") if l.strip()]


def split_commit(line: str) -> tuple[str, str]:
    h, _, subj = line.partition(" ")
    return h, subj


def is_bot(subject: str) -> bool:
    return bool(BOT_RE.search(subject))


def prefix_of(subject: str) -> str:
    m = PREFIX_RE.match(subject)
    return m.group(1) if m else "접두어 없음"


def group_commits(lines: list[str]) -> tuple["OrderedDict[str, list[tuple[str, str]]]", list[tuple[str, str]]]:
    """(접두어별 사람 커밋 묶음(많은 순), 봇 커밋 목록)."""
    groups: dict[str, list] = {}
    bots = []
    for ln in lines:
        h, s = split_commit(ln)
        if is_bot(s):
            bots.append((h, s))
        else:
            groups.setdefault(prefix_of(s), []).append((h, s))
    ordered = OrderedDict(sorted(groups.items(), key=lambda kv: -len(kv[1])))
    return ordered, bots


def bot_patterns(bots: list[tuple[str, str]], top: int = 5) -> list[tuple[str, int]]:
    """봇 제목에서 날짜·괄호 안 내용을 지워 같은 종류끼리 센다."""
    norm = Counter(re.sub(r"\([^)]*\)|\d{4}-\d\d-\d\d", "", s).strip() for _, s in bots)
    return norm.most_common(top)


def chunks(items: list, n: int = CHUNK):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def scrub_hashes(text: str, allowed: set[str]) -> str:
    """LLM 답에서 묶음에 없는 해시 모양 문자열을 지운다."""
    return HASH_RE.sub(lambda m: m.group(0) if m.group(0) in allowed else "", text).strip()


SYSTEM = ("당신은 변경 이력 요약 보조자다. 판정이나 평가를 하지 않는다. "
          "주어진 목록에 없는 내용을 추측하지 않는다. 한국어로 답한다.")


def commit_prompt(prefix: str, batch: list[tuple[str, str]]) -> str:
    lines = "\n".join("- " + (s if len(s) <= SUBJECT_MAX else s[:SUBJECT_MAX] + "...") for _, s in batch)
    return (f"아래는 저장소에서 최근 7일 동안 '{prefix}' 종류로 분류된 커밋 제목 {len(batch)}개다.\n"
            f"무엇이 바뀌었는지 한두 문장으로 요약하라. 목록에 없는 내용은 쓰지 말고, 커밋 해시는 쓰지 마라.\n"
            f"요약 문장만 출력하라.\n\n{lines}")


def parse_status(text: str) -> dict:
    """상태판의 머리줄, 요약줄, 행 목록을 뽑는다. 행: (상태, 항목, 내용)."""
    lines = text.split("\n")
    head = lines[0].lstrip("# ").strip() if lines else ""
    summary = next((l.strip().strip("*").strip() for l in lines[1:6] if l.strip().startswith("**")), "")
    rows = []
    for l in lines:
        if l.startswith("|") and l.count("|") >= 4:
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if cells[0] in ("🔴", "🟡", "🟢", "⚪"):
                rows.append((cells[0], cells[1], cells[2]))
    return {"head": head, "summary": summary, "rows": rows}


def status_prompt(st: dict) -> str:
    probs = [r for r in st["rows"] if r[0] in ("🔴", "🟡", "⚪")]
    body = "\n".join(f"- {s} {name}: {msg[:140]}" for s, name, msg in probs) or "- (문제 행 없음)"
    return (f"아래는 감시 상태판의 요약줄과 문제·대기 행이다. 현재 상태를 두 문장으로 요약하라. "
            f"목록에 없는 원인이나 해결책을 추측하지 마라. 요약 문장만 출력하라.\n\n"
            f"요약줄: {st['summary']}\n{body}")


def one_call(prompt: str, model: str) -> str:
    try:
        return local_llm.chat(prompt, SYSTEM, model=model).replace("\n", " ")
    except local_llm.LLMError as e:
        return f"LLM 실패 ({str(e)[:80]})"


def evidence(batch: list[tuple[str, str]]) -> str:
    prs = sorted({int(n) for _, s in batch for n in PR_RE.findall(s)})
    pr_txt = (" / PR " + ", ".join(f"#{n}" for n in prs)) if prs else ""
    return "근거: " + " ".join(h for h, _ in batch) + pr_txt


def render(model: str, today: date, total: int, groups, bots, status: dict | None,
           status_text: str, blocks: list[tuple[str, str, list]], status_sum: str) -> str:
    human = sum(len(v) for v in groups.values())
    L = [
        f"# 주간 변경 요약 ({today})", "",
        "- **초안, 판정 아님.** 요약 문장은 로컬 LLM이 커밋 제목을 옮겨 쓴 것이고, 근거 해시·PR 번호는 코드가 붙였다.",
        f"- 생성 시각: {local_llm.now_kst()}",
        f"- 사용 모델: {model}",
        f"- LLM 호출 횟수: {local_llm.stats_line()}",
        f"- 범위: 최근 7일 커밋 {total}건 = 사람 커밋 {human}건 + 봇 커밋 {len(bots)}건(개수만 집계)",
        "- 접두어별 건수: " + ", ".join(f"{k} {len(v)}" for k, v in groups.items()), "",
        "## 1. 커밋 묶음별 요약", "",
    ]
    cur = None
    for prefix, summary, batch in blocks:
        if prefix != cur:
            L += [f"### {prefix} ({len(groups[prefix])}건)", ""]
            cur = prefix
        L += [f"- {summary}", f"  - {evidence(batch)}"]
    L += ["", "## 2. 봇 커밋 (요약하지 않고 개수만)", "", f"- 총 {len(bots)}건"]
    L += [f"- {n}건: {p}" for p, n in bot_patterns(bots)]
    L += ["", "## 3. 감시 상태판 현재 상태", ""]
    if status is None:
        L.append(f"- 상태판을 읽지 못함: {status_text}")
    else:
        L += [f"- 원문 머리줄: {status['head']}", f"- 원문 요약줄: {status['summary']}",
              f"- 요약(LLM 초안): {status_sum}", "- 문제·대기 행(원문):"]
        probs = [r for r in status["rows"] if r[0] in ("🔴", "🟡", "⚪")]
        L += [f"  - {s} {name}: {msg[:200]}" for s, name, msg in probs] or ["  - (없음)"]
        cnt = Counter(r[0] for r in status["rows"])
        L.append("- 행 수: " + ", ".join(f"{k} {v}" for k, v in cnt.items()))
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=None)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--status", default=str(STATUS))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(local_llm.KST).date()

    lines = git_log(a.days)
    groups, bots = group_commits(lines)
    model = local_llm.pick_model()

    blocks = []
    total_batches = sum(len(list(chunks(v))) for v in groups.values())
    n = 0
    for prefix, items in groups.items():
        for batch in chunks(items):
            n += 1
            summary = one_call(commit_prompt(prefix, batch), model)
            summary = scrub_hashes(summary, {h for h, _ in batch})
            blocks.append((prefix, summary, batch))
            print(f"[{n}/{total_batches}] {prefix} {len(batch)}건: {summary[:50]}", flush=True)

    status, status_text, status_sum = None, "", ""
    try:
        status_text = Path(a.status).read_bytes().decode("utf-8", errors="replace")
        status = parse_status(status_text)
        status_sum = one_call(status_prompt(status), model)
    except OSError as e:
        status_text = str(e)

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"change-summary-{today}.md"
    path.write_text(render(model, today, len(lines), groups, bots, status, status_text, blocks, status_sum),
                    encoding="utf-8")
    print(f"저장: {path} ({path.stat().st_size} bytes), LLM 호출 {local_llm.stats_line()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
