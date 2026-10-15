# -*- coding: utf-8 -*-
"""컨텍스트 연관관계 지도(2026-10-15 탐, 사장님: "컨텍스트 설계 에이전트는 한 곳 고치면 영향 주는 것까지 고려해 고치거나 제안해야 한다, 사이드 이펙트 없어야 한다").
origin/main의 규칙 문서(CLAUDE.md·스킬·rules·docs), 훅(.claude/hooks), 운영 스크립트(scripts/ops), DB 표 이름 사이의 '언급 관계'를 모아
"이걸 고치면 어디가 영향받나"를 바로 답할 수 있게 한다. 판정은 하지 않는다(관계 목록만).
노드: 파일 경로, CLAUDE 원칙 id(CLAUDE#xxxx), DB 표(opsdb.select('표')·tasks section='값').
간선: A가 B를 이름으로 언급(파일명·스크립트명·원칙 id·표 이름).
사용:
  python scripts/ops/context_graph.py build                 지도 만들기 → C:/work/_ops/context_graph.json
  python scripts/ops/context_graph.py impact <이름>          그 이름(파일·스크립트·id·표)을 언급하는 곳과, 그것이 언급하는 곳
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path("C:/work/hansunghee7.github.io")  # 래퍼가 임시 폴더에 풀어 실행해도 git 기록은 공용 폴더에서 읽는다(10/15 빈 지도 사고)
OUT = Path("C:/work/_ops/context_graph.json")
SCOPE = re.compile(r"^(CLAUDE\.md|\.claude/settings\.json|\.claude/(skills|rules|hooks)/.+\.(md|py|sh)|docs/[^/]+\.md|scripts/ops/[^/]+\.(py|sh|toml))$")
ID_RE = re.compile(r"(?:CLAUDE|WAY|UX_GUIDE)#[0-9a-z]{4}")
TABLE_RE = re.compile(r"select\(\s*['\"]([a-z_]+)['\"]|section['\"]?\s*[:=]\s*['\"](?:eq\.)?([a-z_]+)['\"]")


def git(*a):
    return subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(REPO)] + list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout


def build():
    files = [f for f in git("ls-tree", "-r", "--name-only", "origin/main").split("\n") if SCOPE.match(f)]
    names = {}  # 언급 검색어 → 노드
    for f in files:
        p = Path(f)
        names[p.name] = f
        if p.suffix in (".py", ".sh"):
            names[p.stem + p.suffix] = f
    edges = defaultdict(set)
    ids_def = {}
    for f in files:
        txt = git("show", f"origin/main:{f}")
        for m in re.finditer(r"<!-- id: ([0-9a-z]{4}) -->", txt):
            if f == "CLAUDE.md":
                ids_def[f"CLAUDE#{m.group(1)}"] = f
        for n, target in names.items():
            if target != f and n in txt:
                edges[f].add(target)
        for m in ID_RE.finditer(txt):
            edges[f].add(m.group(0))
        for m in TABLE_RE.finditer(txt):
            t = m.group(1) or m.group(2)
            if t:
                edges[f].add(f"db:{t}")
    if not files:
        print("지도 실패: origin/main 파일 목록이 비었습니다(git 위치 확인)")
        sys.exit(1)
    data = {"files": len(files), "edges": {k: sorted(v) for k, v in edges.items()}, "id_defined_in": ids_def}
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    n = sum(len(v) for v in edges.values())
    print(f"지도 생성: 파일 {len(files)}개, 관계 {n}개 → {OUT}")


def impact(name):
    d = json.loads(OUT.read_text(encoding="utf-8"))
    e = d["edges"]
    key = name
    if not any(key == k or key in v for k, v in e.items()):
        cands = [k for k in e if k.endswith(name)] + sorted({t for v in e.values() for t in v if t.endswith(name)})
        key = cands[0] if cands else name
    used_by = sorted(k for k, v in e.items() if key in v)
    uses = e.get(key, [])
    print(f"[{key}]")
    print(f"이것을 언급하는 곳(고치면 영향받을 수 있음) {len(used_by)}개:")
    for k in used_by:
        print("  -", k)
    print(f"이것이 언급하는 곳 {len(uses)}개:")
    for k in uses:
        print("  -", k)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build()
    elif len(sys.argv) >= 3 and sys.argv[1] == "impact":
        impact(sys.argv[2])
    else:
        print(__doc__)
