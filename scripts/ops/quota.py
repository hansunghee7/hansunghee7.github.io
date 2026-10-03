"""외부 모델 무료 한도 관리 대장(2026-10-03 탐, 사장님 지시 "한도 제한이 걸리면 모두가 골치 아프니 탐이 관리").

왜: 10/3 비티(제미나이) 주 단위 한도가 탐·핏 합산 이틀 13회 호출 만에 소진돼 약 130시간 막혔다.
누가 얼마나 썼는지, 언제 풀리는지를 아무도 몰랐다. 그래서 부르기 전에 이 대장을 보는 관문을 둔다.

기록 원천: C:/work/_ops/agent_calls.csv (ask_bt.sh·ask_dex.sh·bt_loop.py·핏 recommend_topics.py가 한 줄씩 쓴다)
막힘 상태: C:/work/_ops/quota_state.json (한도 오류가 나면 hit으로 기록, 풀리는 시각까지 check가 막는다)

사용:
    python scripts/ops/quota.py status            # 사람용 요약(최근 7일 사용·예산·막힘)
    python scripts/ops/quota.py check 비티 [--who 탐]  # 부르기 전 관문: 0 통과 / 2 막힘(리셋 전) / 3 예산 초과
    python scripts/ops/quota.py hit 비티 "<오류 원문>"   # 한도 오류를 만났을 때. 원문의 "Resets in 130h9m"을 읽어 풀리는 시각을 적는다
    python scripts/ops/quota.py watch             # 감시 대장용: 막힘·예산 80% 넘으면 종료 코드 1

풀(pool) 이름: 같은 한도를 나눠 쓰는 묶음. 비티 제미나이 = "비티", 비티 안의 Sonnet = "비티-sonnet", 덱스 = "덱스".
예산(주): 비티 = 10회(추정, 10/3 실측 1회분) 중 핏 3·탐 7(사장님 결정 10/3). 나머지 풀은 아직 한도를 모르니 세기만 한다.
"""
import csv
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

OPS = Path("C:/work/_ops")
CALLS = OPS / "agent_calls.csv"
STATE = OPS / "quota_state.json"
WEEK = timedelta(days=7)

# 주간 예산. None = 한도를 아직 모름(세기만). 근거는 docs/processes/비티_한도_조건.md
BUDGET = {
    "비티": {"total": 10, "핏": 3, "탐": 7},
    "비티-sonnet": None,
    "덱스": None,
}
# agent_calls.csv의 who 값 → 풀과 사용자. 핏 도구는 who=비티로 쓰지만 시각으로 구분이 안 돼 note 열이 생기기 전까지는 합산으로 본다.
WHO_MAP = {"비티": ("비티", None), "비티-sonnet": ("비티-sonnet", None), "덱스": ("덱스", None)}


def load_calls(now):
    rows = []
    if not CALLS.exists():
        return rows
    with CALLS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                t = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S")
            except (KeyError, ValueError):
                continue
            if now - t <= WEEK and r.get("who") in WHO_MAP:
                pool, _ = WHO_MAP[r["who"]]
                rows.append({"t": t, "pool": pool, "user": (r.get("user") or "").strip() or "미상", "rc": r.get("rc", "")})
    return rows


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def blocked_until(st, pool, now):
    b = st.get(pool, {}).get("blocked_until")
    if b and datetime.fromisoformat(b) > now:
        return datetime.fromisoformat(b)
    return None


def summary(now):
    st, rows, lines = load_state(), load_calls(now), []
    worst = 0
    for pool, bud in BUDGET.items():
        used = [r for r in rows if r["pool"] == pool]
        ok = [r for r in used if r["rc"] == "0"]
        b = blocked_until(st, pool, now)
        part = f"{pool}: 최근 7일 {len(used)}회(성공 {len(ok)})"
        if bud:
            part += f" / 예산 {bud['total']}"
            if len(used) >= bud["total"] * 0.8:
                worst = max(worst, 1)
        if b:
            part += f" / 막힘, {b:%m-%d %H:%M} 풀림"
            worst = max(worst, 1)
        lines.append(part)
    return worst, lines


def parse_reset(msg, now):
    m = re.search(r"Resets in\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?", msg or "")
    if not m or not any(m.groups()):
        return now + timedelta(hours=24)  # 리셋 시각을 모르면 하루 쉬고 다시 본다
    h, mi, s = (int(x or 0) for x in m.groups())
    return now + timedelta(hours=h, minutes=mi, seconds=s)


def main(argv):
    now = datetime.now()
    if not argv or argv[0] == "status":
        _, lines = summary(now)
        print("\n".join(lines))
        return 0
    cmd = argv[0]
    if cmd == "watch":
        worst, lines = summary(now)
        print(" | ".join(lines))
        return worst
    if cmd == "check":
        pool = argv[1]
        who = argv[argv.index("--who") + 1] if "--who" in argv else None
        b = blocked_until(load_state(), pool, now)
        if b:
            print(f"{pool} 막힘: {b:%m-%d %H:%M}까지(한도 초과 기록). 다른 풀을 쓰세요(비티 → 비티-sonnet 또는 덱스).")
            return 2
        bud = BUDGET.get(pool)
        used = [r for r in load_calls(now) if r["pool"] == pool]
        if bud and len(used) >= bud["total"]:
            print(f"{pool} 주간 예산 {bud['total']}회 다 씀(최근 7일 {len(used)}회).")
            return 3
        print(f"{pool} 통과(최근 7일 {len(used)}회{'' if not bud else ' / 예산 ' + str(bud['total'])})")
        return 0
    if cmd == "hit":
        pool, msg = argv[1], (argv[2] if len(argv) > 2 else "")
        until = parse_reset(msg, now)
        st = load_state()
        st[pool] = {"blocked_until": until.isoformat(timespec="seconds"), "hit_at": now.isoformat(timespec="seconds"), "msg": msg[:300]}
        save_state(st)
        print(f"{pool} 막힘 기록: {until:%m-%d %H:%M}까지")
        return 0
    print(__doc__)
    return 64


if __name__ == "__main__":
    try:  # 감시·셸이 cp949로 읽어도 한글이 깨지지 않게
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main(sys.argv[1:]))
