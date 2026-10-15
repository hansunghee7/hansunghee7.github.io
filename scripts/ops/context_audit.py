# -*- coding: utf-8 -*-
"""컨텍스트 감수 에이전트 v0(2026-10-15 탐, 사장님: "우리 컨텍스트만 관리하는 전문 에이전트를 두고, 우리 에이전트의 오류·실수를 감지해 문서나 DB를 개선").
하는 일(제안 전용): 최근 N시간의 마찰 기록(훅 차단, 사람 개입 표시, 권한 거절, 목표 재질문 관문)을 모아 집계하고,
Claude API(api_run.py, 프로모션 크레딧)로 '반복되는 실수 → 원인이 된 문서·규칙·DB → 고칠 제안 한 줄'을 뽑아 파일로 남긴다.
하지 않는 일: 문서·DB·훅을 직접 고치지 않는다(덱스·비티 의견 10/15: 제안만 하고 승인 뒤 반영, 근거 표시, 되돌릴 수 있게). 반영은 탐이 PR로.
비밀값 보호: 명령 원문에 key·token·secret·password·Bearer 같은 말이 있으면 그 줄은 보내지 않는다.
산출: C:/work/_ops/context_audit/YYYYMMDD_HHMM.md (집계표 + 모델 제안). 실패하면 종료 코드 1.
사용: python scripts/ops/context_audit.py [--hours 24] [--model claude-sonnet-5-5] [--dry]"""
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
    rf.write_text(f"# 컨텍스트 감수 {stamp} (최근 {hours}시간, 기록 {total}건, 제안 전용)\n\n## 모델 제안\n{af.read_text(encoding='utf-8')}\n\n## 집계\n{summary}\n", encoding="utf-8")
    print(f"컨텍스트 감수 완료: {rf} (기록 {total}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
