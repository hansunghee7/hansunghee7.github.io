# -*- coding: utf-8 -*-
"""GCP Vertex 실제 사용량을 API로 읽는다(N163, 2026-10-05 탐, 사장님 지시 "구글 클라우드 사용량은 물어보지 말고 API로 끌어가서 확인"):
Cloud Monitoring의 `aiplatform.googleapis.com/publisher/online_serving/token_count`(프로젝트의 모든 호출자 합계, 모델·입출력별 토큰)에
Cloud Billing 카탈로그의 공개 단가(원/토큰)를 곱해 하루(한국시간) 지출을 계산한다. 호출자별 분해는 불가(프로젝트 합계).
왜: 우리 호출 기록(vertex_usage.csv)은 ask_vertex.py 경유분만 담고, 단가도 추정값이라 10/5 실측에서 실제의 1/200 수준(₩170 vs 약 ₩33,000)이었다.
한계: 크레딧 잔액 자체는 API로 못 읽는다(결제 화면 전용). 그래서 잔액 = vertex_budget.json의 기준 잔액(기준일 시점) − 그 뒤 API 실사용 지출로 계산한다.
인증: gcloud 토큰(hansunghee7), 값은 출력하지 않는다. 캐시 10분: C:/work/_ops/gcp_usage_cache.json.
사용: python scripts/ops/gcp_usage.py   (최근 9일 일별 토큰·지출과 추세 출력)"""
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = "project-e59cbc25-e96a-44f5-ac6"
ACCOUNT = "hansunghee7@gmail.com"
CACHE = Path(r"C:\work\_ops\gcp_usage_cache.json")
KST = timezone(timedelta(hours=9))
# 공개 단가(Cloud Billing 카탈로그 SKU, 원/토큰 × 1e6 = 원/백만 토큰, 2026-10-05 확인): 3.6·3.8 Flash Global 텍스트
PRICE = {"input": 2038.125, "output": 10190.625}  # 원/백만 토큰. 그 밖 모델은 같은 값으로 가정(과대 쪽)


def _token():
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    return subprocess.run([exe, "auth", "print-access-token", f"--account={ACCOUNT}"], capture_output=True, text=True, timeout=60,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()


def _fetch(days=9):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    q = urllib.parse.urlencode({"filter": 'metric.type="aiplatform.googleapis.com/publisher/online_serving/token_count"',
                                "interval.startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "interval.endTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "aggregation.alignmentPeriod": "3600s", "aggregation.perSeriesAligner": "ALIGN_SUM"})
    req = urllib.request.Request(f"https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries?{q}", headers={"Authorization": "Bearer " + _token()})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.loads(r.read().decode("utf-8", "replace"))
    daily = {}
    for ts in body.get("timeSeries", []):
        typ = ts["metric"]["labels"].get("type")
        model = ts["resource"]["labels"].get("model_user_id") or "?"
        for p in ts.get("points", []):
            t = datetime.fromisoformat(p["interval"]["endTime"].replace("Z", "+00:00")).astimezone(KST)
            d = daily.setdefault(t.strftime("%Y-%m-%d"), {"input": 0, "output": 0, "models": {}})
            v = int(p["value"].get("int64Value", 0))
            d[typ] = d.get(typ, 0) + v
            d["models"][model] = d["models"].get(model, 0) + v
    for d in daily.values():
        d["krw"] = round(d["input"] / 1e6 * PRICE["input"] + d["output"] / 1e6 * PRICE["output"], 1)
    return daily


def daily_usage(max_age=600):
    """{날짜(KST): {input, output, krw, models}}  캐시 10분. API가 막히면 캐시를, 캐시도 없으면 빈 dict."""
    try:
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        if time.time() - c["at"] < max_age:
            return c["daily"]
    except (OSError, ValueError, KeyError):
        c = None
    try:
        daily = _fetch()
        CACHE.write_text(json.dumps({"at": time.time(), "daily": daily}, ensure_ascii=False), encoding="utf-8")
        return daily
    except Exception:  # noqa: BLE001
        return c["daily"] if c else {}


def today_krw():
    return daily_usage().get(datetime.now(KST).strftime("%Y-%m-%d"), {}).get("krw", 0.0)


def spent_since(start, before=None):
    return round(sum(v["krw"] for d, v in daily_usage().items() if d >= start and (before is None or d < before)), 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    du = daily_usage(0)
    for d in sorted(du):
        v = du[d]
        print(f"{d}  입력 {v['input']:>9,}  출력 {v['output']:>9,}  지출 약 ₩{v['krw']:>9,.0f}  {v['models']}")
