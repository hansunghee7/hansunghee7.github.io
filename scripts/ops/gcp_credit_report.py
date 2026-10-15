# -*- coding: utf-8 -*-
"""GCP 크레딧 일일 보고(타미 시험 A, 2026-10-15 탐 #71 ②): Vertex 크레딧 잔액·소진 속도·회사/개인 비중을 한 줄로.
왜: 사장님이 크레딧 숫자를 손으로 읽어 주는 것은 스펙 위반이라는 기준(10/8). 규칙으로 정해진 계산만 하고 판정은 하지 않는다(타미 전담 후보 기준).
Claude API 크레딧은 credit_daily_report.py가 따로 맡는다(이름이 겹치지 않게 gcp_ 접두).
읽는 곳: C:/work/_ops/vertex_budget.json(기준 잔액·만료), gcp_usage_cache*.json(프로젝트별 일별 실사용, gcp_usage.py가 10분 캐시로 갱신).
한계: 크레딧 잔액은 API로 못 읽어 기준 잔액에서 이후 실사용을 뺀 추정이다. Azure·AWS·GitHub는 이 스크립트에 포함하지 않는다(각자 확인 경로가 다름).
사용: python scripts/ops/gcp_credit_report.py [--save]   (--save: C:/work/_ops/gcp_credit_report_YYYYMMDD.txt에도 기록)"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

OPS = Path("C:/work/_ops")
PROJECTS = (("개인", "gcp_usage_cache.json"), ("회사", "gcp_usage_cache_simplifier-vertex-credit.json"))


def used_since(cache, since):
    try:
        d = json.loads((OPS / cache).read_text(encoding="utf-8")).get("daily", {})
    except Exception:
        return None, {}
    per = {day: float(v.get("krw", 0) if isinstance(v, dict) else v or 0) for day, v in d.items() if day > since}
    return sum(per.values()), per


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    b = json.loads((OPS / "vertex_budget.json").read_text(encoding="utf-8"))
    today = date.today()
    expiry = date.fromisoformat(b["expiry"])
    left_days = max((expiry - today).days, 1)
    parts, total, daily_all = {}, 0.0, {}
    for name, f in PROJECTS:
        u, per = used_since(f, b["as_of"])
        if u is None:
            print(f"GCP 크레딧 일일 보고 {today:%m/%d}: 실사용 캐시({f})를 읽지 못했습니다. gcp_usage.py를 먼저 실행하세요.")
            return 1
        parts[name] = u
        total += u
        for day, k in per.items():
            daily_all[day] = daily_all.get(day, 0) + k
    remain = b["balance"] - total
    reserved = b.get("reserved", [])
    res_txt = (" 예약 " + ", ".join(f"{r['who']} ₩{r['krw']:,}" for r in reserved) + "(예약분은 실사용이 아니라 상한 표시).") if reserved else ""
    last3 = [daily_all.get((today - timedelta(days=i)).isoformat(), 0.0) for i in (1, 2, 3)]
    avg3 = sum(last3) / 3
    need = remain / left_days
    share = {k: (round(v / total * 100) if total else 0) for k, v in parts.items()}
    status = "속도 부족(만료 전 소진 어려움)" if avg3 < need * 0.5 else ("속도 보통" if avg3 < need else "속도 충분")
    line = (f"GCP 크레딧 일일 보고 {today:%m/%d}: 잔액 약 ₩{remain:,.0f}(기준 ₩{b['balance']:,} {b['as_of']} − 이후 실사용 ₩{total:,.0f}), "
            f"만료 {b['expiry']} D-{left_days}, 하루 필요 ₩{need:,.0f}, 최근 3일 평균 ₩{avg3:,.0f} → {status}. "
            f"프로젝트별 비중 회사 {share.get('회사', 0)}% 개인 {share.get('개인', 0)}%. 잔액은 추정이며 Azure·AWS·GitHub는 포함하지 않음." + res_txt)
    print(line)
    if "--save" in sys.argv:
        (OPS / f"gcp_credit_report_{today:%Y%m%d}.txt").write_text(line + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
