# -*- coding: utf-8 -*-
"""구PC 상주 크롬 정기 재기동(핏, 2026-10-19, 사장님 승인: 타미가 아니라 조건을 코드로 거는 스크립트).
배경: 상주 크롬이 5~25일째 메모리를 쥐어 가용 1.7GB, 실행기 훅의 메모리 게이트가 reseed를 취소한다(탐 10/19, 공정 카드 핏-영상생성 #92).
한 번 실행에 한 포트만, 모든 조건이 맞을 때만 그 계정 크롬을 껐다 켠다. 프로필 폴더가 로그인을 쥐고 있으므로 다시 켜도 로그인은 유지된다.
조건(전부 만족):
  1) 기동 14일 초과 또는 프로필 전체 메모리 2GB 초과
  2) 그 포트의 작업기 잠금(logs/worker-<포트>.lock)을 비차단으로 잡을 수 있다 = 작업기가 안 돌고 있다. 잡은 채로 재기동해서 그 사이 작업기가 시작되지 못하게 한다
  3) account_worker·flow_batch·cut_runner 프로세스가 그 포트를 쓰고 있지 않다
  4) 그 계정 갱신 시각(KST) 앞 30분~뒤 40분 창이 아니다(갱신 직후 이벤트 기동 idle_guard +10분 보호)
기본은 모의 실행(--apply 가 있어야 실제 재기동). 기록 logs/chrome_recycle.log.
사용: python3 chrome_recycle.py [--port 9224] [--apply] [--max-days 14] [--max-mb 2048]"""
import argparse, fcntl, os, signal, subprocess, sys, time, urllib.request
from pathlib import Path

W = Path.home() / "workshop"
# 작업기가 있는 포트와 갱신 시각(KST). 크론의 --refresh 값과 같다. SNS용 9227·9228, 9222는 대상 아님.
REFRESH = {9223: None, 9224: "10:11", 9225: "22:50", 9226: None, 9229: "23:03", 9230: "02:19", 9231: "01:53"}
PROFILE = {9223: "acct3", 9224: "acct4", 9225: "acct5", 9226: "acct2", 9229: "acct6", 9230: "port-9230", 9231: "port-9231"}


