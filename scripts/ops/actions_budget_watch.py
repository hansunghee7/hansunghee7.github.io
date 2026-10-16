"""비공개 저장소 GitHub Actions 사용량 감시(2026-10-16 탐, 공정 카드 탐#65·#109).

사장님 10/15 원문: "한도 초과 시 소액 상한을 열어 두고, 앞으로 유료결제가 최소화되도록 관리". 상한은 5달러.
깃허브 청구 API는 gh 토큰에 user 권한이 없어 못 읽으므로, 실행 기록으로 이번 달 분을 근사한다(실행마다 올림).
붉음(종료 코드 1) = 추정 유료 금액이 상한의 80% 이상, 또는 오늘 사고 우회 배포가 있음. watch.py가 알린다.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPOS = ["hansunghee7/simplifier-saegim", "hansunghee7/simplifier-cxo-db", "hansunghee7/shorts-lab",
         "hansunghee7/solar-bible", "hansunghee7/carvit-ai", "hansunghee7/saegim-pass"]
FREE_MIN = 2000
CAP_USD = 5.0
USD_PER_MIN = 0.006  # 리눅스 기본 러너 단가 추정. 청구 화면과 어긋나면 이 값을 맞춘다
ALERT_RATIO = 0.8
DEPLOY_WF = "deploy-cloud-run.yml"
KST = timezone(timedelta(hours=9))
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def gh(args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", creationflags=FLAGS)
    return r.stdout if r.returncode == 0 else ""


def minutes(run):
    try:
        s = datetime.fromisoformat(run["startedAt"].replace("Z", "+00:00"))
        e = datetime.fromisoformat(run["updatedAt"].replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return 0
    return max(1, -(-int((e - s).total_seconds()) // 60))


def main():
    now = datetime.now(KST)
    month_start = now.strftime("%Y-%m-01")
    total = 0
    for repo in REPOS:
        if gh(["api", f"repos/{repo}", "--jq", ".private"]).strip() != "true":
            continue
        out = gh(["run", "list", "-R", repo, "--limit", "1000", "--created", f">={month_start}",
                  "--json", "startedAt,updatedAt"])
        total += sum(minutes(r) for r in json.loads(out or "[]"))
    paid = max(0, total - FREE_MIN) * USD_PER_MIN

    # 오늘(KST) 수동 배포와 사고 우회 횟수
    since = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runs = json.loads(gh(["api", f"repos/hansunghee7/simplifier-saegim/actions/workflows/{DEPLOY_WF}/runs"
                                 f"?event=workflow_dispatch&created=%3E%3D{since}&per_page=100",
                          "--jq", "[.workflow_runs[] | {id, sha: .head_sha, ok: (.conclusion == \"success\"), suite: .check_suite_id}]"]) or "[]")
    incidents = []
    for r in runs:
        notes = gh(["api", f"repos/hansunghee7/simplifier-saegim/check-suites/{r['suite']}/check-runs",
                    "--jq", "[.check_runs[].output.annotations_count] | add"]).strip()
        if notes and notes != "0" and notes != "null":
            ann = gh(["api", f"repos/hansunghee7/simplifier-saegim/check-suites/{r['suite']}/check-runs",
                      "--jq", ".check_runs[].id"]).split()
            for cid in ann:
                msg = gh(["api", f"repos/hansunghee7/simplifier-saegim/check-runs/{cid}/annotations",
                          "--jq", '.[].message | select(startswith("사고 우회 배포"))']).strip()
                if msg:
                    incidents.append(msg)
    manual_ok = len({r["sha"] for r in runs if r["ok"]})

    print(f"이번 달 비공개 저장소 Actions 약 {total}분(무료 {FREE_MIN}분), 추정 유료 ${paid:.2f} / 상한 ${CAP_USD:.0f}"
          f" · 오늘 수동 배포 성공 {manual_ok}건(상한 3) · 사고 우회 {len(incidents)}건")
    for m in incidents:
        print(" -", m)
    red = paid >= CAP_USD * ALERT_RATIO or bool(incidents)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
