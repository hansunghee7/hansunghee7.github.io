#!/usr/bin/env python3
r"""GPU 사용 패턴 표본 수집 (N92, 탐 2026-09-30). 1분마다 1줄을 C:\work\_ops\gpu_usage.csv에 붙인다.
열: 시각, VRAM 사용 MiB, 사용률 %, 프로세스(이름:PID 목록). 판정 없음, 측정만.
작업 스케줄러 simplifier-gpu-sample(pythonw, 창 없음)이 1분마다 실행한다."""
import subprocess, time, csv, sys
from pathlib import Path

OUT = Path(r"C:\work\_ops\gpu_usage.csv")
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def q(*a):
    return subprocess.run(list(a), capture_output=True, text=True, timeout=20, creationflags=NW).stdout.strip()


def main():
    g = q("nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits")
    mem, util = [x.strip() for x in g.splitlines()[0].split(",")]
    procs = []
    for l in q("nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader").splitlines():
        pid = l.strip()
        if not pid.isdigit():
            continue
        name = q("powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName") or "?"
        procs.append(f"{name}:{pid}")
    new = not OUT.exists()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "vram_mib", "util_pct", "procs"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), mem, util, " ".join(procs)])


if __name__ == "__main__":
    main()
