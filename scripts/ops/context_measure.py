# -*- coding: utf-8 -*-
"""Carvit Context 대시보드 실측(2026-10-15 탐, 사장님: "카빗 컨텍스트 대시보드 완성해주세요").
우리 팀(Carvit 에이전트 팀)의 최근 7일 지표를 로컬 기록과 GitHub에서 계산해 JSON으로 쓴다. 판정 없이 계산만 한다.
지표 정의(시안 v8의 항목을 실제 기록으로 연결, 정의가 시안과 다른 곳은 한계를 JSON 'note'에 남긴다):
  - merged_pr_7d     : 병합 PR 수(작성자가 봇이 아닌 것). GitHub GraphQL.
  - lead_min_median  : 요청 완료 시간 = PR 열림에서 병합까지 중앙값(분). 이슈를 쓰지 않아 PR로 대신한다.
  - human_per_day    : 사람 개입 = '[사람 개입 필요]' 표시 건수/일(C:/work/_ops/human_touch_log.jsonl, 훅이 자동 기록).
  - revert_pct       : PR 되돌림 비율 = 제목이 Revert로 시작하거나 되돌림·롤백이 들어간 병합 PR / 병합 PR(최근 14일).
  - cpso_krw         : 성공 한 건당 비용 = 최근 7일 Vertex 호출 추정 비용(C:/work/_ops/vertex_usage.csv) / 병합 PR 수. GCP 비용만이라 클로드·Azure는 빠진 하한값이다.
  - docs_count       : 정본 문서 수 = origin/main의 docs/*.md.
이어받기 점수는 5문항 시험을 돌려야 해서 측정 전으로 둔다.
사용: python scripts/ops/context_measure.py [--out C:/work/_ops/context_pilot/measure_live.json]"""
import csv
import json
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "hansunghee7/hansunghee7.github.io"
OPS = Path("C:/work/_ops")
Q = """query($q:String!,$after:String){search(query:$q,type:ISSUE,first:100,after:$after){pageInfo{hasNextPage endCursor}
nodes{... on PullRequest{number title createdAt mergedAt author{login __typename}}}}}"""


def gh(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout


def merged_prs(since, until):
    q = f"repo:{REPO} is:pr is:merged merged:{since}..{until}"
    after, out = None, []
    while True:
        a = ["api", "graphql", "-f", f"query={Q}", "-f", f"q={q}"]
        if after:
            a += ["-f", f"after={after}"]
        d = json.loads(gh(a))["data"]["search"]
        out += d["nodes"]
        if not d["pageInfo"]["hasNextPage"]:
            return out
        after = d["pageInfo"]["endCursor"]


def is_bot(n):
    a = n.get("author") or {}
    login = a.get("login") or ""
    return a.get("__typename") == "Bot" or "[bot]" in login or login.startswith("app/")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OPS / "context_pilot" / "measure_live.json"
    today = datetime.now(timezone.utc).date()
    d7, d14 = (today - timedelta(days=6)).isoformat(), (today - timedelta(days=13)).isoformat()
    res = {"as_of": today.isoformat(), "window_7d": f"{d7}..{today.isoformat()}", "note": {}}
    p14 = [n for n in merged_prs(d14, today.isoformat()) if not is_bot(n)]
    p7 = [n for n in p14 if n["mergedAt"][:10] >= d7]
    res["merged_pr_7d"] = len(p7)
    lead = [(ts(n["mergedAt"]) - ts(n["createdAt"])).total_seconds() / 60 for n in p7]
    res["lead_min_median"] = round(statistics.median(lead), 1) if lead else None
    res["note"]["lead"] = "이슈를 쓰지 않아 PR 열림에서 병합까지로 대신함(시안의 이슈 열림에서 닫힘과 다름)"
    rev = [n for n in p14 if (n["title"].lower().startswith("revert") or "되돌" in n["title"] or "롤백" in n["title"])]
    res["revert_count_14d"], res["merged_pr_14d"] = len(rev), len(p14)
    res["revert_pct"] = round(100 * len(rev) / max(len(p14), 1), 2)
    since7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    touch = 0
    try:
        for ln in (OPS / "human_touch_log.jsonl").read_text(encoding="utf-8").splitlines():
            if ln.strip() and json.loads(ln).get("t", "") >= since7:
                touch += 1
    except OSError:
        touch = None
    res["human_touch_7d"] = touch
    res["human_per_day"] = round(touch / 7, 1) if touch is not None else None
    res["note"]["human"] = "시안은 비율(%)인데 분모(처리한 일 전체)가 기록되지 않아 하루 개입 건수로 대신함"
    krw = 0.0
    try:
        with open(OPS / "vertex_usage.csv", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["time"] >= since7:
                    krw += float(r.get("est_krw") or 0)
    except OSError:
        krw = None
    res["vertex_krw_7d"] = round(krw) if krw is not None else None
    res["cpso_krw"] = round(krw / len(p7)) if krw is not None and p7 else None
    res["note"]["cpso"] = "GCP Vertex 호출 추정 비용만 포함한 하한값(클로드·Azure·GitHub 제외)"
    repo = Path("C:/work/hansunghee7.github.io")  # 래퍼가 스크립트를 임시 폴더에 풀어 실행해도 git 기록은 공용 폴더에서 읽는다
    names = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(repo), "ls-tree", "-r", "--name-only", "origin/main"], capture_output=True, text=True, encoding="utf-8", timeout=60).stdout.split("\n")
    res["docs_count"] = sum(1 for x in names if x.startswith("docs/") and x.endswith(".md"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
