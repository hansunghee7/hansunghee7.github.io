# -*- coding: utf-8 -*-
"""슈퍼얼라인 공통 점검기(핏 2026-10-11 신설, 사장님 명명). 에이전트별 설정 파일(docs/align/<이름>.toml)의 점검 목록을 읽어 PASS/FAIL 을 낸다.
목적: 사장님과 합의한 목표(KPI)가 세션이 바뀌어도 읽히고, 도구 관문으로 강제되고, 자동 작업이 돌고, 문서가 서로 어긋나지 않는지 주 1회 자동 확인.
사용: python scripts/ops/align_check.py <이름>  [--out 결과.md]     설정 형식과 정본: docs/슈퍼얼라인.md
점검 종류(type): file_contains(path, text) / file_age(path, max_hours) / schtask(task) / jobs_id(id) / cmd_ok(cmd 리스트, 종료코드 0) / cmd_fails(cmd, 종료코드 0이 아님)
"""
import subprocess, sys, time, tomllib
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parents[2]
JOBS = ROOT / "scripts" / "ops" / "jobs.toml"


def txt(p):
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""


def run_check(c):
    t = c["type"]
    if t == "file_contains":
        return c["text"] in txt(c["path"]), c["path"]
    if t == "file_age":
        try:
            h = (time.time() - Path(c["path"]).stat().st_mtime) / 3600
        except Exception:
            return False, "파일 없음"
        return h < c["max_hours"], f"{h:.0f}시간 전"
    if t == "schtask":
        r = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-ScheduledTask -TaskName '{c['task']}' -ErrorAction SilentlyContinue).State"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        s = r.stdout.strip()
        return s in ("Ready", "Running"), s or "없음"
    if t == "jobs_id":
        return c["id"] in txt(JOBS), "jobs.toml"
    if t in ("cmd_ok", "cmd_fails"):
        r = subprocess.run(c["cmd"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return (r.returncode == 0) == (t == "cmd_ok"), f"rc={r.returncode}"
    return False, f"알 수 없는 type {t}"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    who = sys.argv[1]
    cfg = tomllib.loads(txt(ROOT / "docs" / "align" / f"{who}.toml"))
    goal = cfg.get("goal", "")
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    res = []
    for c in cfg.get("check", []):
        try:
            ok, d = run_check(c)
        except Exception as e:  # 점검 자체가 깨져도 FAIL 로 보이게
            ok, d = False, f"점검 오류 {e}"
        res.append((c.get("name", c["type"]), ok, d))
    bad = [r for r in res if not r[1]]
    L = [f"# 슈퍼얼라인 점검: {who} ({datetime.now():%Y-%m-%d %H:%M} 자동 생성, scripts/ops/align_check.py)", "",
         f"- 목표: {goal}", f"- 결과: 통과 {len(res) - len(bad)} / 전체 {len(res)}, FAIL {len(bad)}", ""]
    L += [f"- {'PASS' if ok else '**FAIL**'} {n} ({d})" for n, ok, d in res]
    s = "\n".join(L) + "\n"
    if out_path:
        out_path.write_text(s, encoding="utf-8")
    print(s)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
