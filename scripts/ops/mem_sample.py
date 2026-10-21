#!/usr/bin/env python3
r"""신PC 메모리 표본 수집(탐 2026-10-21, 사장님 지시: 신PC 메모리 악화·갑작스런 재부팅의 원인을 숫자로 찾는다).
5분마다 1줄을 C:\work\_ops\mem_sample\YYYY-MM-DD.jsonl에 붙인다. 판정 없음, 측정만. 14일 지난 파일은 지운다.
기록: 전체·여유 램, 커밋(가상 메모리) 사용률, 이름별 상위 12개(개수·MB), 크롬 최상위 프로세스(프로필·디버그 포트·나이),
700MB 넘는 프로세스(이름·PID·명령줄 앞부분). 명령줄에는 비밀이 있을 수 있어 앞 120자만 남기고 --key/--token 같은 값은 가린다.
작업 스케줄러 simplifier-mem-sample(pythonw, 창 없음)이 5분마다 실행한다."""
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT_DIR = Path(r"C:\work\_ops\mem_sample")
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
KEEP_DAYS = 14
BIG_MB = 700
MASK = re.compile(r"(?i)(--?(?:key|token|secret|password|passwd|api[-_]?key)[=\s]+)\S+")

PS = r"""
$ErrorActionPreference='SilentlyContinue'
$os=Get-CimInstance Win32_OperatingSystem
$procs=Get-Process | ForEach-Object { [pscustomobject]@{n=$_.ProcessName;id=$_.Id;ws=[math]::Round($_.WorkingSet64/1MB);pm=[math]::Round($_.PrivateMemorySize64/1MB)} }
$chrome=Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -notmatch '--type=' } | ForEach-Object {
  $p=Get-Process -Id $_.ProcessId
  [pscustomobject]@{id=$_.ProcessId;age_h=[math]::Round(((Get-Date)-$p.StartTime).TotalHours,1);cmd=$_.CommandLine}
}
$big=@(); foreach($x in ($procs | Where-Object { $_.ws -ge %d })){ $c=(Get-CimInstance Win32_Process -Filter ("ProcessId="+$x.id)).CommandLine; $big += [pscustomobject]@{n=$x.n;id=$x.id;ws=$x.ws;cmd=$c} }
[pscustomobject]@{total_kb=$os.TotalVisibleMemorySize;free_kb=$os.FreePhysicalMemory;vtotal_kb=$os.TotalVirtualMemorySize;vfree_kb=$os.FreeVirtualMemory;procs=$procs;chrome=@($chrome);big=@($big)} | ConvertTo-Json -Depth 4 -Compress
""" % BIG_MB


def collect():
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, creationflags=NW)
    return json.loads(r.stdout)


def clip(cmd, n=120):
    return MASK.sub(r"\1***", cmd or "")[:n]


def chrome_roots(rows):
    out = []
    for c in rows:
        cmd = c.get("cmd") or ""
        prof = re.search(r'--user-data-dir="?([^" ]+)', cmd)
        port = re.search(r"remote-debugging-port=(\d+)", cmd)
        out.append({"pid": c["id"], "age_h": c["age_h"], "profile": prof.group(1) if prof else "default",
                    "port": port.group(1) if port else ""})
    return out


def factory_tabs(ports=(9333, 9334)):
    """공장 전용 크롬(디버그 포트)의 탭 수와 주소 호스트별 개수. 응답이 없으면 -1. 탭 제목·주소 경로는 남기지 않는다."""
    out = {}
    for port in ports:
        try:
            raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5).read()
            pages = [t for t in json.loads(raw) if t.get("type") == "page"]
            hosts = {}
            for t in pages:
                h = urllib.parse.urlparse(t.get("url", "")).netloc or "(빈 탭)"
                hosts[h] = hosts.get(h, 0) + 1
            out[str(port)] = {"tabs": len(pages), "hosts": hosts}
        except Exception:
            out[str(port)] = {"tabs": -1}
    return out


def main():
    d = collect()
    groups = {}
    for p in d["procs"]:
        g = groups.setdefault(p["n"], [0, 0])
        g[0] += 1
        g[1] += p["ws"]
    top = sorted(([k, v[0], v[1]] for k, v in groups.items()), key=lambda x: -x[2])[:12]
    total, free = d["total_kb"], d["free_kb"]
    vt, vf = d["vtotal_kb"], d["vfree_kb"]
    row = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ram_total_gb": round(total / 1048576, 1), "ram_free_gb": round(free / 1048576, 1),
        "ram_used_pct": round(100 * (1 - free / total)),
        "commit_used_pct": round(100 * (1 - vf / vt)) if vt else None,
        "top": top,
        "chrome_roots": chrome_roots(d.get("chrome") or []),
        "factory_tabs": factory_tabs(),
        "big": [{"n": b["n"], "pid": b["id"], "mb": b["ws"], "cmd": clip(b.get("cmd"))} for b in (d.get("big") or [])],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / (time.strftime("%Y-%m-%d") + ".jsonl")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUT_DIR / "latest.txt").write_text(row["time"], encoding="utf-8")  # 감시 대장(jobs.toml)이 보는 갱신 표시
    cutoff = time.time() - KEEP_DAYS * 86400
    for old in OUT_DIR.glob("*.jsonl"):
        if old.stat().st_mtime < cutoff:
            old.unlink()


if __name__ == "__main__":
    main()
