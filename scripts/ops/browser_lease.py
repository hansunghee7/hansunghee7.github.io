# -*- coding: utf-8 -*-
"""서브에이전트 크롬 도구 임대(핏 2026-10-05, 사장님 승인: 영상 생성 같은 기계적 반복은 서브에이전트(새 컨텍스트, 하이쿠 포함)로 분산).
배경: `.claude/hooks/subagent-blocking-gate.py`는 9/29 하이쿠가 브라우저 제어권을 붙잡아 다른 세션까지 멈춘 사고 뒤 서브에이전트의 브라우저 도구를 막는다.
이 예외는 사고 조건을 그대로 막는다: ① claude-in-chrome 도구만(Claude_Browser·computer-use는 계속 차단) ② 임대가 살아 있는 동안만(기본 60분, 최대 120분, 자동 만료)
③ 한 번에 한 명(임대가 있으면 새 임대 거부) ④ 허용된 호출은 `C:/work/_ops/factory_browser_lease.log`에 남김 ⑤ 멈춤 조건은 서브에이전트 지시서에 넣는다.
충돌: 같은 크롬(신PC)을 부모 세션과 서브에이전트가 동시에 쓰면 충돌한다 → 임대 중에는 부모 세션이 그 크롬 탭을 쓰지 않는다. 구PC 크롬은 별도라 여러 개를 동시에 돌릴 수 있다(사장님 10/5).
첫 시험은 소넷으로 한 컷, 안전하게 끝나면 하이쿠로 내린다(9/29 사고의 주인공이 하이쿠였다).
사용:
  python scripts/ops/browser_lease.py grant --who 핏 --minutes 60 --note "lf03 Flow 생성"
  python scripts/ops/browser_lease.py status
  python scripts/ops/browser_lease.py release
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LEASE = Path(r"C:\work\_ops\factory_browser_lease.json")
KST = timezone(timedelta(hours=9))
sys.stdout.reconfigure(encoding="utf-8")


def read():
    try:
        d = json.loads(LEASE.read_text(encoding="utf-8"))
        if datetime.fromisoformat(d["expires"]) > datetime.now(KST):
            return d
    except Exception:
        pass
    return None


ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["grant", "status", "release"])
ap.add_argument("--who", default="")
ap.add_argument("--minutes", type=int, default=60)
ap.add_argument("--note", default="")
a = ap.parse_args()
cur = read()
if a.cmd == "status":
    print(json.dumps(cur, ensure_ascii=False) if cur else "임대 없음")
elif a.cmd == "release":
    LEASE.unlink(missing_ok=True)
    print("임대 해제")
else:
    if cur:
        sys.exit(f"이미 임대 중({cur['who']}, {cur['expires']}). 한 번에 한 명만 가능")
    if not a.who:
        sys.exit("--who 필요")
    m = min(max(a.minutes, 1), 120)
    d = {"who": a.who, "granted": datetime.now(KST).isoformat(), "expires": (datetime.now(KST) + timedelta(minutes=m)).isoformat(), "note": a.note}
    LEASE.parent.mkdir(parents=True, exist_ok=True)
    LEASE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print("임대 시작:", json.dumps(d, ensure_ascii=False))
