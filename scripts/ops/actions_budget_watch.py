"""비공개 저장소 GitHub Actions 사용량 감시(2026-10-16 탐, 공정 카드 탐#65·#109).

사장님 10/15 원문: "한도 초과 시 소액 상한을 열어 두고, 앞으로 유료결제가 최소화되도록 관리".
10/18 사장님이 5달러를 충전했고(5,000원과 같은 뜻) 추가 충전은 없다. 청구 화면 예산은 $5.00(10/18 밤 실측 $1.66 사용). 추정은 잡마다 분을 올려 실제보다 높게 나온다.
깃허브 청구 API는 gh 토큰에 user 권한이 없어 못 읽으므로, 실행 기록으로 이번 달 분을 근사한다(실행마다 올림).
붉음(종료 코드 1) = 추정 유료 금액이 상한의 80% 이상, 또는 오늘 사고 우회 배포가 있음. watch.py가 알린다.
측정 불완전(종료 코드 2) = gh 호출 실패(반환코드≠0, API 한도 403 포함)가 1건이라도 있음. 이때 합계는 하한값이다.
"""
import base64
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPOS = ["hansunghee7/simplifier-saegim", "hansunghee7/simplifier-cxo-db", "hansunghee7/shorts-lab",
         "hansunghee7/solar-bible", "hansunghee7/carvit-staging", "hansunghee7/carvit-insight-data",
         "hansunghee7/saegim-pass"]
FREE_MIN = 2000
CAP_USD = 5.0  # 청구 화면 예산 상한(사장님 10/18 충전액)
USD_PER_MIN = 0.006  # 리눅스 기본 러너 단가 추정. 청구 화면과 어긋나면 이 값을 맞춘다
ALERT_RATIO = 0.8
DEPLOY_WF = "deploy-cloud-run.yml"
KST = timezone(timedelta(hours=9))
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


_fail_lock = threading.Lock()
_fail_count = 0


def gh(args, tolerate_404=False):
    """gh 실행. 실패(반환코드≠0)는 빈 문자열을 돌려주되 실패 횟수를 센다(스레드 안전)."""
    global _fail_count
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", creationflags=FLAGS,
                           timeout=90)
    except subprocess.TimeoutExpired:
        r = subprocess.CompletedProcess(args, 124, "", "timeout")
    if r.returncode == 0:
        return r.stdout
    if tolerate_404 and "404" in (r.stderr or ""):
        return ""
    with _fail_lock:
        _fail_count += 1
    print("gh 실패:", " ".join(args)[:120], "|", (r.stderr or "").strip()[:100], file=sys.stderr)
    return ""


RUNS_ON = re.compile(r"runs-on:\s*\[?\s*[\"']?(ubuntu-|windows-|macos-)", re.I)


def host_pinned_workflows(repo):
    """runs-on에 GitHub 호스트 라벨을 직접 지정한 워크플로 파일명 목록(알림 전용)."""
    names = gh(["api", f"repos/{repo}/contents/.github/workflows", "--jq",
                '[.[] | select(.name | test("[.]ya?ml$")) | .name] | .[]'], tolerate_404=True).split()
    hit = []
    for n in names:
        b64 = gh(["api", f"repos/{repo}/contents/.github/workflows/{n}", "--jq", ".content"]).strip()
        try:
            text = base64.b64decode(b64).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        if RUNS_ON.search(text):
            hit.append(n)
    return hit


def job_minutes(arg):
    """run 하나의 잡들 중 자체 실행기가 아닌 잡만 잡마다 분 올림(최소 1분)해 합산."""
    repo, rid = arg
    out = gh(["api", f"repos/{repo}/actions/runs/{rid}/jobs?per_page=100", "--jq",
              "[.jobs[] | {l: .labels, s: .started_at, c: .completed_at}]"])
    try:
        jobs = json.loads(out or "[]")
    except ValueError:
        return 0
    total = 0
    for j in jobs:
        if "self-hosted" in (j.get("l") or []):
            continue
        try:
            a = datetime.fromisoformat(j["s"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(j["c"].replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        total += max(1, -(-int(max(0, (b - a).total_seconds())) // 60))
    return total


def month_runs(repo, month_start):
    """이번 달 run id를 2일 구간으로 나눠 모은다(목록 1000개 제한 회피, id로 중복 제거)."""
    runs = {}
    d0 = datetime.fromisoformat(month_start)
    end = datetime.now() + timedelta(days=1)
    while d0 < end:
        d1 = d0 + timedelta(days=2)
        rng = f"{d0:%Y-%m-%d}..{d1:%Y-%m-%d}"
        part = json.loads(gh(["run", "list", "-R", repo, "--limit", "1000", "--created", rng,
                              "--json", "databaseId"]) or "[]")
        if len(part) >= 1000:
            print("경고: 구간 잘림", repo, rng)
        for r in part:
            runs[r["databaseId"]] = r
        d0 = d1
    return list(runs)


def main():
    now = datetime.now(KST)
    month_start = now.strftime("%Y-%m-01")
    global _fail_count
    _fail_count = 0
    total = 0
    pinned = []
    for repo in REPOS:
        if gh(["api", f"repos/{repo}", "--jq", ".private"]).strip() != "true":
            continue
        pinned += [(repo, n) for n in host_pinned_workflows(repo)]
        ids = month_runs(repo, month_start)
        with ThreadPoolExecutor(8) as ex:
            total += sum(ex.map(job_minutes, [(repo, i) for i in ids]))
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
          f" · 오늘 수동 배포 성공 {manual_ok}건 · 사고 우회 {len(incidents)}건"
          + (" (하한값)" if _fail_count else ""))
    for m in incidents:
        print(" -", m)
    by_repo = {}
    for repo, n in pinned:
        by_repo.setdefault(repo.split("/")[-1], []).append(n)
    detail = "; ".join(f"{r}: {', '.join(v)}" for r, v in by_repo.items())
    print(f"호스트 직접 지정 워크플로: {len(pinned)}개" + (f" (저장소: {detail})" if pinned else ""))
    if _fail_count:
        print(f"측정 불완전: 호출 실패 {_fail_count}건 (위 합계는 하한값)")
        return 2
    red = paid >= CAP_USD * ALERT_RATIO or bool(incidents)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
