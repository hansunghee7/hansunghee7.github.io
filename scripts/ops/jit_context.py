# -*- coding: utf-8 -*-
"""행동 시점 기억 주입(Just-in-time context, 2026-10-15 탐 시제품).
사장님 진단(10/15): "프로세스표와 정본을 만들어도 세션이 바뀌거나 조건이 바뀌면 까먹는다. 훅도 특정 키워드에서만 발동돼서 힘들다."
원인: 지금 기억 도우미(recall)는 사장님 '말'의 키워드로만 깨어난다. 에이전트가 스스로 어떤 파일을 고치려는 순간에는 아무것도 알려 주지 않는다.
이 도구는 키워드가 아니라 '행동 대상'으로 깨어난다: 에이전트가 파일을 고치기 직전(Edit·Write), 그 파일과 연결된 규칙·공정 카드·영향받는 곳을 붙여 준다.
재료: 연관관계 지도(C:/work/_ops/context_graph.json, context_graph.py), 기억 캐시의 공정 카드(C:/work/_ops/recall_cache.json).
막지 않는다(알림만). 관련 없으면 조용히 끝난다.
사용:
  python scripts/ops/jit_context.py --file .claude/hooks/save-gate.py      사람이 보는 시험
  python scripts/ops/jit_context.py --hook < 훅JSON                         PreToolUse 훅용(tool_input.file_path)"""
import json
import sys
from pathlib import Path

GRAPH = Path("C:/work/_ops/context_graph.json")
CACHE = Path("C:/work/_ops/recall_cache.json")


def rel(path):
    p = str(path).replace("\\", "/")
    for root in ("hansunghee7.github.io/",):
        if root in p:
            return p.split(root, 1)[1]
    # 워크트리(C:/work/tam-xxx/...)도 저장소 상대 경로로 맞춘다
    for marker in ("/scripts/", "/docs/", "/.claude/"):
        if marker in p:
            return p[p.index(marker) + 1:]
    return p


def lookup(path):
    r = rel(path)
    name = r.split("/")[-1]
    stem = name.rsplit(".", 1)[0]
    out = []
    try:
        g = json.loads(GRAPH.read_text(encoding="utf-8"))["edges"]
        used_by = sorted(k for k, v in g.items() if r in v)
        uses_rules = [x for x in g.get(r, []) if "#" in x]
        if used_by:
            out.append(f"이 파일을 언급하는 곳 {len(used_by)}개(고치면 같이 확인): " + ", ".join(used_by[:8]) + (" ..." if len(used_by) > 8 else ""))
        if uses_rules:
            out.append("이 파일이 근거로 삼는 원칙: " + ", ".join(uses_rules[:6]))
    except (OSError, ValueError, KeyError):
        pass
    try:
        cards = json.loads(CACHE.read_text(encoding="utf-8")).get("cards", [])
        keys = {name, stem, stem.replace("-", "_"), stem.replace("_", "-")}
        hits = [c for c in cards if any(k and len(k) >= 5 and k in (c["t"] + " " + c["d"]) for k in keys)]
        for c in hits[:3]:
            out.append(f"공정 카드 [{c['p']}#{c['no']}] {c['t'][:70]}" + (f" ★사장님: {c['b'][:100]}" if c.get("b") else ""))
    except (OSError, ValueError, KeyError):
        pass
    return r, out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    if "--file" in a:
        r, out = lookup(a[a.index("--file") + 1])
        print(f"[{r}]")
        print("\n".join(out) or "(연결된 규칙·카드 없음)")
        return 0
    if "--hook" in a:
        try:
            d = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            return 0
        fp = (d.get("tool_input") or {}).get("file_path")
        if not fp:
            return 0
        r, out = lookup(fp)
        if out:
            msg = f"[행동 시점 기억] {r}를 고치기 전에 확인할 연결:\n- " + "\n- ".join(out)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}, ensure_ascii=False))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
