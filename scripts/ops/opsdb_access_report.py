# -*- coding: utf-8 -*-
"""G2 지표: C:/work/_ops/opsdb_access.jsonl 에서 에이전트(who)·명령(cmd)별 DB 조회 횟수를 집계한다.
사용: python scripts/ops/opsdb_access_report.py [로그경로]"""
import json
import sys
from collections import Counter
from pathlib import Path

P = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\work\_ops\opsdb_access.jsonl")
if not P.exists():
    print(f"파일 없음: {P}")
    sys.exit(0)
who, cmd, tbl, days, bad = Counter(), Counter(), Counter(), Counter(), 0
for line in P.read_text(encoding="utf-8", errors="replace").splitlines():
    try:
        r = json.loads(line)
    except ValueError:
        bad += 1
        continue
    who[r.get("who") or "(미기재)"] += 1
    cmd[r.get("cmd") or "?"] += 1
    tbl[r.get("table") or "?"] += 1
    days[str(r.get("t", ""))[:10]] += 1
print(f"총 {sum(who.values())}건 (깨진 줄 {bad}), 기간 {min(days, default='-')} ~ {max(days, default='-')}")
for title, c in (("에이전트(who)", who), ("명령(cmd)", cmd), ("표(table)", tbl), ("일자", days)):
    print(f"[{title}]")
    for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:15] if title != "일자" else sorted(c.items()):
        print(f"  {k}: {v}")
