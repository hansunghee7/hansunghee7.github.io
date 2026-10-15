# -*- coding: utf-8 -*-
"""혼란 정보 찾기(2026-10-15 탐, 사장님: "찾아야 하는 것은 찾기 쉽게, 혼란스럽게 만드는 정보는 찾기 어렵게 만들어야 함").
기억 도우미(recall)의 1차 자리(공정 카드)에 남아 있지만 이미 바뀌었거나 폐기된 규칙을 찾아 '내릴 후보'로 낸다. 직접 숨기지 않는다(제안 전용).
판정 신호(규칙 기반, 판정은 컨텍스트 감수 에이전트가 최종):
  ① 폐기·대체 표시: 제목·내용에 폐기, 롤백, 정정, 대체, 옛 방식, 이전 규칙, 무효, 접음 같은 말
  ② 같은 주제 중복: 제목 앞부분이 비슷한 카드가 여러 개(최신 하나만 1차에 두고 나머지는 가리키게)
사용: python scripts/ops/confusion_scan.py [--top 20]   (결과 C:/work/_ops/context_audit/confusion_YYYYMMDD.md)"""
import collections
import json
import re
import sys
import time
from pathlib import Path

CACHE = Path("C:/work/_ops/recall_cache.json")
OUT = Path("C:/work/_ops/context_audit")
STALE = re.compile(r"(폐기|롤백|정정|대체됨|옛 방식|옛 규칙|이전 규칙|무효|더 이상 쓰지|부분 폐기|→ 정본)")  # "대체 경로"(다른 길)는 폐기가 아니라 제외(10/15 첫 실행 오탐)


def norm(t):
    t = re.sub(r"[\[\]()（）0-9/.:·,~\-]", " ", t)
    return " ".join(w for w in t.split() if len(w) >= 2)[:14]  # 앞 14자로 같은 주제 묶음


def scan(top=20):
    cards = json.loads(CACHE.read_text(encoding="utf-8")).get("cards", [])
    stale = [c for c in cards if STALE.search(c["t"])]
    groups = collections.defaultdict(list)
    for c in cards:
        k = (c["p"], norm(c["t"]))
        if len(k[1]) >= 10:
            groups[k].append(c)
    # 같은 절의 하위 단계(예: "5. ...: 계정", "5. ...: 프롬프트")는 중복이 아니라 오탐이 많아(10/15 첫 실행 18묶음 전부 하위 단계) 판정 재료에서 뺀다
    dups = []
    lines = [f"# 혼란 정보 후보 {time.strftime('%Y-%m-%d %H:%M')} (카드 {len(cards)}개 중, 제안 전용)", "",
             f"## ① 폐기·대체 표시가 있는데 1차 자리에 남은 카드 {len(stale)}개(상위 {top})"]
    for c in stale[:top]:
        lines.append(f"- [{c['p']}#{c['no']}] {c['t'][:90]}")
    lines += ["", "제안 원칙: 최신 정본 하나만 1차에 두고, 폐기·대체된 카드는 '숨김'(기억 도우미가 1차에서 빼는 상태)으로 내리며, 내용은 이력으로 남긴다."]
    return len(cards), len(stale), len(dups), "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    top = int(a[a.index("--top") + 1]) if "--top" in a else 20
    n, s, d, text = scan(top)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"confusion_{time.strftime('%Y%m%d')}.md"
    f.write_text(text, encoding="utf-8")
    print(f"혼란 정보 후보: 카드 {n}개 중 폐기·대체 표시 {s}개, 중복 묶음 {d}개 → {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
