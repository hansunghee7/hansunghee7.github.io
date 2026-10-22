# -*- coding: utf-8 -*-
"""사장님 화면에 뜨는 창(콘솔 깜빡임)을 잡는 감시기(핏 2026-10-22). 사용: python console_flash_watch.py <초> <결과.json>
새로 보이는 최상위 창의 시각·클래스·소유 프로그램·제목을 기록한다. 절차: docs/콘솔창_범인색출_절차.md"""
import ctypes, ctypes.wintypes as w, time, sys, json, subprocess
u = ctypes.windll.user32
k = ctypes.windll.kernel32
dur = float(sys.argv[1]); out = sys.argv[2]
seen = {}
buf = ctypes.create_unicode_buffer(256)
CB = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
def exe(pid):
    h = k.OpenProcess(0x1000, False, pid)
    if not h: return "?"
    n = w.DWORD(520); b = ctypes.create_unicode_buffer(520)
    k.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(n)); k.CloseHandle(h)
    return b.value.split("\\")[-1]
def cb(hwnd, _):
    if not u.IsWindowVisible(hwnd): return True
    u.GetClassNameW(hwnd, buf, 256); c = buf.value
    if True:
        pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        key = (hwnd, pid.value)
        if key not in seen:
            u.GetWindowTextW(hwnd, buf, 256)
            seen[key] = {"t": time.strftime("%H:%M:%S"), "class": c, "pid": pid.value, "owner": exe(pid.value), "title": buf.value[:80]}
    return True
f = CB(cb); end = time.time() + dur
while time.time() < end:
    u.EnumWindows(f, 0); time.sleep(0.02)
json.dump(list(seen.values()), open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
