# -*- coding: utf-8 -*-
"""컨텍스트 감수 판정 실행기(2026-10-15 탐, 사장님: "옮기는 사람이 없었다 → 전체를 보는 에이전트가 옮기거나 수정하게 해야 한다").
감수 에이전트(context_audit.py, 오퍼스)가 판정 파일(a2_*.md)의 'B0. 혼란 정보 판정 > 숨김'에 적은 공정 카드를
실제로 1차 검색에서 내린다(proc.py retire와 같은 '숨김', 내용·이력은 보존). 판정과 실행 사이에 사람 손을 두지 않는다.
안전: 한 번에 최대 MAX장, 이미 숨김이면 건너뜀, 실행마다 이전 상태를 apply_log.jsonl에 남기고 --undo로 그 실행 전체를 되돌린다.
숨김 항목 형식(감수 프롬프트가 지키게 함): "- 카드[, 카드]: 이유"  (콜론 앞의 '이름#번호'만 대상, 콜론 뒤의 정본 번호는 대상 아님)
사용:
  python scripts/ops/context_apply.py [판정파일] [--dry]     기본 = 가장 최근 a2_*.md
  python scripts/ops/context_apply.py --undo <run_id>        그 실행에서 숨긴 카드를 원래 상태로"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
DIR = Path("C:/work/_ops/context_audit")
LOG = DIR / "apply_log.jsonl"
MAX = 10
REF = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z0-9\-]*)#(\d+)")


def hide_refs(text):
    """판정 파일에서 B0의 숨김 목록만 뽑는다."""
    m = re.search(r"##\s*B0\.(.*?)(?=\n##\s|\Z)", text, re.S)
    if not m:
        return []
    refs, on = [], False
    for ln in m.group(1).splitlines():
        s = ln.strip()
        if s.startswith("**"):
            on = s.startswith("**숨김")
            continue
        if on and s.startswith("-"):
            head = s[1:].split(":", 1)[0]
            refs += [(p, int(n)) for p, n in REF.findall(head)]
    out = []
    for r in refs:
        if r not in out:
            out.append(r)
    return out


def apply(path, dry=False):
    import opsdb
    refs = hide_refs(Path(path).read_text(encoding="utf-8"))[:MAX]
    run = time.strftime("%Y%m%d_%H%M%S")
    done = []
    for proc, no in refs:
        rs = opsdb.select("tasks", "id,status,title,raw", where={"section": "eq.step", "owner": f"eq.{proc}", "no": f"eq.{no}"}, limit=1)
        if not rs or rs[0]["status"] == "숨김":
            continue
        r = rs[0]
        if not dry:
            raw = dict(r["raw"] or {})
            raw["retired"] = {"why": f"컨텍스트 감수 판정 {Path(path).name}", "at": time.strftime("%F %T"), "by": "감수 에이전트"}
            opsdb.patch("tasks", {"id": f"eq.{r['id']}"}, {"status": "숨김", "raw": raw})
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"run": run, "id": r["id"], "card": f"{proc}#{no}", "prev": r["status"], "src": str(path)}, ensure_ascii=False) + "\n")
        done.append(f"{proc}#{no} {r['title'][:50]}")
    return run, refs, done


def undo(run):
    import opsdb
    n = 0
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        e = json.loads(ln)
        if e["run"] == run:
            opsdb.patch("tasks", {"id": f"eq.{e['id']}"}, {"status": e["prev"]})
            n += 1
    print(f"되돌림: 실행 {run}의 카드 {n}장")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if a[:1] == ["--undo"]:
        return undo(a[1])
    files = [x for x in a if not x.startswith("--")]
    path = files[0] if files else max(DIR.glob("a2_*.md"), key=lambda p: p.stat().st_mtime, default=None)
    if not path:
        print("감수 실행: 판정 파일 없음")
        return 0
    run, refs, done = apply(path, dry="--dry" in a)
    tag = "(시험)" if "--dry" in a else f"(실행 {run}, 되돌리기: --undo {run})"
    print(f"감수 실행{tag}: 판정 숨김 {len(refs)}장 중 {len(done)}장 내림 " + " / ".join(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
