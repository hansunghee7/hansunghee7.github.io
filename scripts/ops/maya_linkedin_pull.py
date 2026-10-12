# -*- coding: utf-8 -*-
"""구PC가 매일 21:05 KST에 읽는 링크드인 글별 성과(~/workshop/out/maya/latest.json)를 가져와
maya_measure_due.py가 읽는 형식(C:/work/_ops/maya_linkedin/<날짜_시각>.json, maya_linkedin_latest.json)으로 바꿔 저장한다.
사장님 지시 2026-10-12: 구PC 무인 프로필로 매일 자동 읽기. 읽기 자체는 구PC cron(goosolar/workshop/read_maya_linkedin.py)이 한다.
  python scripts/ops/maya_linkedin_pull.py            가져오기(성공 0, 실패 1)
읽은 시각이 36시간보다 오래된 파일이면 실패로 본다(구PC 읽기가 멈춘 것).
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KST = timezone(timedelta(hours=9))
OUT = Path("C:/work/_ops/maya_linkedin")


def main():
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", "goosolar", "cat ~/workshop/out/maya/latest.json"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not r.stdout.strip():
        print("구PC에서 latest.json을 못 가져옴:", (r.stderr or "")[-200:])
        return 1
    d = json.loads(r.stdout)
    at = datetime.strptime(d["fetched_at_kst"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    if datetime.now(KST) - at > timedelta(hours=36):
        print("읽은 시각이 36시간보다 오래됨:", d["fetched_at_kst"])
        return 1
    rec = {"collected": at.isoformat(timespec="minutes"), "source": "goosolar read_maya_linkedin.py",
           "posts": [{"title": p["head"], "likes": p["reactions"], "impressions": p["impressions"], "age": p["age"]}
                     for p in d["posts"]]}
    OUT.mkdir(parents=True, exist_ok=True)
    name = at.strftime("%Y-%m-%d_%H%M") + ".json"
    (OUT / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (OUT.parent / "maya_linkedin_latest.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("ok", name, len(rec["posts"]), "글")
    return 0


if __name__ == "__main__":
    sys.exit(main())
