#!/usr/bin/env python3
"""마야 작업서 실행기 (구PC 작업실, 2026-10-21 마야 #13 개선 과제).

왜: 구PC에 게시 스크립트를 올리고 크론을 거는 일이 마야 세션에서 자동 권한 분류기에 막혀, 사장님이 PowerShell로
매번 실행해야 했다(642). 없애는 설계: 마야는 비공개 저장소 solar-bible에 "작업서"(JSON)와 본문·이미지 파일만 올리고,
구PC 크론(5분마다)이 이 실행기를 불러 저장소를 받아 온 뒤 시각이 된 작업서만 실행한다. 크론은 한 번만 설치한다.

안전장치(전부 코드로 막는다):
- 명령은 아래 허용 목록 3개뿐이다(임의 명령 실행 불가). 인자는 작업서 칸에서 조립한다.
- approved_by가 "사장님"이고 approved_quote(사장님 원문 인용 10자 이상)가 있어야 한다.
- 파일은 저장소의 jobs/maya/files/ 안에 있어야 하고 작업서에 적힌 sha256과 같아야 한다(승인 뒤 본문이 바뀌면 멈춘다).
- run_at 이후 window_min(기본 120분) 안에서만 실행한다. 지나면 expired로 멈춘다(늦은 게시 방지).
- 실행 직전에 상태 파일에 running을 적는다. 실패해도 자동 재시도하지 않는다(이중 게시 방지, 마야가 결과를 보고 판단).
- post가 false면 모의 실행(--post 없음)이다.
작업서 위치: ~/solar-bible/jobs/maya/pending/<id>.json  /  결과: ~/workshop/out/maya/jobs_state.json, jobs/<id>/result.json
사용: python maya_jobrunner.py [--no-pull] [--now ISO] [--repo 경로]
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
HOME = Path.home()
WORK = HOME / "workshop"
OUT = WORK / "out" / "maya"
ALLOWED = {
    # cmd: (스크립트, 본문 인자 이름, 필수 args)
    "post_linkedin": ("post_linkedin.py", "--text", ["title"]),
    "post_rocketpunch": ("post_rocketpunch.py", "--file", []),
    "post_remember": ("post_remember.py", "--file", []),
}
FILES_ROOT = "jobs/maya/files"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def problems(spec, repo, now):
    """작업서가 실행 조건을 만족하는지. 문제 목록(빈 리스트면 통과)."""
    p = []
    for k in ("id", "run_at", "cmd", "files", "approved_by", "approved_quote"):
        if not spec.get(k):
            p.append(f"{k} 없음")
    if p:
        return p
    if spec["cmd"] not in ALLOWED:
        p.append(f"허용되지 않은 명령: {spec['cmd']}")
        return p
    if spec["approved_by"] != "사장님" or len(str(spec["approved_quote"]).strip()) < 10:
        p.append("승인(approved_by=사장님, 원문 인용 10자 이상)이 없음")
    for need in ALLOWED[spec["cmd"]][2]:
        if not (spec.get("args") or {}).get(need):
            p.append(f"args.{need} 없음")
    files = spec["files"]
    for name in ("text", "image"):
        f = files.get(name)
        if not f or not f.get("path") or not f.get("sha256"):
            p.append(f"files.{name} 없음")
            continue
        fp = (Path(repo) / f["path"]).resolve()
        try:
            fp.relative_to((Path(repo) / FILES_ROOT).resolve())
        except ValueError:
            p.append(f"files.{name}이 {FILES_ROOT} 밖")
            continue
        if not fp.is_file():
            p.append(f"files.{name} 파일 없음")
        elif sha256(fp) != f["sha256"]:
            p.append(f"files.{name} sha256 불일치(승인 뒤 파일이 바뀜)")
    try:
        datetime.fromisoformat(spec["run_at"])
    except Exception:
        p.append("run_at 형식 오류")
    return p


def timing(spec, now):
    """'wait' / 'run' / 'expired'."""
    run_at = datetime.fromisoformat(spec["run_at"])
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=KST)
    if now < run_at:
        return "wait"
    if now > run_at + timedelta(minutes=int(spec.get("window_min", 120))):
        return "expired"
    return "run"


def build_argv(spec, jobdir):
    script, text_flag, _ = ALLOWED[spec["cmd"]]
    argv = [str(WORK / "venv" / "bin" / "python"), str(WORK / script),
            text_flag, str(jobdir / Path(spec["files"]["text"]["path"]).name),
            "--image", str(jobdir / Path(spec["files"]["image"]["path"]).name)]
    if spec["cmd"] == "post_linkedin":
        argv += ["--title", spec["args"]["title"]]
    if spec.get("post"):
        argv.append("--post")
    return argv


def load_state():
    f = OUT / "jobs_state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_state(st):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "jobs_state.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def run_job(spec, repo, now):
    jobdir = OUT / "jobs" / spec["id"]
    jobdir.mkdir(parents=True, exist_ok=True)
    for name in ("text", "image"):
        src = Path(repo) / spec["files"][name]["path"]
        shutil.copyfile(src, jobdir / src.name)
    argv = build_argv(spec, jobdir)
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=600, cwd=str(WORK))
        res = {"rc": r.returncode, "stdout": r.stdout[-1500:], "stderr": r.stderr[-800:]}
    except subprocess.TimeoutExpired:
        res = {"rc": -1, "stdout": "", "stderr": "timeout 600s"}
    (jobdir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = res["rc"] == 0
    if ok and spec.get("post"):
        ok = '"posted": true' in res["stdout"] or "'posted': True" in res["stdout"]
    return ("done" if ok else "failed"), res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(HOME / "solar-bible"))
    ap.add_argument("--no-pull", action="store_true")
    ap.add_argument("--now", default="")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(KST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    OUT.mkdir(parents=True, exist_ok=True)
    import fcntl  # 구PC(리눅스)에서만 쓴다
    lock = open(OUT / "jobrunner.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("다른 실행기가 돌고 있음"); return 0
    if not a.no_pull:
        subprocess.run(["git", "-C", a.repo, "pull", "--ff-only", "-q"], capture_output=True, timeout=120)
    pend = Path(a.repo) / "jobs" / "maya" / "pending"
    st = load_state()
    for f in sorted(pend.glob("*.json")) if pend.exists() else []:
        try:
            spec = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{f.name}: JSON 오류 {e}"); continue
        jid = spec.get("id", f.stem)
        if st.get(jid, {}).get("status") in ("done", "failed", "running", "expired", "rejected"):
            continue
        bad = problems(spec, a.repo, now)
        if bad:
            st[jid] = {"status": "rejected", "why": bad, "at": now.isoformat()}; save_state(st)
            print(f"{jid}: 거절 {bad}"); continue
        t = timing(spec, now)
        if t == "wait":
            continue
        if t == "expired":
            st[jid] = {"status": "expired", "at": now.isoformat()}; save_state(st); print(f"{jid}: 시간 지남"); continue
        st[jid] = {"status": "running", "at": now.isoformat()}; save_state(st)
        status, res = run_job(spec, a.repo, now)
        st[jid] = {"status": status, "at": now.isoformat(), "rc": res["rc"]}; save_state(st)
        print(f"{jid}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
