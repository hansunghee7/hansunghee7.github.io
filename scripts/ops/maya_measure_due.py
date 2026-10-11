# -*- coding: utf-8 -*-
"""마야 KPI 측정 기한 점검(환경요건 R2, 2026-10-12). 링크드인 실험 장부(assets/data/linkedin_experiment.json)에서
게시 후 12시간 측정이 기한을 넘겼는데 비어 있는 글을 찾는다. 기한을 넘긴 글이 있으면 종료 코드 1(슈퍼얼라인 점검이 FAIL로 본다).
  python scripts/ops/maya_measure_due.py            기한 현황 출력(종료 코드 0/1)
  python scripts/ops/maya_measure_due.py set <글> key=value ...   글의 속성·상태 기록(published_at, status, attrs.image_source 등)
  python scripts/ops/maya_measure_due.py miss <글> "사유"          12시간 값을 못 쟀다고 남긴다(판정에서는 빠지고 기록은 남음)
기한: published_at(KST ISO)이 있으면 +12시간, 없으면 planned 날짜 09:00 KST +12시간. status가 cancelled인 글은 제외한다.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KST = timezone(timedelta(hours=9))
PATH = Path(__file__).resolve().parents[2] / "assets" / "data" / "linkedin_experiment.json"


def load():
    return json.loads(PATH.read_text(encoding="utf-8"))


def save(d):
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def due_at(p):
    if p.get("published_at"):
        return datetime.fromisoformat(p["published_at"]).astimezone(KST) + timedelta(hours=12)
    day = datetime.fromisoformat(p["planned"]).replace(hour=9, tzinfo=KST)
    return day + timedelta(hours=12)


def status(now=None):
    now = now or datetime.now(KST)
    rows = []
    for p in load()["posts"]:
        if p.get("status") == "cancelled":
            continue
        s = (p.get("snaps") or {}).get("12h")
        d = due_at(p)
        if s:
            state = "기록(미측정 사유)" if s.get("missed") else "측정 완료"
        elif now >= d:
            state = "기한 지남"
        else:
            state = "대기"
        rows.append((p["post"], p["title"], d.strftime("%m-%d %H:%M"), state))
    return rows


def main():
    a = sys.argv[1:]
    if a and a[0] == "set":
        d = load()
        p = next(x for x in d["posts"] if x["post"] == a[1])
        for kv in a[2:]:
            k, v = kv.split("=", 1)
            tgt = p
            *path, last = k.split(".")
            for seg in path:
                tgt = tgt.setdefault(seg, {})
            tgt[last] = {"true": True, "false": False}.get(v, v)
        save(d)
        print("ok", json.dumps(p, ensure_ascii=False)[:300])
        return 0
    if a and a[0] == "miss":
        d = load()
        p = next(x for x in d["posts"] if x["post"] == a[1])
        p.setdefault("snaps", {})["12h"] = {"missed": a[2], "at": datetime.now(KST).isoformat(timespec="minutes")}
        save(d)
        print("ok miss", a[1])
        return 0
    rows = status()
    late = [r for r in rows if r[3] == "기한 지남"]
    for r in rows:
        print(f"{r[3]:<10} 기한 {r[2]}  {r[1][:40]}")
    print(f"기한 지난 미측정: {len(late)}건")
    return 1 if late else 0


if __name__ == "__main__":
    sys.exit(main())
