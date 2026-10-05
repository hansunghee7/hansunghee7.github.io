#!/usr/bin/env python3
r"""GPU 공용 관문 (N92, 탐 2026-10-01). 4090 한 장을 핏·탐·마야가 나눠 쓰기 위한 "쓰기 전 확인".

사용:
  python scripts/ops/gpu_gate.py need <GB> --who 탐 [--note 설명] [--now] [--ttl 분]
      통과하면 exit 0과 예약 1건을 남긴다. 모자라거나 큰 작업이 낮이면 exit 3과 이유를 출력한다.
  python scripts/ops/gpu_gate.py release --who 탐      내 예약을 지운다(안 지워도 ttl 뒤 자동 만료).
  python scripts/ops/gpu_gate.py status                현재 남은 VRAM과 예약 목록.

규칙(근거: 2026-09-30~10-01 측정 1,450건, VRAM 5GB 초과는 6%뿐이고 24GB까지 찬 겹침이 2번):
  - 5GB 미만 작은 작업은 확인만 하고 통과한다(예약도 안 한다).
  - 20GB 이상 큰 작업은 새벽 01~06시에만 통과한다. 급하면 --now(사유가 기록에 남는다).
  - 남은 VRAM은 nvidia-smi 값에서 다른 사람의 살아 있는 예약을 뺀 값이다(예약 직후 로딩 전의 겹침을 막는다).
  - 새벽(01~06시)에 예약으로 설명되지 않는 점유 때문에 모자라면 ComfyUI 모델을 내리고 한 번 더 본다
    (사장님 2026-10-02: 사장님이 에이전트 없을 때 연습으로 띄운 것은 새벽 정기 작업이 내려도 된다). 결과 reclaim-night.
기록: C:\work\_ops\gpu_gate_log.csv (시각, 누가, 요청 GB, 남은 GB, 결과, 메모). 프로세스별 VRAM은 윈도우가 안 줘서
이 기록이 "누가 언제 얼마" 정본이다.
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

OPS = Path(r"C:\work\_ops")
LOG = OPS / "gpu_gate_log.csv"
RES = OPS / "gpu_reservations.json"
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SMALL_GB = 5       # 이 미만은 예약 없이 통과
BIG_GB = 20        # 이 이상은 새벽에만
NIGHT = (1, 6)     # 01:00 ~ 05:59
MARGIN_MIB = 1024  # 윈도우·브라우저가 쓰는 여유


def free_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=20, creationflags=NW).stdout.strip().splitlines()[0]
    total, used = [int(x) for x in out.split(",")]
    return total - used, total


def load_res(now):
    try:
        data = json.loads(RES.read_text(encoding="utf-8"))
    except Exception:
        data = []
    return [r for r in data if r.get("expires", 0) > now]


def save_res(data):
    OPS.mkdir(parents=True, exist_ok=True)
    RES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def log(who, gb, free_gb, result, note):
    OPS.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "who", "need_gb", "free_gb", "result", "note"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), who, gb, round(free_gb, 1), result, note])

    _log_db(who, gb, free_gb, result, note)


def _log_db(who, gb, free_gb, result, note):
    """자원이용부(N156, 2026-10-05 사장님 지시 "공용자원은 DB에 기록하고 쓰게"): 같은 기록을 운영 상태 DB의 gpu_gate_log에도 남긴다.
    실패하거나 느려도 관문은 절대 멈추지 않는다(3초 안에 못 끝나면 포기, CSV가 정본이고 DB는 import_ops_tables.py가 빠진 줄을 채운다)."""
    import threading

    def work():
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import opsdb
            from datetime import datetime, timezone, timedelta
            at = datetime.now(timezone(timedelta(hours=9))).isoformat()
            opsdb.insert("gpu_gate_log", [{"logged_at": at, "who": who, "need_gb": gb, "free_gb": round(free_gb, 1), "result": result, "note": note, "source": "gpu_gate.py"}])
        except BaseException:
            pass
    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(3)


COMFY_FREE = "http://127.0.0.1:8188/free"


def reclaim_unreserved():
    """예약 없는 점유(사장님 연습용 ComfyUI 등)의 모델을 내린다. 프로세스는 끄지 않고 ComfyUI 공식 /free만 부른다."""
    import urllib.request
    try:
        req = urllib.request.Request(COMFY_FREE, data=b'{"unload_models": true, "free_memory": true}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10).read()
        time.sleep(5)
        return "comfy-free"
    except Exception as e:
        return f"comfy-free 실패({type(e).__name__})"


def need(gb, who, note="", now_flag=False, ttl_min=30):
    """통과하면 (True, 메시지), 아니면 (False, 이유). 다른 스크립트가 import해서 쓴다."""
    now = time.time()
    free, total = free_mib()
    mine_removed = [r for r in load_res(now) if r["who"] != who]
    others = sum(r["gb"] for r in mine_removed)
    avail_gb = (free - MARGIN_MIB) / 1024 - others
    hour = time.localtime(now).tm_hour
    if gb < SMALL_GB:
        log(who, gb, avail_gb, "ok-small", note)
        return True, f"통과(작은 작업 {gb}GB, 남은 {avail_gb:.1f}GB)"
    if gb >= BIG_GB and not (NIGHT[0] <= hour < NIGHT[1]) and not now_flag:
        log(who, gb, avail_gb, "deny-daytime", note)
        return False, (f"큰 작업({gb}GB)은 새벽 {NIGHT[0]:02d}~{NIGHT[1]:02d}시에만 돌립니다. "
                       "지금 꼭 필요하면 --now를 붙이세요(기록에 남습니다).")
    if avail_gb < gb and NIGHT[0] <= hour < NIGHT[1] and others < gb:
        # 예약으로 설명되지 않는 점유가 있다: 새벽이면 사장님 연습용 점유를 내리고 한 번 더 본다.
        how = reclaim_unreserved()
        free, total = free_mib()
        avail_gb = (free - MARGIN_MIB) / 1024 - others
        log(who, gb, avail_gb, "reclaim-night", f"{how}; {note}")
    if avail_gb < gb:
        holders = ", ".join(f"{r['who']} {r['gb']}GB" for r in mine_removed) or "예약 없음"
        log(who, gb, avail_gb, "deny-full", note)
        return False, f"남은 VRAM {avail_gb:.1f}GB로 {gb}GB가 모자랍니다(다른 예약: {holders}). 끝날 때까지 기다리거나 핏에게 알리세요."
    mine_removed.append({"who": who, "gb": gb, "note": note, "expires": now + ttl_min * 60})
    save_res(mine_removed)
    log(who, gb, avail_gb, "ok-now" if now_flag else "ok", note)
    return True, f"통과({gb}GB 예약, {ttl_min}분 뒤 자동 만료, 남은 {avail_gb:.1f}GB)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("need")
    n.add_argument("gb", type=float)
    n.add_argument("--who", required=True)
    n.add_argument("--note", default="")
    n.add_argument("--now", action="store_true")
    n.add_argument("--ttl", type=int, default=30)
    r = sub.add_parser("release")
    r.add_argument("--who", required=True)
    sub.add_parser("status")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "need":
        ok, msg = need(a.gb, a.who, a.note, a.now, a.ttl)
        print(msg)
        sys.exit(0 if ok else 3)
    if a.cmd == "release":
        data = load_res(time.time())
        save_res([x for x in data if x["who"] != a.who])
        log(a.who, 0, 0, "release", "")
        print("예약 해제")
        return
    now = time.time()
    free, total = free_mib()
    print(f"VRAM 전체 {total/1024:.1f}GB, 남은 {free/1024:.1f}GB")
    for x in load_res(now):
        print(f"예약: {x['who']} {x['gb']}GB (남은 {int((x['expires']-now)/60)}분) {x.get('note','')}")


if __name__ == "__main__":
    main()
