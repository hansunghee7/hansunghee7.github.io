"""타미 실패 라우팅: solar-bible/reports/*-result.md 의 '## 결과' 절에서 실패 신호를 찾아 다음 갈래(Vertex)를 권장한다.

실패면 _ops/tami_failures.jsonl 에 한 줄 + 탐 우편함에 한 통(--dry 면 출력만). 처리한 파일명은 상태 파일에 기록(중복 방지).
"""
import argparse, json, re, subprocess, sys
from datetime import datetime
from pathlib import Path

REPORTS = Path("C:/work/solar-bible/reports")
STATE = Path("C:/work/_ops/tami_router_state.json")
FAILS = Path("C:/work/_ops/tami_failures.jsonl")
MAILBOX = "C:/work/solar-bible/mailbox/mailbox.py"
NEXT = ("GCP Vertex (ask_vertex.py, 핏#52 4단계)", "타미는 3단계라 실패하면 4단계부터")
NEG = re.compile(r"(성공\s*/\s*실패|(막힌 곳|막힘|실패|오류|에러|failure)\s*[:：]?\s*(없음|없다|없었|0\s*건?\b|0\b)|실패\s*0|막힌 곳 없|실패(시|하면|할 경우)|rc\s*=\s*0|관문 막힘)", re.I)
SIG = [("rc/exit", re.compile(r"(rc\s*=\s*|exit[ _]code\s*[:=]?\s*)([1-9]\d*)", re.I)),
       ("실패", re.compile(r"실패|failure|failed", re.I)), ("막힘", re.compile(r"막힘|막혔|3분 넘게")),
       ("권한", re.compile(r"권한\s*(거부|없|부족|오류)|permission denied", re.I)), ("timeout", re.compile(r"timeout|timed out|시간 초과", re.I))]
OKLINE = re.compile(r"막힌 곳\s*[:：]?\s*없|막힌 곳 없")


def result_text(md):
    out, on = [], False
    for ln in md.splitlines():
        if ln.startswith("## "):
            on = ln.startswith("## 결과")
            continue
        if on:
            out.append(ln)
    return "\n".join(out)


def detect(md):
    """실패면 (신호이름, 인용 한 줄), 아니면 None."""
    m = re.search(r"exit code:\s*(\d+)", md)
    if m and int(m.group(1)) >= 1:
        return "exit code", f"메타 exit code: {m.group(1)}"
    res = result_text(md)
    if OKLINE.search(res):  # 명시적 '막힌 곳: 없음' 이면 보고서가 성공으로 끝난 것(진단 결과에 실패 단어가 들어갈 수 있음)
        return next(((n, ln.strip()[:160]) for ln in res.splitlines() for n, r in SIG[:1] if r.search(NEG.sub("", ln))), None)
    for ln in res.splitlines():
        if ln.lstrip().startswith(("|", ">", '"')):  # 표·인용은 남의 문장
            continue
        clean = NEG.sub("", ln)
        for name, rx in SIG:
            if rx.search(clean):
                return name, ln.strip()[:160]
    return None


def mail(name, quote, dry):
    title = f"타미 실패 라우팅: {name}"
    body = f"결과 파일: {name}\n실패 신호: {quote}\n권장 다음 갈래: {NEXT[0]}\n이유: {NEXT[1]}\n기록: {FAILS}"
    if dry:
        print(f"[DRY 우편] {title}\n{body}")
        return
    subprocess.run([sys.executable, MAILBOX, "send", "탐", title, "--body", body, "--from", "타미라우터"], check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def run(reports=REPORTS, state=STATE, fails=FAILS, dry=False):
    done = set(json.loads(state.read_text(encoding="utf-8"))) if state.exists() else None
    if done is None and not dry:  # 첫 실행: 쌓인 옛 결과는 알림 폭주를 막으려고 처리 완료로만 기록
        done = {f.name for f in Path(reports).glob("*-result.md")}
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
        print(f"첫 실행: 기존 {len(done)}건을 처리 완료로 기록(알림 없음)")
        return []
    done = done or set()
    found = []
    for f in sorted(Path(reports).glob("*-result.md")):
        if f.name in done:
            continue
        hit = detect(f.read_text(encoding="utf-8", errors="replace"))
        done.add(f.name)
        if not hit:
            continue
        found.append((f.name, hit))
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), "file": f.name, "signal": hit[1], "next": NEXT[0], "why": NEXT[1]}
        if not dry:
            fails.parent.mkdir(parents=True, exist_ok=True)
            with fails.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        mail(f.name, hit[1], dry)
    if not dry:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--reports", default=str(REPORTS))
    ap.add_argument("--state", default=str(STATE))
    a = ap.parse_args()
    r = run(Path(a.reports), Path(a.state), dry=a.dry)
    print(f"실패 판정 {len(r)}건: " + ", ".join(n for n, _ in r))
