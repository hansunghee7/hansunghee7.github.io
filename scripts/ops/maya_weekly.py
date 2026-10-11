# -*- coding: utf-8 -*-
"""마야 주간 점검(슈퍼얼라인 적용, 2026-10-11). 작업 스케줄러 「마야_주간점검」(토 09:00)이 실행한다.
한 번에 세 가지를 확인해 C:/work/_ops/maya_weekly.md 에 쓴다(사람이 읽는 주간 보고에 그대로 붙임).
  1) 슈퍼얼라인 점검(align_check.py 마야) 결과
  2) 사장님 응답 없이 7일 넘게 '대기'인 제안(maya_proposals.jsonl) 개수와 제목
  3) 글 단계표(maya_stages.py)의 빈칸 개수
FAIL이 하나라도 있으면 종료 코드 1(감시 대장이 보는 건 결과 파일의 갱신 시각).
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.stdout is not None:  # pythonw(스케줄러)는 stdout이 없다. 첫 자동 실행 시험에서 이 줄이 죽었다(10/11)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
OUT = Path("C:/work/_ops/maya_weekly.md")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


PY = sys.executable.replace("pythonw.exe", "python.exe")  # 자식은 콘솔 파이썬으로(출력 포획)


def run(args):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NOWIN)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def old_pending():
    p = ROOT / "assets" / "data" / "maya_proposals.jsonl"
    rows, cut = [], datetime.now() - timedelta(days=7)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        try:
            at = datetime.strptime(d["at"], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if d.get("boss") == "대기" and at < cut:
            rows.append(d["title"])
    return rows


def main():
    rc, align = run(["scripts/ops/align_check.py", "마야"])
    pend = old_pending()
    _, stages = run(["scripts/ops/maya_stages.py"])
    blanks = sum(line.count("| - ") for line in stages.splitlines()[2:])
    body = [f"# 마야 주간 점검 ({datetime.now():%Y-%m-%d %H:%M} 자동 생성, scripts/ops/maya_weekly.py)", "",
            "## 1. 슈퍼얼라인", align.strip(), "",
            f"## 2. 7일 넘게 응답 없는 제안: {len(pend)}건"] + [f"- {t}" for t in pend] + [
            "", f"## 3. 글 단계표 빈칸: {blanks}개(maya_stages.py 표 기준)", "",
            "## 한계", "있는가를 확인하며, 제안이 정직한지·이미지 채점이 맞는지는 사람이 샘플로 본다."]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    if sys.stdout is not None:
        print(f"wrote {OUT} align_rc={rc} old_pending={len(pend)} blanks={blanks}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
