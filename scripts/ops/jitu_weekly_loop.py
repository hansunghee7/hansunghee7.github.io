#!/usr/bin/env python3
"""지투 주간 KPI 루프(슈퍼프로세스 KPI 관리 공통 공정 ⑥, 2026-10-12 지투).

지투 KPI = 고객수(사장님 지정 2026-10-12: UX MCP와 Carvit 전체 상품의 고객 획득·리텐션).
작업 스케줄러가 주 1회 돌려 한 장(C:/work/_ops/jitu_po/주간_KPI.md)을 만든다: 고객수 추이, 선행 지표, 열린 예측·결정·검사 공백,
슈퍼얼라인 점검 결과. 에이전트는 이 장을 읽고 제안·기록까지만 한다(해석과 방향은 사장님·비티·덱스).
고객수는 아직 사람이 적는다(`jitu_po.py kpi add --customers N`). 자동 수집은 개선 과제(검사 공백 원장)에 올라 있다.
수동 실행: python scripts/ops/jitu_weekly_loop.py
"""
import datetime as dt
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("JITU_WEEKLY_OUT", "C:/work/_ops/jitu_po/주간_KPI.md")

spec = importlib.util.spec_from_file_location("jitu_po", os.path.join(HERE, "jitu_po.py"))
jp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jp)


def trend(rows):
    out = []
    for r in rows[-4:]:
        c = r.get("customers")
        out.append(f"- {r['date']} ({r['week']}): 고객수 {c if c is not None else '미기록'}"
                   f"(신규 {r.get('new_customers', '-')}, 이탈 {r.get('lost_customers', '-')}) | 활성 호출자 {r['ext_active_callers_7d']}, "
                   f"인용 {r['ext_cites_7d']}, 찾지 못한 검색률 {r.get('miss_rate')}")
    return out


def main():
    today = jp.today()
    kpis = jp.load("kpi")
    lines = [f"# 지투 주간 KPI 루프 ({today})", "",
             "**KPI: 고객수**(UX MCP와 Carvit 전체 상품의 고객 획득·리텐션, 사장님 지정 2026-10-12). 숫자 목표는 기준선을 본 뒤 사장님과 정한다.", ""]
    lines.append("## 고객수 추이(최근 4회)")
    if not kpis:
        lines.append("- 측정 기록 없음")
    else:
        lines += trend(kpis)
        last = kpis[-1]
        age = jp.days_since(last["date"])
        if last.get("customers") is None:
            lines.append("- ⚠ 마지막 측정에 고객수가 비어 있다. 이번 주 안에 `kpi add --customers N`으로 적는다.")
        if age >= jp.KPI_EVERY_DAYS:
            lines.append(f"- ⚠ 마지막 측정이 {age}일 전이다(주 1회 기준 초과).")
    lines += ["", "## 일일 수집(최근 7일, kpi_daily.jsonl)"]
    daily = []
    try:
        import json as _json
        with open(os.path.join(os.path.dirname(OUT), "kpi_daily.jsonl"), encoding="utf-8") as _f:
            daily = [_json.loads(l) for l in _f if l.strip()][-7:]
    except OSError:
        pass
    if not daily:
        lines.append("- 일일 수집 기록 없음(jitu_kpi_daily.py가 돌지 않았다)")
    for d in daily:
        lines.append(f"- {d['date']}: 조회 {d.get('views_24h')}, 방문 {d.get('visits_24h')}(EU 제외), 문의 7일 {d.get('inquiries_7d')}, 고객수 {d.get('customers')}")
    lines += ["", "## 열린 예측(점검일 7일 안 또는 지남)"]
    n = 0
    for r in jp.load("predict"):
        if r.get("verdict"):
            continue
        d = (dt.date.fromisoformat(r["check_on"]) - today).days
        if d <= 7:
            n += 1
            lines.append(f"- {r['id']} 점검일 {r['check_on']}({'지남' if d < 0 else f'{d}일 뒤'}): {r['change'][:70]} → 지표 {r['metric']}")
    if not n:
        lines.append("- 없음")
    lines += ["", "## 열린 결정 요청·검사 공백·고객 신호"]
    r = subprocess.run([sys.executable, os.path.join(HERE, "jitu_po.py"), "due"], capture_output=True, text=True, encoding="utf-8",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    body = (r.stdout or "").strip()
    lines.append(body if body else "- 기한 지난 것 없음")
    lines += ["", "## 슈퍼얼라인 점검(docs/align/지투.toml)"]
    a = subprocess.run([sys.executable, os.path.join(HERE, "align_check.py"), "지투"], capture_output=True, text=True, encoding="utf-8",
                       cwd=os.path.dirname(os.path.dirname(HERE)), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    lines.append((a.stdout or a.stderr or "점검 출력 없음").strip()[:2500])
    lines += ["", "## 이번 주 할 일(에이전트가 제안, 사장님이 정함)",
              "1. 위 경고를 해소한다(고객수 기록, 지난 예측 점검).",
              "2. 다음 개선 제안에는 `--kpi`로 고객수와의 연결을 쓴다(도구 관문).",
              "3. 숫자의 의미 해석이 필요하면 비티·덱스에게 같은 자료로 묻는다."]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"썼다: {OUT} ({len(lines)}줄)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
