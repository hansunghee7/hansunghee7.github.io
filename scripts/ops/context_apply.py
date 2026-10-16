# -*- coding: utf-8 -*-
"""컨텍스트 감수 판정 실행기(2026-10-15 탐, 사장님: "옮기는 사람이 없었다 → 전체를 보는 에이전트가 옮기거나 수정하게 해야 한다").
감수 에이전트(context_audit.py, 오퍼스)가 판정 파일(a2_*.md)의 'B0. 혼란 정보 판정 > 숨김'에 적은 공정 카드를
실제로 1차 검색에서 내린다(proc.py retire와 같은 '숨김', 내용·이력은 보존). 판정과 실행 사이에 사람 손을 두지 않는다.
안전: 한 번에 최대 MAX장, 이미 숨김이면 건너뜀, 실행마다 이전 상태를 apply_log.jsonl에 남기고 --undo로 그 실행 전체를 되돌린다.
숨김 항목 형식(감수 프롬프트가 지키게 함): "- 카드[, 카드]: 이유"  (콜론 앞의 '이름#번호'만 대상, 콜론 뒤의 정본 번호는 대상 아님)
고쳐 쓰기(사장님 10/15 "감수 에이전트가 하이쿠나 소넷 서브에이전트로 실행까지"): 판정 파일 끝 ```actions 블록의 rewrite 지시마다
소넷(api_run.py)이 카드 제목·할 일만 고친 JSON을 내고, 실행기가 검사(제목 1~200자, 사장님 원문 칸은 건드리지 않음) 뒤 반영한다. 하루 최대 REWRITE_MAX건, 이전 값은 로그와 카드 이력에 남는다.
사용:
  python scripts/ops/context_apply.py [판정파일] [--dry]     기본 = 가장 최근 a2_*.md
  python scripts/ops/context_apply.py --supersede <새 결정 id> <옛 결정 id...> --why "이유"   사장님 결정 원장 대체 표시(옛 결정은 1차 검색에서 빠짐)
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
REWRITE_MAX = 5
WORKER = "claude-sonnet-5-5"
REF = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z0-9\-]*)#(\d+)")


def actions(text):
    """판정 파일 끝의 ```actions JSON 블록."""
    m = re.search(r"```actions\s*(\[.*?\])\s*```", text, re.S)
    if not m:
        return []
    try:
        acts = json.loads(m.group(1))
    except ValueError:
        return []
    ok = []
    for x in acts:
        if not isinstance(x, dict) or not REF.fullmatch(str(x.get("card", ""))):
            continue
        if x.get("op") == "rewrite" and x.get("instruction"):
            ok.append(x)
        # 기한 칸 채우기(10/16 사장님: 기한 넘은 열린 일을 세션 시작 맨 위에) — 사장님 원문에 기한이 있는데 칸이 빈 카드
        elif x.get("op") == "due" and re.fullmatch(r"20\d\d-\d\d-\d\d", str(x.get("due", ""))):
            ok.append(x)
    return ok


def worker_rewrite(card, instruction):
    """소넷 실행 담당: 카드 하나를 지시대로 고친 {"title","do"}를 받는다. 실패하면 None."""
    import subprocess
    import tempfile
    q = Path(tempfile.mkdtemp()) / "q.md"
    q.write_text(f"""너는 공정 카드 정리 담당이다. 감수 에이전트의 지시대로 카드 하나만 고친다.
규칙: 새 사실을 만들지 않는다. 지시에 없는 규칙을 바꾸지 않는다. 사장님 원문은 건드리지 않는다(입력에도 없다). 제목은 200자 이내 한 줄.
출력은 JSON 한 줄만: {{"title": "...", "do": "..."}}

지시: {instruction}
현재 제목: {card['title']}
현재 할 일: {card.get('next_action') or ''}
""", encoding="utf-8")
    o = q.with_name("a.md")
    r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "api_run.py"), "--who", "컨텍스트감수-실행", "--model", WORKER,
                        "--prompt-file", str(q), "--max-tokens", "1500", "--out", str(o)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not o.exists():
        return None
    m = re.search(r"\{.*\}", o.read_text(encoding="utf-8"), re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        return None
    if not d or not isinstance(d.get("title"), str) or not (1 <= len(d["title"].strip()) <= 200):
        return None
    return {"title": d["title"].strip(), "do": str(d.get("do") or "")[:600]}


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
    fixed = []
    for act in actions(Path(path).read_text(encoding="utf-8"))[:REWRITE_MAX]:
        proc, no = REF.fullmatch(act["card"]).groups()
        rs = opsdb.select("tasks", "id,status,title,next_action,raw", where={"section": "eq.step", "owner": f"eq.{proc}", "no": f"eq.{no}"}, limit=1)
        if not rs or rs[0]["status"] == "숨김":
            continue
        r = rs[0]
        if dry:
            fixed.append(f"{act['card']}(시험)")
            continue
        if act["op"] == "due":
            raw = dict(r["raw"] or {})
            prev = raw.get("due")
            raw["due"] = act["due"]
            opsdb.patch("tasks", {"id": f"eq.{r['id']}"}, {"raw": raw})
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"run": run, "id": r["id"], "card": act["card"], "op": "due", "prev_due": prev, "due": act["due"], "src": str(path)}, ensure_ascii=False) + "\n")
            fixed.append(f"{act['card']}(기한 {act['due']})")
            continue
        new = worker_rewrite(r, act["instruction"])
        if not new:
            continue
        raw = dict(r["raw"] or {})
        raw["history"] = (raw.get("history") or [])[-9:] + [{"title": r["title"], "do": r.get("next_action"), "at": time.strftime("%F %T"), "by": "감수 에이전트(소넷 실행)"}]
        opsdb.patch("tasks", {"id": f"eq.{r['id']}"}, {"title": new["title"], "next_action": new["do"], "raw": raw})
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run": run, "id": r["id"], "card": act["card"], "op": "rewrite", "prev_title": r["title"], "prev_do": r.get("next_action"), "src": str(path)}, ensure_ascii=False) + "\n")
        fixed.append(act["card"])
    return run, refs, done, fixed


def supersede(new_id, old_ids, why="", dry=False):
    """사장님 결정 원장(section=boss): 새 결정이 옛 결정을 대체함을 표시한다. 옛 행은 기억 도우미 1차에서 빠지고 원장에는 남는다."""
    import opsdb
    run = time.strftime("%Y%m%d_%H%M%S")
    new = opsdb.select("tasks", "id,raw", where={"section": "eq.boss", "id": f"eq.{new_id}"}, limit=1)
    if not new:
        print(f"대체 표시 실패: 새 결정 {new_id} 없음")
        return 1
    done = []
    for oid in old_ids:
        old = opsdb.select("tasks", "id,raw", where={"section": "eq.boss", "id": f"eq.{oid}"}, limit=1)
        if not old or dry:
            continue
        raw = dict(old[0]["raw"] or {})
        prev = raw.get("superseded_by")
        raw["superseded_by"] = new_id
        raw["superseded_why"] = why
        opsdb.patch("tasks", {"id": f"eq.{oid}"}, {"raw": raw})
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run": run, "id": oid, "op": "supersede", "prev_sup": prev, "new": new_id, "why": why}, ensure_ascii=False) + "\n")
        done.append(oid)
    if done:
        raw = dict(new[0]["raw"] or {})
        raw["supersedes"] = sorted(set((raw.get("supersedes") or []) + done))
        opsdb.patch("tasks", {"id": f"eq.{new_id}"}, {"raw": raw})
    print(f"대체 표시(실행 {run}, 되돌리기: --undo {run}): 결정 {new_id}가 {done or old_ids} 대체")
    return 0


def undo(run):
    import opsdb
    n = 0
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        e = json.loads(ln)
        if e["run"] != run:
            continue
        if e.get("op") == "supersede":
            r = opsdb.select("tasks", "id,raw", where={"id": f"eq.{e['id']}"}, limit=1)[0]
            raw = dict(r["raw"] or {})
            raw.pop("superseded_why", None)
            if e.get("prev_sup"):
                raw["superseded_by"] = e["prev_sup"]
            else:
                raw.pop("superseded_by", None)
            opsdb.patch("tasks", {"id": f"eq.{e['id']}"}, {"raw": raw})
        elif e.get("op") == "due":
            r = opsdb.select("tasks", "id,raw", where={"id": f"eq.{e['id']}"}, limit=1)[0]
            raw = dict(r["raw"] or {})
            if e.get("prev_due"):
                raw["due"] = e["prev_due"]
            else:
                raw.pop("due", None)
            opsdb.patch("tasks", {"id": f"eq.{e['id']}"}, {"raw": raw})
        elif e.get("op") == "rewrite":
            opsdb.patch("tasks", {"id": f"eq.{e['id']}"}, {"title": e["prev_title"], "next_action": e["prev_do"]})
        else:
            opsdb.patch("tasks", {"id": f"eq.{e['id']}"}, {"status": e["prev"]})
        n += 1
    print(f"되돌림: 실행 {run}의 카드 {n}장")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if a[:1] == ["--undo"]:
        return undo(a[1])
    if a[:1] == ["--supersede"]:  # --supersede 새결정id 옛결정id [옛결정id...] [--why "이유"]
        why = a[a.index("--why") + 1] if "--why" in a else ""
        ids = [int(x) for x in a[1:] if x.isdigit()]
        return supersede(ids[0], ids[1:], why, dry="--dry" in a)
    files = [x for x in a if not x.startswith("--")]
    path = files[0] if files else max(DIR.glob("a2_*.md"), key=lambda p: p.stat().st_mtime, default=None)
    if not path:
        print("감수 실행: 판정 파일 없음")
        return 0
    run, refs, done, fixed = apply(path, dry="--dry" in a)
    tag = "(시험)" if "--dry" in a else f"(실행 {run}, 되돌리기: --undo {run})"
    print(f"감수 실행{tag}: 판정 숨김 {len(refs)}장 중 {len(done)}장 내림, 소넷 고쳐 쓰기 {len(fixed)}건 " + " / ".join(done + fixed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
