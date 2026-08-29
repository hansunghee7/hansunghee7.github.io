"""
Microsoft Clarity Data Export API에서 UX 품질 지표를 가져와
assets/data/clarity.json으로 저장하는 스크립트. fetch_ga4.py와 같은 패턴 --
수집은 여기서, 화면은 스튜디오(insight-7b3e9f2c/)의 정적 JS가 그린다.

이 API의 제약(공식 문서 기준)이 설계를 결정한다:
  - 최근 1~3일 데이터만 제공 -> 장기 추이는 여기서 매일 하루치를 받아
    history에 "누적"해야만 남는다. 하루라도 수집이 빠지면 그 날짜는 영구 공백.
  - 프로젝트당 하루 10회 호출 제한 -> 한 번 실행에 3회만 쓴다
    (전체 합계 1회 + URL별 1회 + 소스별 1회). cron이 하루 두 번 돌아도
    6회라 한도 안이다.
  - 세션 녹화 영상은 API로 제공되지 않는다 -> 녹화는 대시보드에서 직접 본다.

받는 지표: 트래픽, 관여 시간, 스크롤 깊이, 그리고 UX 문제 신호들
(분노 클릭 RageClick, 죽은 클릭 DeadClick, 스크립트 에러, 빠른 이탈 Quickback).
URL별 분해는 "어느 페이지에서 사용자가 막히는가"를, 소스별 분해는
"어느 유입 경로의 방문 품질이 좋은가"를 보기 위한 것.

인증 토큰(CLARITY_API_TOKEN)은 GitHub Actions Secrets에서만 주입받는다 --
저장소나 대화에 절대 남기지 말 것. 응답의 숫자가 문자열로 오는 경우가 있어
가볍게 숫자로 정규화하되, 필드 구성이 문서와 다를 수 있으므로(문서 스스로
"추가 필드가 있을 수 있다"고 명시) 모르는 필드도 버리지 않고 그대로 둔다.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

OUT_PATH = "assets/data/clarity.json"
API_URL = "https://www.clarity.ms/export-data/api/v1/project-live-insights"
HISTORY_MAX_DAYS = 400


def call_api(token, num_of_days, dimension1=None):
    params = {"numOfDays": str(num_of_days)}
    if dimension1:
        params["dimension1"] = dimension1
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(value):
    """API가 숫자를 문자열로 주는 경우("9554")를 숫자로. 아니면 그대로."""
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    return value


def to_metric_map(payload):
    """[{metricName, information:[...]}] -> {metricName: [rows]} 로 정리."""
    out = {}
    for item in payload if isinstance(payload, list) else []:
        name = item.get("metricName", "unknown")
        rows = []
        for row in item.get("information", []) or []:
            rows.append({k: normalize(v) for k, v in row.items()})
        out[name] = rows
    return out


def load_existing():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    token = os.environ.get("CLARITY_API_TOKEN")
    if not token:
        sys.exit("CLARITY_API_TOKEN 환경변수가 없습니다.")

    now = datetime.now(timezone.utc)
    # numOfDays=1은 "호출 시점 기준 지난 24시간". 대략 전날 하루치로 보고
    # 전날 날짜로 적재한다 -- 같은 날 여러 번 실행되면 마지막 값으로 덮어쓴다.
    window_date = (now - timedelta(days=1)).date().isoformat()

    try:
        daily_totals = to_metric_map(call_api(token, 1))
        by_url = to_metric_map(call_api(token, 3, "URL"))
        by_source = to_metric_map(call_api(token, 3, "Source"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            # 하루 호출 한도 초과 -- 기존 파일을 지우지 말고 조용히 넘어간다.
            print("Clarity API 일일 호출 한도(10회) 초과 -- 이번 실행은 건너뜁니다.")
            return
        if e.code in (401, 403):
            sys.exit(f"Clarity API 인증 실패(HTTP {e.code}) -- 토큰이 유효한지 확인하세요.")
        raise

    data = load_existing()
    history = data.get("history", [])
    history = [h for h in history if h.get("date") != window_date]
    history.append({"date": window_date, "metrics": daily_totals})
    history.sort(key=lambda h: h.get("date", ""))
    history = history[-HISTORY_MAX_DAYS:]

    data = {
        "updated_at": now.isoformat(),
        "note": "history는 매일 지난 24시간 집계를 누적한 것. latest_*는 최근 3일 창.",
        "history": history,
        "latest_by_url": by_url,
        "latest_by_source": by_source,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH} (history {len(history)}일)")


if __name__ == "__main__":
    main()