def say(msg):
    line = time.strftime("%F %T UTC ") + msg
    print(line, flush=True)
    with open(W / "logs" / "chrome_recycle.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def kst_min():
    t = time.gmtime(time.time() + 9 * 3600)
    return t.tm_hour * 60 + t.tm_min


def near_refresh(refresh, before=30, after=40):
    if not refresh:
        return False
    h, m = map(int, refresh.split(":"))
    d = (kst_min() - (h * 60 + m) + 12 * 60) % (24 * 60) - 12 * 60  # -720..719, 갱신 기준 상대 분
    return -before <= d <= after


def profile_procs(prof):
    """(pid, ppid, etimes, rss_kb) 목록: 그 프로필 폴더를 쓰는 크롬 프로세스 전부(자식 포함)."""
    out = subprocess.run(["ps", "-eo", "pid=,ppid=,etimes=,rss=,args="], capture_output=True, text=True).stdout
    key = f"user-data-dir={W}/profiles/{prof}"
    rows = []
    for ln in out.splitlines():
        p = ln.split(None, 4)
        if len(p) < 5 or "chrom" not in p[4]:
            continue
        if key + " " in p[4] + " " or key + "/" in p[4]:
            rows.append((int(p[0]), int(p[1]), int(p[2]), int(p[3])))
    return rows


def stat(port):
    rows = profile_procs(PROFILE[port])
    if not rows:
        return None
    # 가장 오래된 프로세스를 크롬 기동 시각으로 본다. 메모리는 합계(공유 페이지 중복 포함이라 과대 가능).
    return {"days": max(r[2] for r in rows) / 86400, "mb": sum(r[3] for r in rows) / 1024, "n": len(rows)}


def busy(port):
    out = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if str(port) in ln and any(k in ln for k in ("account_worker", "flow_batch", "cut_runner")) and "chrome_recycle" not in ln:
            return ln.strip()[:120]
    return None


def alive(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3).read()
        return True
    except Exception:
        return False


def free_display():
    # xvfb-run -a 가 옛 Xvfb 찌꺼기와 부딪혀 "Authorization required"로 크롬이 못 뜨는 일이 있어(10/19 9230 시험) 빈 번호를 직접 고른다.
    n = 120
    while Path(f"/tmp/.X{n}-lock").exists() or Path(f"/tmp/.X11-unix/X{n}").exists():
        n += 1
    return n


def launch(port):
    prof = PROFILE[port]
    d = W / "profiles" / prof
    for f in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try: (d / f).unlink()
        except OSError: pass
    log = open(W / "logs" / f"chrome-{prof}.log", "w")
    subprocess.Popen(
        ["xvfb-run", "-n", str(free_display()), "-s", "-screen 0 1366x900x24", "google-chrome",
         f"--user-data-dir={d}", f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1",
         "--no-first-run", "--no-default-browser-check", "--lang=ko", "https://labs.google/fx/tools/flow"],
        stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true", help="그 포트 크롬이 죽어 있으면 같은 프로필로 다시 켠다(작업기 잠금을 잡을 수 있을 때만)")
    ap.add_argument("--max-days", type=float, default=14)
    ap.add_argument("--max-mb", type=float, default=2048)
    a = ap.parse_args()
    ports = [a.port] if a.port else list(REFRESH)
    cands = []
    for p in ports:
        if p not in REFRESH:
            say(f"{p}: 대상 아님"); continue
        s = stat(p)
        if not s:
            if a.restore and a.apply and not alive(p):
                lk = open(W / "logs" / f"worker-{p}.lock", "w")
                try:
                    fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    say(f"{p}: 복구 건너뜀, 작업기 잠금 사용 중"); continue
                launch(p)
                for _ in range(30):
                    if alive(p): break
                    time.sleep(2)
                say(f"{p}: 크롬 없음 -> 복구 " + ("성공" if alive(p) else "실패"))
                lk.close()
            else:
                say(f"{p}: 크롬 없음(start_chromes.sh 담당)")
            continue
        why = []
        if s["days"] > a.max_days: why.append(f"{s['days']:.1f}일")
        if s["mb"] > a.max_mb: why.append(f"{s['mb']:.0f}MB")
        say(f"{p}: {s['days']:.1f}일 {s['mb']:.0f}MB 프로세스 {s['n']}개 -> " + ("대상(" + ",".join(why) + ")" if why else "기준 미달"))
        if why:
            cands.append((s["mb"], p, s))
    cands.sort(reverse=True)
    for mb, p, s in cands:
        lock = open(W / "logs" / f"worker-{p}.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            say(f"{p}: 건너뜀, 작업기 잠금 사용 중"); lock.close(); continue
        b = busy(p)
        if b:
            say(f"{p}: 건너뜀, 작업 프로세스 있음 {b}"); lock.close(); continue
        if near_refresh(REFRESH[p]):
            say(f"{p}: 건너뜀, 갱신 {REFRESH[p]}(KST) 앞뒤 보호 창"); lock.close(); continue
        if not a.apply:
            say(f"{p}: [모의] 모든 조건 통과, --apply 가 있으면 재기동"); lock.close(); return 0
        rows = profile_procs(PROFILE[p])
        pids = [r[0] for r in rows]
        # 같은 부모(크론 셸) 밑의 Xvfb(화면 서버)도 같이 끈다. 안 끄면 찌꺼기로 쌓여 다음 기동을 방해한다.
        ppids = {r[1] for r in rows}
        for ln in subprocess.run(["ps", "-eo", "pid=,ppid=,args="], capture_output=True, text=True).stdout.splitlines():
            q = ln.split(None, 2)
            if len(q) == 3 and q[2].startswith("Xvfb") and int(q[1]) in ppids:
                pids.append(int(q[0]))
        for pid in pids:
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
        for _ in range(15):
            time.sleep(1)
            if not profile_procs(PROFILE[p]): break
        for r in profile_procs(PROFILE[p]):
            try: os.kill(r[0], signal.SIGKILL)
            except ProcessLookupError: pass
        time.sleep(2)
        launch(p)
        ok = False
        for _ in range(30):
            if alive(p): ok = True; break
            time.sleep(2)
        s2 = stat(p)
        say(f"{p}: 재기동 {'성공' if ok else '실패(5분 뒤 start_chromes.sh 가 다시 시도)'} 전 {mb:.0f}MB -> 후 " + (f"{s2['mb']:.0f}MB" if s2 else "없음"))
        lock.close()
        return 0 if ok else 1
    say("재기동할 포트 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
