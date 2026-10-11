"""세션 시작 카드 안내 횟수를 날짜별로 센다. 기록: C:/work/_ops/card_reads.jsonl"""
import json
import sys
from collections import Counter

PATH = sys.argv[1] if len(sys.argv) > 1 else "C:/work/_ops/card_reads.jsonl"
on, off = Counter(), Counter()
try:
    with open(PATH, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            day = str(r.get("ts", ""))[:10]
            (on if r.get("card") == "on" else off)[day] += 1
except FileNotFoundError:
    print("기록 없음:", PATH)
    sys.exit(0)
for day in sorted(set(on) | set(off)):
    print(f"{day}  켜짐 {on[day]}  꺼짐 {off[day]}")
print(f"합계  켜짐 {sum(on.values())}  꺼짐 {sum(off.values())}")
