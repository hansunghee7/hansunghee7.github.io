#!/usr/bin/env python3
"""개인 GCP 무료 크레딧(Vertex) 사용량·만료 감시(2026-10-03 탐, 대장 N120). 감시 대장(jobs.toml)의 cmd 작업이 부른다.

왜: 사장님 방침(10/3)으로 비티·리서치가 이 크레딧을 쓴다. 조용히 바닥나거나 만료되지 않게 한다.
읽는 곳: C:/work/_ops/vertex_usage.csv (ask_vertex.py가 호출마다 한 줄). 추정 비용이므로 결제 보고서와 가끔 대조한다.
붉음(종료 코드 1): 오늘 추정 비용이 하루 상한의 80% 이상 / 만료 14일 전부터 / 7일 추정 합계가 남은 기간 예산(일 상한 x 7)을 넘음.
사용: python scripts/ops/vertex_watch.py
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date, datetime, timedelta
from pathlib import Path

LOG = Path("C:/work/_ops/vertex_usage.csv")
DAY_KRW = float(os.environ.get("VERTEX_DAY_KRW", "3400"))  # ask_vertex.py와 같은 값
EXPIRY = date(2026, 12, 23)  # 무료 체험 크레딧 만료(결제 화면 10/3)
WARN_DAYS = 14


def main():
    today = date.today()
    d_left = (EXPIRY - today).days
    n_today, krw_today, krw_week = 0, 0.0, 0.0
    if LOG.exists():
        since = datetime.now() - timedelta(days=7)
        for r in csv.DictReader(LOG.open(encoding="utf-8")):
            t = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S")
            krw = float(r["est_krw"] or 0)
            if t >= since:
                krw_week += krw
            if t.date() == today:
                n_today += 1
                krw_today += krw
    try:  # 실사용(Cloud Monitoring 토큰×공개 단가)과 다이나믹 일 상한 기준으로 판정(10/5: 우리 기록은 실제의 1/200이었음)
        import gcp_usage
        import dynamic_quota
        krw_today = max(krw_today, gcp_usage.today_krw())
        krw_week = max(krw_week, gcp_usage.spent_since((today - timedelta(days=6)).isoformat()))
        DAY = dynamic_quota.vertex_day_cap()
    except Exception:  # noqa: BLE001
        DAY = DAY_KRW
    msgs, red = [], False
    try:
        rem = dynamic_quota.remaining(today)
        fl = dynamic_quota.budget().get('floor_remaining', 100000)
        if rem < fl + 50000:
            red = True; msgs.append(f"남은 크레딧 추정 ₩{rem:,.0f}가 바닥선 ₩{fl:,.0f}+5만 이내(관찰 기간 중이어도 평시 상한으로 복귀 임박)")
    except Exception:  # noqa: BLE001
        rem = None
    if krw_today >= DAY * 0.8:
        red = True; msgs.append(f"오늘 실사용 약 ₩{krw_today:,.0f}가 다이나믹 일 상한 ₩{DAY:,.0f}의 80% 이상")
    if krw_week > DAY * 7:
        red = True; msgs.append(f"7일 실사용 약 ₩{krw_week:,.0f}가 주간 예산 ₩{DAY*7:,.0f} 초과")
    if d_left <= WARN_DAYS:
        red = True; msgs.append(f"크레딧 만료 {d_left}일 전({EXPIRY}), 남은 일 정리·유료 전환 여부 사장님 결정")
    print(f"Vertex 크레딧: 오늘 우리 호출 {n_today}회·실사용 약 ₩{krw_today:,.0f} / 7일 ₩{krw_week:,.0f} / 만료까지 {d_left}일" + (" | " + "; ".join(msgs) if msgs else ""))
    return 1 if red else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 원화 기호가 cp949 콘솔에서 깨지지 않게(quota.py와 같은 처리)
    sys.exit(main())
