#!/usr/bin/env python3
"""헤르메스 수집 보고서의 인용을 코드로 대조한다(2026-09-21). AI를 쓰지 않는다.

보고서의 `항목 | URL | 접속 시각 | 열람 성공/일부/실패 | 원문 인용` 줄(마크다운 표 행 포함)을 읽어
각 URL을 실제로 내려받아 인용이 본문에 그대로 있는지 문자열로 대조한다. 결과는 표준출력 표 한 장.
사용: verify_collect_report.py <보고서.md> [--max N]
판정은 하지 않는다. 일치는 "그 페이지에 그 문장이 있다"는 뜻일 뿐이다.
대조 함수는 goosolar/night_research.py의 verify()를 그대로 쓴다(https + 공인 주소만 내려받음).
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "goosolar"))
import night_research as nr  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = re.compile(r"https?://[^\s|)>\]]+")


def parse(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        if "|" not in line or "http" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        idx = next((i for i, c in enumerate(cells) if URL.search(c)), None)
        if idx is None or len(cells) < idx + 2:
            continue
        quote = cells[-1].strip("`* ")
        if len(cells) - 1 == idx:  # 인용 칸이 없는 행
            continue
        rows.append({"claim": cells[0].strip("`* ") if idx else "", "url": URL.search(cells[idx]).group(0).rstrip(".,"), "quote": quote,
                     "reported": next((c for c in cells[idx + 1:-1] if "열람" in c or c in ("성공", "일부", "실패")), "")})
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 999
    rows = parse(sys.argv[1])[:limit]
    stat = {}
    print(f"| 대조 | 보고서의 열람 표기 | URL | 인용(앞 60자) | 비고 |\n|---|---|---|---|---|")
    for r in rows:
        st, why = nr.verify(r)
        stat[st] = stat.get(st, 0) + 1
        print(f"| {st} | {r['reported'] or '-'} | {r['url'][:70]} | {r['quote'][:60].replace('|', '/')} | {why} |")
    print(f"\n합계 {len(rows)}줄: " + ", ".join(f"{k} {v}" for k, v in sorted(stat.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
