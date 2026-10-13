# -*- coding: utf-8 -*-
"""링크드인 게시 후 12시간 전용 읽기 진입점(신PC 작업 스케줄러가 10분마다 실행, 대부분은 '읽을 글 없음'으로 즉시 종료).
  python scripts/ops/linkedin_12h_read.py            필요하면 1회 읽기(하루 최대 2회, 차단 신호 시 그날 중지)
  python scripts/ops/linkedin_12h_read.py --plan     읽기 시각 목록만 출력(링크드인 접속 없음)
읽기는 기존 read_maya_linkedin.py(구PC SNS 크롬)를 그대로 호출하고, 결과는 maya_linkedin_pull.py 로 가져온 뒤 스냅샷 jsonl 에 쌓는다.
상태: C:/work/_ops/linkedin_collect/state_12h.json, 스냅샷: snapshots.jsonl. 자격증명·쿠키는 다루지 않는다.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkedin_12h as L  # noqa: E402

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "assets" / "data" / "linkedin_experiment.json"
BASE = Path("C:/work/_ops/linkedin_collect")
STATE = BASE / "state_12h.json"
SNAPS = BASE / "snapshots.jsonl"
LATEST = Path("C:/work/_ops/maya_linkedin_latest.json")
NOFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
READ_CMD = ["ssh", "-o", "ConnectTimeout=20", "goosolar", "python3 ~/workshop/read_maya_linkedin.py"]  # 읽기 로직 불변, 호출만


def run_read():
    """구PC 읽기 1회 + 가져오기. (ok, blocked, 출력)"""
    r = subprocess.run(READ_CMD, capture_output=True, text=True, encoding="utf-8", timeout=240, creationflags=NOFLAGS)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        return False, L.is_block_text(out), out[-300:]
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "ops" / "maya_linkedin_pull.py")],
                       capture_output=True, text=True, encoding="utf-8", timeout=180, creationflags=NOFLAGS)
    return p.returncode == 0, False, ((p.stdout or "") + (p.stderr or ""))[-300:]


def _latest_as_read():
    """pull 이 만든 maya_linkedin_latest.json(collected/posts)을 스냅샷 입력 형식으로 맞춘다."""
    d = json.loads(LATEST.read_text(encoding="utf-8"))
    return {"fetched_at_kst": datetime.fromisoformat(d["collected"]).strftime("%Y-%m-%d %H:%M"),
            "posts": [{"head": p["title"], "reactions": p["likes"], "impressions": p["impressions"], "age": p.get("age")}
                      for p in d["posts"]]}


def _miss(post, reason):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "ops" / "maya_measure_due.py"), "miss", post, reason], creationflags=NOFLAGS)


def main(argv=None, now=None, reader=run_read, miss=None, ledger=None, state_path=None, snaps_path=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args(argv)
    now = now or datetime.now(L.KST)
    posts = json.loads(Path(ledger or LEDGER).read_text(encoding="utf-8"))["posts"]
    if a.plan:
        for post, target, at, cov in L.read_schedule(posts):
            print(f"{post} 12h={target:%m-%d %H:%M} 읽기={at:%m-%d %H:%M}{' (정기 읽기가 갈음)' if cov else ''}")
        return 0
    st, sn = Path(state_path or STATE), Path(snaps_path or SNAPS)
    st.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(st.read_text(encoding="utf-8")) if st.exists() else {}
    post, why = L.decide(now, posts, state)
    if not post:
        print("skip:", why)
        return 0
    ok, blocked, out = reader()
    paused = L.record_result(state, now, post, ok, blocked)
    if ok and LATEST.exists():
        L.append_snapshots(sn, L.snapshot_lines(_latest_as_read(), "12h-read"))
    if paused:
        for pp, target, _, _ in L.read_schedule(posts):
            if pp not in state.get("done", []) and target <= now:
                (miss or _miss)(pp, "연속 2일 읽기 실패로 3일 쉼, 12시간 값을 못 쟀음")
    st.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("ok" if ok else f"fail blocked={blocked} paused={paused}", post, out[-120:].replace("\n", " "))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
