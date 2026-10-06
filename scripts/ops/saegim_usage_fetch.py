#!/usr/bin/env python3
"""새김 서버 사용량 산출물을 받아 로컬에 쌓고 일일 요약 한 줄을 남긴다(대장 N164·G3, 2026-10-06 탐).

simplifier-cxo-db의 gcp-usage 워크플로가 만든 artifact(saegim-usage)의 가장 최근 성공 실행을 받아
C:/work/_ops/saegim_usage/<수집일>.json 으로 저장하고, C:/work/_ops/saegim_usage_daily.md 에 날짜별 한 줄을 쓴다.
같은 collected_at은 건너뛰고, 같은 수집일의 이후 수집값은 별도 파일로 저장한다. 운영 DB 표는 새 표 DDL이 필요해 아직 쓰지 않는다(파일이 정본, 10/31 결정 자료의 재료).
종료 코드 0 = 정상, 1 = 성공한 실행·산출물 없음, 2 = gh 오류.
"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = "hansunghee7/simplifier-cxo-db"
OUT = Path("C:/work/_ops/saegim_usage")
SUMMARY = Path("C:/work/_ops/saegim_usage_daily.md")
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def pick_dest(out_dir, data):
    """Return a destination for data, or None if its collected_at is already saved."""
    collected_at = data["collected_at"]
    day = collected_at[:10]
    out_dir = Path(out_dir)

    for path in out_dir.glob(f"{day}*.json"):
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if saved.get("collected_at") == collected_at:
            return None

    first = out_dir / f"{day}.json"
    if not first.exists():
        return first

    timestamp = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    utc_time = timestamp.astimezone(timezone.utc).strftime("%H%M%S")
    base = out_dir / f"{day}-{utc_time}.json"
    if not base.exists():
        return base
    suffix = 2
    while True:
        candidate = out_dir / f"{day}-{utc_time}-{suffix}.json"
        if not candidate.exists():
            return candidate
        suffix += 1


def gh(args, timeout=120):
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=NW)


def main():
    r = gh(["run", "list", "--repo", REPO, "--workflow", "gcp-usage.yml", "--limit", "10", "--json", "databaseId,conclusion,createdAt,event"])
    if r.returncode:
        print("gh 오류", r.stderr[:120])
        return 2
    ok = [x for x in json.loads(r.stdout) if x["conclusion"] == "success"]
    if not ok:
        print("성공한 실행 없음")
        return 1
    run = ok[0]
    with tempfile.TemporaryDirectory() as tmp:
        d = gh(["run", "download", str(run["databaseId"]), "--repo", REPO, "-n", "saegim-usage", "-D", tmp])
        f = Path(tmp) / "saegim_usage.json"
        if d.returncode or not f.exists():
            print("산출물 없음", d.stderr[:120])
            return 1
        data = json.loads(f.read_text(encoding="utf-8"))
    day = data["collected_at"][:10]
    OUT.mkdir(parents=True, exist_ok=True)
    dest = pick_dest(OUT, data)
    if dest is None:
        print(f"{day} 이미 있음(실행 {run['databaseId']}, {run['event']})")
        return 0
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    last = max(data["requests_daily"])
    cost = data.get("cost_krw_est", {})
    line = (f"{data['collected_at'][:16]} | 마지막 집계일 {last} 요청 {data['requests_daily'][last]:.0f} | 30일 요청 {data['requests_30d']} | 5xx(30일) {data['errors_5xx_30d']} | "
            f"인스턴스 초(30일) {data['billable_instance_seconds_30d']} | 비용 추정 무료분 제외 {cost.get('no_free_tier')}원·포함 {cost.get('with_free_tier')}원 | 실행 {run['databaseId']}({run['event']})")
    new = not SUMMARY.exists()
    with SUMMARY.open("a", encoding="utf-8") as s:
        if new:
            s.write("# 새김 서버 사용량 일일 요약 (saegim_usage_fetch.py가 한 줄씩 추가)\n\n")
        s.write(line + "\n")
    print("저장", dest.name, "|", line[:120])
    return 0


if __name__ == "__main__":
    sys.exit(main())
