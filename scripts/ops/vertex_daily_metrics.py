#!/usr/bin/env python3
"""Vertex·라우터 일일 지표(대장 N160·G1, 2026-10-06 탐): 하루 호출 수·추정 비용, 무료 전환(장애 전환) 횟수, 라우터 통과 수, 최종 실패율.
읽는 곳: C:/work/_ops/vertex_usage.csv(Vertex 호출 기록), vertex_failover.csv(상한·429·403 때 무료로 전환한 기록, model 열이 router:...이면 옴니라우터 통과).
쓰는 곳: C:/work/_ops/vertex_metrics.md(날짜별 한 줄, 매번 전체를 다시 씀 = 멱등). 종료 코드 0 = 정상, 1 = 읽기 오류.
G1 완료 기준(운영 호출 1곳 이상 라우터 통과 + 1주 비교 숫자)을 이 파일의 '라우터' 열로 본다."""
import collections
import csv
import sys
from pathlib import Path

OPS = Path("C:/work/_ops")


def rows(name):
    p = OPS / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    try:
        use, fo = rows("vertex_usage.csv"), rows("vertex_failover.csv")
    except (OSError, csv.Error) as e:
        print("읽기 오류", e)
        return 1
    day = collections.defaultdict(lambda: {"calls": 0, "fail": 0, "krw": 0.0, "fo": 0, "router": 0, "fo_fail": 0})
    for r in use:
        d = day[r["time"][:10]]
        d["calls"] += 1
        d["krw"] += float(r.get("est_krw") or 0)
        d["fail"] += 1 if str(r.get("rc", "0")) not in ("0", "") else 0
    for r in fo:
        d = day[r["time"][:10]]
        d["fo"] += 1
        d["router"] += 1 if str(r.get("model", "")).startswith("router:") else 0
        d["fo_fail"] += 1 if r.get("ok") == "0" else 0
    lines = ["# Vertex·라우터 일일 지표 (vertex_daily_metrics.py가 매번 다시 씀)", "", "날짜 | Vertex 호출 | 추정비용(원) | 호출 실패 | 무료 전환 | 라우터 통과 | 전환 최종 실패", "---|---|---|---|---|---|---"]
    for k in sorted(day):
        d = day[k]
        lines.append(f"{k} | {d['calls']} | {d['krw']:.0f} | {d['fail']} | {d['fo']} | {d['router']} | {d['fo_fail']}")
    (OPS / "vertex_metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = day[max(day)] if day else None
    print(f"최근일 {max(day) if day else '-'}: 호출 {t['calls'] if t else 0}, 전환 {t['fo'] if t else 0}, 라우터 {t['router'] if t else 0}, 누적 라우터 {sum(d['router'] for d in day.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
