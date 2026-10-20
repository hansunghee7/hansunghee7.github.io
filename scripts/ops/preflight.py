#!/usr/bin/env python3
"""작업 시작 전 연결 확인(읽기 전용). 값(키·토큰)은 절대 출력하지 않는다.

항목별 OK/경고/실패 한 줄 + 마지막 줄 'PREFLIGHT ok=N warn=N fail=N'.
실행 기록: C:/work/_ops/preflight_log.jsonl (시각, 개수, 경고·실패 항목 이름).
종료 코드: fail이 하나라도 있으면 1.
"""
import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

TIMEOUT = 8
PASS_CLI = "C:/work/saegim-pass-dev/host/pass.py"
SHARED_REPO = "C:/work/hansunghee7.github.io"
CXO_REPO = "C:/work/simplifier-cxo-db"
LOG_PATH = "C:/work/_ops/preflight_log.jsonl"
MIN_MEM_MB = 3072  # 구PC 실행기 관문 기준
OK, WARN, FAIL = "OK", "경고", "실패"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(cmd, timeout=TIMEOUT):
    """(returncode, stdout). 시간 초과·실행 불가는 (-1, 사유)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", creationflags=NOWIN)
        return p.returncode, (p.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "시간 초과"
    except Exception as e:  # noqa: BLE001
        return -1, type(e).__name__


def check_pass():
    rc, out = run([sys.executable, PASS_CLI, "ping"])
    if rc != 0:
        return FAIL, "카빗 패스 도우미 응답 없음"
    try:
        if not json.loads(out).get("ok"):
            return FAIL, "카빗 패스 ping ok=false"
    except ValueError:
        return FAIL, "카빗 패스 ping 응답 해석 불가"
    rc, out = run([sys.executable, PASS_CLI, "list"])
    try:
        d = json.loads(out)
    except ValueError:
        return FAIL, "카빗 패스 list 응답 해석 불가"
    if not d.get("ok"):
        return FAIL, "카빗 패스 list 거절(도우미 키 불일치 가능)"
    n = len(d.get("keys") or [])
    locked = bool(d.get("locked"))
    # 잠김은 일반 구역만 보이는 정상 상태라 경고가 아니다
    return OK, f"카빗 패스 응답, locked={str(locked).lower()}, 키 {n}개"


def check_oldpc():
    rc, out = run(["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={TIMEOUT - 2}", "goosolar",
                   "echo ok; grep MemAvailable /proc/meminfo; pgrep -x Runner.Listener | wc -l"])
    if rc != 0 or not out.startswith("ok"):
        return [(FAIL, f"구PC SSH 실패({out[:30] if rc == -1 else 'rc=' + str(rc)})")]
    res = [(OK, "구PC SSH 응답")]
    mb = None
    runners = 0
    for line in out.splitlines()[1:]:
        if line.startswith("MemAvailable"):
            try:
                mb = int(line.split()[1]) // 1024
            except (ValueError, IndexError):
                pass
        elif line.strip().isdigit():
            runners = int(line.strip())
    if mb is None:
        res.append((WARN, "구PC 여유 메모리 읽기 실패"))
    elif mb < MIN_MEM_MB:
        res.append((WARN, f"구PC 여유 메모리 {mb}MB (기준 {MIN_MEM_MB}MB 미만)"))
    else:
        res.append((OK, f"구PC 여유 메모리 {mb}MB"))
    res.append((OK, f"구PC 실행기 프로세스 {runners}개") if runners > 0
               else (FAIL, "구PC 실행기 프로세스 없음"))
    return res


def check_ollama():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=TIMEOUT) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return OK, f"신PC Ollama 응답, 모델 {len(d.get('models') or [])}개"
    except Exception as e:  # noqa: BLE001
        return WARN, f"신PC Ollama 응답 없음({type(e).__name__})"


def check_git():
    res = []
    rc, _ = run(["gh", "auth", "status"])
    res.append((OK, "gh 인증됨") if rc == 0 else (FAIL, "gh 인증 안 됨"))
    rc, br = run(["git", "-C", SHARED_REPO, "rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        res.append((FAIL, "공유 폴더 브랜치 확인 실패"))
        return res
    rc, behind = run(["git", "-C", SHARED_REPO, "rev-list", "--count", "HEAD..origin/main"])
    n = int(behind) if rc == 0 and behind.isdigit() else None
    msg = f"공유 폴더 브랜치 {br}, origin/main 대비 뒤처짐 " + ("확인 불가" if n is None else f"{n}커밋")
    if br != "main" or (n or 0) > 0:
        res.append((WARN, msg))
    else:
        res.append((OK if n is not None else WARN, msg))
    return res


def check_cxo():
    rc, br = run(["git", "-C", CXO_REPO, "rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        return FAIL, "cxo-db 폴더 브랜치 확인 실패"
    return (OK if br == "main" else WARN), f"cxo-db 브랜치 {br}"


def collect():
    jobs = {"카빗패스": check_pass, "구PC": check_oldpc, "Ollama": check_ollama,
            "git": check_git, "cxo-db": check_cxo}
    results = []  # (이름, 상태, 문구)
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(f) for k, f in jobs.items()}
        for k, fut in futs.items():
            try:
                r = fut.result(timeout=TIMEOUT * 3)
            except Exception as e:  # noqa: BLE001
                r = (FAIL, f"{k} 점검 오류({type(e).__name__})")
            for st, msg in (r if isinstance(r, list) else [r]):
                results.append((k, st, msg))
    return results


def write_log(results, path=LOG_PATH):
    rec = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"),
           "ok": sum(1 for _, s, _ in results if s == OK),
           "warn": sum(1 for _, s, _ in results if s == WARN),
           "fail": sum(1 for _, s, _ in results if s == FAIL),
           "warn_items": [m for _, s, m in results if s == WARN],
           "fail_items": [m for _, s, m in results if s == FAIL]}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def main():
    results = collect()
    for _, st, msg in results:
        print(f"[{st}] {msg}")
    rec = write_log(results)
    print(f"PREFLIGHT ok={rec['ok']} warn={rec['warn']} fail={rec['fail']}")
    return 1 if rec["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
