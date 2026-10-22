# -*- coding: utf-8 -*-
"""콘솔 창 깜빡임 상시 기록기(핏 2026-10-22). 사장님이 창을 신고할 때 타이핑이 안 되므로 PC가 스스로 기록한다.
동작: 0.05초마다 새로 보이는 콘솔 창을 보고, 창이 뜨면 직전 3초에 새로 생긴 프로세스(부모→자식 이름)를 함께 기록한다.
기록: C:/work/_ops/flash_log.jsonl (한 줄 = 창 1개 또는 폭주 요약). 3일 지난 줄은 시작할 때 지운다.
읽기: python scripts/ops/console_flash_logger.py --report [분]   (최근 N분 창 개수·범인 후보를 한 화면으로)
실행: pythonw scripts/ops/console_flash_logger.py   (예약 작업 '핏_창기록', 로그온 때 시작, 창 없음)
절차 문서: docs/콘솔창_범인색출_절차.md
"""
import ctypes
import ctypes.wintypes as w
import json
import os
import sys
import time
from collections import Counter, deque

LOG = r"C:\work\_ops\flash_log.jsonl"
KEEP_SEC = 3 * 86400
CONSOLE_CLASSES = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow")


def report(minutes):
    now = time.time()
    rows = []
    if os.path.exists(LOG):
        for ln in open(LOG, encoding="utf-8"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if now - d.get("ts", 0) <= minutes * 60:
                rows.append(d)
    print(f"최근 {minutes}분 콘솔 창 {len(rows)}개")
    if not rows:
        return
    c = Counter((x.get("culprit") or "?") for x in rows)
    print("범인 후보(부모→자식, 개수):")
    for k, v in c.most_common(8):
        print(f"  {v:3d}  {k}")
    print("시각 분포(초 단위 상위):", Counter(x["t"] for x in rows).most_common(5))


if len(sys.argv) > 1 and sys.argv[1] == "--report":
    report(float(sys.argv[2]) if len(sys.argv) > 2 else 5)
    sys.exit(0)

u = ctypes.windll.user32
k = ctypes.windll.kernel32
k.CreateToolhelp32Snapshot.restype = w.HANDLE
TH32CS_SNAPPROCESS = 0x2


class PE(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG),
                ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


def snapshot():
    h = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = {}
    pe = PE()
    pe.dwSize = ctypes.sizeof(PE)
    ok = k.Process32FirstW(h, ctypes.byref(pe))
    while ok:
        out[pe.th32ProcessID] = (pe.th32ParentProcessID, pe.szExeFile.lower())
        ok = k.Process32NextW(h, ctypes.byref(pe))
    k.CloseHandle(h)
    return out


def trim():
    if not os.path.exists(LOG):
        return
    cut = time.time() - KEEP_SEC
    keep = []
    for ln in open(LOG, encoding="utf-8"):
        try:
            if json.loads(ln).get("ts", 0) >= cut:
                keep.append(ln)
        except Exception:
            pass
    open(LOG, "w", encoding="utf-8").writelines(keep)


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    trim()
    buf = create_buf = ctypes.create_unicode_buffer(256)
    CB = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    seen_win = set()
    recent = deque()  # (ts, pid, ppid, exe, parent_exe)
    known = snapshot()
    names = {pid: v[1] for pid, v in known.items()}  # 끝난 부모의 이름도 알기 위해 pid→exe를 기억
    last_proc = 0.0
    last_alive = 0.0
    start = time.time()

    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        u.GetClassNameW(hwnd, buf, 256)
        if buf.value not in CONSOLE_CLASSES:
            return True
        pid = w.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        key = (hwnd, pid.value)
        if key in seen_win:
            return True
        seen_win.add(key)
        if time.time() - start < 3:  # 시작 시점에 이미 떠 있던 창은 기록 안 함
            return True
        now = time.time()
        kids = [r for r in recent if now - r[0] <= 3.0 and r[3] not in ("conhost.exe", "openconsole.exe")]
        culprit = None
        if kids:
            # 부모가 pythonw·서비스 등이고 자식이 콘솔 프로그램인 쌍을 우선
            pri = [r for r in kids if r[3] in ("ffprobe.exe", "ffmpeg.exe", "git.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "python.exe", "bash.exe", "node.exe", "gcloud.cmd", "curl.exe")]
            pick = (pri or kids)[-1]
            culprit = f"{pick[4] or '?'} → {pick[3]}"
        ev = {"ts": now, "t": time.strftime("%H:%M:%S", time.localtime(now)), "class": buf.value, "win_pid": pid.value,
              "culprit": culprit, "recent": [f"{r[4] or '?'}→{r[3]}" for r in kids[-6:]]}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return True

    f = CB(cb)
    while True:
        u.EnumWindows(f, 0)
        t = time.time()
        if t - last_proc >= 0.2:
            last_proc = t
            cur = snapshot()
            for pid, (pp, exe) in cur.items():
                if pid not in known:
                    recent.append((t, pid, pp, exe, names.get(pp) or (cur.get(pp) or (0, ""))[1]))
                names[pid] = exe
            known = cur
            if len(names) > 20000:
                names.clear()
            while recent and t - recent[0][0] > 6:
                recent.popleft()
            if len(seen_win) > 5000:
                seen_win.clear()
        if t - last_alive >= 30:
            last_alive = t
            with open(ALIVE, "w") as fa:
                fa.write(time.strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(0.05)


if __name__ == "__main__":
    main()
