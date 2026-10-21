#!/usr/bin/env python3
"""비티·덱스 아침 피드백(대장 N112, 2026-10-21 탐).

매일 아침 한 번: 어제와 비교해 바뀐 탐 열린 행만 모아 짧은 카드로 만들고, 비티(Vertex 제미나이 풀)와 덱스에게
"이 행들의 다음 행동에서 빠진 위험, 더 나은 순서 3줄"을 한 번씩 묻는다. 답은 파일로만 저장한다.
  결과: C:/work/_ops/morning_feedback/YYYY-MM-DD.md (카드·비티 답·덱스 답, 바뀐 행이 없으면 '없음' 기록만)
  실행 증거: C:/work/_ops/morning_feedback/last_run (시각·rc·호출 수, jobs.toml file_age 감시용)

원칙
  - 운영 DB는 읽기만 한다(opsdb.select). DB·메일·메신저에 쓰지 않는다.
  - 바뀐 행 기준: 운영 DB의 imported_at은 동기화 때마다 전부 갱신돼 변경 시각으로 못 쓴다. 그래서 행마다
    (제목·상태·다음 행동)의 해시를 state.json에 저장해 두고 어제와 다른 행·새 행만 '바뀐 행'으로 본다.
    첫 실행은 어제 기록이 없어 열린 행 전체가 후보이고, 20행 상한이 자른다(번호 큰 순).
  - 바뀐 행이 없으면 비티·덱스를 부르지 않는다(호출 낭비 방지).
  - 비밀·키 단어는 카드에서 가린다. 고객 정보·가격은 대장 행에 원래 없지만 단어 가림은 마지막 방어선이다.
  - 업무대장 관문(ledger_gate.sh)용 행은 상시 행 하나씩(비티 BT, 덱스 DX)을 ledger_row.py 절차로 한 번 만들고
    이후엔 같은 번호를 재사용한다(매일 대장 문서가 바뀌어 공용 메인 폴더가 더러워지는 것을 막는다).
사용: python scripts/ops/morning_feedback.py [--date YYYY-MM-DD] [--no-call]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OUT_DIR = Path("C:/work/_ops/morning_feedback")
BASH = r"C:\Program Files\Git\bin\bash.exe"
MAX_ROWS = 20
STANDING_TITLE = "아침 피드백 정기 작업(N112, 매일 08:30 morning_feedback.py가 카드를 보냄)"
STANDING_NEXT = "매일 바뀐 탐 열린 행을 카드로 받아 빠진 위험·더 나은 순서 3줄을 파일로 남긴다. 채택률은 탐이 달마다 점검"
SECRET_RE = re.compile(r"(api[_-]?key|token|password|secret|credential|sk-[A-Za-z0-9]+|비밀번호|비밀|토큰|패스워드|금고|자격증명|키 ?값)", re.I)
ASK = (
    "아래는 1인 회사의 업무대장에서 어제 바뀐 열린 행입니다. 행마다 '다음 행동'을 읽고 한국어로 정확히 3줄만 답하세요.\n"
    "1줄 = 다음 행동에서 빠진 위험, 2줄 = 더 나은 순서, 3줄 = 가장 먼저 할 한 가지(행 번호 포함).\n"
    "대장에 이미 적힌 말을 되풀이하지 말고, 근거 없는 숫자는 쓰지 마세요."
)


def mask(text):
    return SECRET_RE.sub("[가림]", text or "")


def one_line(text, n=140):
    return re.sub(r"\s+", " ", mask(text)).strip()[:n]


def row_hash(r):
    s = "|".join(str(r.get(k) or "") for k in ("title", "status", "next_action"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def num_key(r):
    m = re.search(r"\d+", r.get("no") or "")
    return int(m.group()) if m else -1


def fetch_open_rows():
    """운영 DB 읽기 전용: 탐 열린 행."""
    import opsdb
    return opsdb.select("tasks", "no,title,status,next_action", {"owner": "eq.탐", "section": "eq.open"}, "no.asc", 1000)


def changed_rows(rows, prev):
    return [r for r in rows if prev.get(r.get("no")) != row_hash(r)]


def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_card(rows, ledger_line, total_changed):
    rows = sorted(rows, key=num_key, reverse=True)[:MAX_ROWS]
    lines = [ledger_line, "", ASK, "", f"바뀐 행 {len(rows)}건(전체 변경 {total_changed}건, 상한 {MAX_ROWS}):"]
    for r in rows:
        lines.append(f"- {r.get('no')} | {one_line(r.get('title'), 80)} | {one_line(r.get('status'), 20)} | 다음: {one_line(r.get('next_action'))}")
    return "\n".join(lines) + "\n"


def ensure_standing_row(agent, docs=None):
    """상시 행 번호를 돌려준다. 없으면 ledger_row.add_row 절차로 만든다(문서 쓰기는 그때 한 번뿐)."""
    import ledger_row
    docs = Path(docs) if docs else ledger_row.DOCS
    pfx, name = ledger_row.CFG[agent]
    text = (docs / name).read_text(encoding="utf-8")
    m = re.search(rf"^###\s*\[[^\]]*\]\s*({pfx}\d+):\s*{re.escape(STANDING_TITLE)}", text, re.M)
    if m:
        return m.group(1)
    return ledger_row.add_row(agent, STANDING_TITLE, STANDING_NEXT, "진행", docs=docs)


def _run_ask(script, card, out, env_extra):
    env = {**os.environ, **env_extra}
    r = subprocess.run([BASH, str(HERE / script).replace("\\", "/"), str(card).replace("\\", "/"), str(out).replace("\\", "/")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900,
                       stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        reply = Path(out).read_text(encoding="utf-8", errors="replace")
    except OSError:
        reply = ""
    return r.returncode, reply


def call_bt(card, out):
    return _run_ask("ask_bt.sh", card, out, {"BT_MODEL": "vertex"})


def call_dex(card, out):
    return _run_ask("ask_dex.sh", card, out, {})


def run(date, fetch=fetch_open_rows, bt=call_bt, dex=call_dex, ensure=ensure_standing_row, out_dir=OUT_DIR, no_call=False):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "state.json"
    prev = load_state(state_path)
    rows = fetch()
    changed = changed_rows(rows, prev)
    result_path = out_dir / f"{date}.md"
    calls = 0
    rc = 0
    if not changed:
        result_path.write_text(f"# 비티·덱스 아침 피드백 {date}\n\n바뀐 행: 없음 (호출 0회)\n", encoding="utf-8")
    else:
        card_path = out_dir / f"{date}_card.md"
        shown = sorted(changed, key=num_key, reverse=True)[:MAX_ROWS]
        sections = [f"# 비티·덱스 아침 피드백 {date}\n"]
        if no_call:
            card = build_card(changed, "업무대장: BT0", len(changed))
            card_path.write_text(card, encoding="utf-8")
            sections += ["(--no-call: 카드만 저장)\n", "## 카드\n", card]
        else:
            for label, agent, fn, pfx in (("비티", "bt", bt, "BT"), ("덱스", "dex", dex, "DX")):
                rid = ensure(agent)
                card = build_card(changed, f"업무대장: {rid}", len(changed))
                cp = out_dir / f"{date}_card_{agent}.md"
                cp.write_text(card, encoding="utf-8")
                op = out_dir / f"{date}_{agent}_reply.md"
                code, reply = fn(cp, op)
                calls += 1
                if code != 0:
                    rc = 1
                sections.append(f"## {label} (rc={code})\n\n{mask(reply).strip() or '(답 없음)'}\n")
            sections.insert(1, f"바뀐 행 {len(shown)}건 표시(전체 변경 {len(changed)}건). 호출 {calls}회.\n")
            sections.append("## 카드(비티·덱스에게 보낸 내용)\n\n" + card)
        result_path.write_text("\n".join(sections), encoding="utf-8")
    state_path.write_text(json.dumps({r.get("no"): row_hash(r) for r in rows}, ensure_ascii=False), encoding="utf-8")
    (out_dir / "last_run").write_text(f"{datetime.datetime.now():%F %T} rc={rc} calls={calls} changed={len(changed)}\n", encoding="utf-8")
    return {"path": str(result_path), "calls": calls, "changed": len(changed), "rc": rc}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--no-call", action="store_true")
    a = ap.parse_args(argv)
    res = run(a.date, no_call=a.no_call)
    print(json.dumps(res, ensure_ascii=False))
    return res["rc"]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
