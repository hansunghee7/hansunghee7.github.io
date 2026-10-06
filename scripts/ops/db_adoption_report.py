# -*- coding: utf-8 -*-
"""운영 DB 실적용 보고(G2, 2026-10-05 탐, 사장님 지시 "수파베이스를 에이전트들에게 빨리 실적용"): 하루에 DB가 얼마나 읽혔고, 큰 업무 md 통읽기 시도를 몇 번 막았는지 숫자로 본다.
읽는 곳(값 없음): C:/work/_ops/opsdb_access.jsonl (opsdb.py가 호출마다 한 줄: 시각·방식·표·명령), C:/work/_ops/db_gate_log.jsonl (DB 관문 훅의 막힘·통과).
주의: 관문 훅 로그에는 10/5 시험 호출이 섞여 있어 10/6부터를 본다. 호출자(에이전트) 구분은 환경변수 OPSDB_WHO가 있을 때만 된다.
사용: python scripts/ops/db_adoption_report.py [일수=7]"""
import collections
import json
import sys
from datetime import datetime, timedelta

OPS = r"C:\work\_ops"


def load(name):
    out = []
    try:
        for l in open(f"{OPS}\\{name}", encoding="utf-8"):
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    acc = [r for r in load("opsdb_access.jsonl") if r["t"][:10] >= since]
    gate = [r for r in load("db_gate_log.jsonl") if r["t"][:10] >= since]
    print(f"[운영 DB 실적용 {since}~] DB 호출 {len(acc)}건 / 관문 막힘 {sum(1 for g in gate if g['decision'] == 'block')}건·통과 {sum(1 for g in gate if g['decision'] == 'pass')}건")
    by_day = collections.Counter(r["t"][:10] for r in acc)
    by_cmd = collections.Counter(r.get("cmd", "?") for r in acc)
    by_who = collections.Counter(r.get("who") or "(미지정)" for r in acc)
    by_tab = collections.Counter(r.get("table", "?") for r in acc)
    print("  일별:", dict(sorted(by_day.items())))
    print("  명령별:", dict(by_cmd.most_common(6)))
    print("  호출자별:", dict(by_who))
    print("  표별:", dict(by_tab.most_common(6)))
    # G2 완료 기준: 에이전트 3명 이상의 일일 DB 조회 기록(조회=GET). 호출자는 OPSDB_WHO 또는 --who로 구분된다(10/6부터).
    per = collections.defaultdict(collections.Counter)
    for r in acc:
        if r.get("m") == "GET" and r.get("who"):
            per[r["t"][:10]][r["who"]] += 1
    for day in sorted(per):
        who = per[day]
        mark = "달성" if len(who) >= 3 else f"{len(who)}명"
        print(f"  G2 {day} 조회한 에이전트 {len(who)}명({mark}):", dict(who.most_common()))
    unk = sum(1 for r in acc if r.get("m") == "GET" and not r.get("who"))
    print(f"  호출자 미지정 조회 {unk}건(--who를 붙이면 구분됨)")
    gb = collections.Counter(g["t"][:10] for g in gate if g["decision"] == "block")
    print("  md 통읽기 시도 막힘(일별):", dict(sorted(gb.items())))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
