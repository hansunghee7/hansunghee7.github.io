#!/usr/bin/env python3
"""탐 업무대장에서 "사장님 결정 대기" 목록을 만들 때, 이미 사장님이 정한 것을 다시 묻지 않게 하는 점검기. 2026-10-03 탐.

사고: B50은 10/2에 사장님이 "유료 전환은 직접, 대기 서버는 멘토링"이라 정했고 대장에도 적혀 있었는데,
같은 칸에 "선택 대기"·"사장님 할 일: 방안 선택"이 낡은 채 남고 상태가 [사장님]이라, 10/3 저녁 세션이 머리줄·끝줄만 보고
"선택 대기"로 보고했다. 사장님은 어느 에이전트와 언제 말했는지 다 기억할 수 없으므로 찾는 일은 탐의 몫이다.

사용:
  python scripts/ops/ledger_lint.py            모순 칸만(결정 기록이 있는데 아직 선택 대기 문구가 남은 [사장님]·[확인필요] 칸). 있으면 종료코드 1
  python scripts/ops/ledger_lint.py --boss     [사장님] 칸마다 사장님 결정·지시 줄을 잘라내지 않고 전부 출력(대기 목록 보고 전에 이걸 읽는다)
  python scripts/ops/ledger_lint.py --find 키워드   대장·히스토리·진행상황·아카이브·역할노트에서 키워드가 든 사장님 결정 줄 검색
"""
import re, sys, glob, os
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.environ.get("LEDGER_FILE") or os.path.join(ROOT, "docs", "탐_업무대장.md")
DECIDED = re.compile(r"사장님[^\n]{0,12}(판단|결정|확정|지시|승인|정정|합의|제안)")
WAITING = re.compile(r"선택 대기|결정 대기|결정 필요|선택 필요|사장님 할 일:[^\n]*(선택|결정)")


def blocks():
    text = open(LEDGER, encoding="utf-8").read().replace("\r\n", "\n")
    parts = re.split(r"(?m)^(?=### \[)", text)
    for p in parts:
        m = re.match(r"### \[([^\]]+)\] (\S+):? ?(.*)", p)
        if m:
            yield m.group(1), m.group(2).rstrip(":"), m.group(3).split("\n")[0], p.split("\n")[1:]


def main():
    a = sys.argv[1:]
    if a[:1] == ["--find"]:
        kw = a[1]
        files = [LEDGER, os.path.join(ROOT, "docs", "탐_업무대장_히스토리.md"), os.path.join(ROOT, "docs", "진행상황.md"),
                 os.path.join(ROOT, "docs", "역할노트-탐.md")] + sorted(glob.glob(os.path.join(ROOT, "docs", "진행상황_아카이브", "*.md")))
        for f in files:
            if not os.path.exists(f):
                continue
            for i, l in enumerate(open(f, encoding="utf-8", errors="ignore"), 1):
                if kw in l and DECIDED.search(l):
                    print(f"{os.path.relpath(f, ROOT)}:{i}: {l.strip()[:400]}")
        return 0
    bad = 0
    for status, nid, title, lines in blocks():
        if status in ("완료", "드랍"):
            continue
        # 칸은 위에서 아래로 시간순이라 가정: "선택 대기" 문구보다 뒤에 사장님 결정·지시 줄이 있으면 그 대기 문구는 낡았을 가능성이 큼.
        # 이미 정정한 줄("정정", "결정 완료", "결정됨", "없음")은 제외해 오탐을 줄인다.
        FIXED = re.compile(r"정정|결정 완료|결정됨|대기 없음|결정 예정: 없음")
        stale = []
        for idx, l in enumerate(lines):
            if WAITING.search(l) and not FIXED.search(l) and any(DECIDED.search(x) for x in lines[idx + 1:]):
                stale.append(l)
        if "--boss" in a and status == "사장님":
            print(f"\n## {nid} [{status}] {title}")
            for l in lines:
                if DECIDED.search(l) or WAITING.search(l):
                    print("  " + l.strip())
        if stale and "--boss" not in a:
            bad += 1
            print(f"⚠ {nid} [{status}] {title}: 낡았을 수 있는 대기 문구 {len(stale)}줄(뒤에 사장님 결정·지시 기록이 있음) -> 칸을 읽고 고칠 것")
            for l in stale[:2]:
                print("    " + l.strip()[:160])
    # 측정 먼저 규칙(사장님 2026-10-05 "탐과 일할 때는 측정(정답지)을 먼저 만드는 작업이 1번, 그 뒤에 설계"): N160 이후 [진행] 칸에는 측정 기준·정답지 줄이 있어야 한다
    nomeasure = [(i, t) for st, i, t, ls in blocks() if st == "진행" and re.fullmatch(r"N\d+", i) and int(i[1:]) >= 160 and not any(re.search(r"측정|정답지", l) for l in ls)]
    for i, t in nomeasure:
        bad += 1
        print(f"⚠ {i} [진행] {t[:60]}: 측정 기준(정답지 출처)이 적혀 있지 않음 -> 설계 전에 '측정:' 줄부터 적을 것")
    if "--boss" not in a:
        print("모순 칸 없음" if not bad else f"모순 {bad}건")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
