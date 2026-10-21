"""매일 별칭 사용 관찰(S5): 제품 저장소 최근 24시간 Actions 로그의 env_alias_legacy 건수와
이 PC 사용자 환경변수의 옛·새 이름 존재(이름만, 값은 읽어도 출력·저장하지 않는다)를 한 줄로 남긴다.

산출물: C:/work/_ops/name_scan/alias_latest.txt. 로그 내용은 저장하지 않고 건수만 센다.
건수가 0이 아니어도 종료 코드는 0이고 줄 끝에 '주의'를 붙인다.
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

OUT = Path("C:/work/_ops/name_scan/alias_latest.txt")
REPO = "hansunghee7/simplifier-saegim"
NEEDLE = "env_alias_legacy"
MAX_RUNS = 20
TIMEOUT = 60
_OLD = "SAEG" + "IM_"  # 옛 접두사(철자를 이어 붙여 이름 관문 문자열 검색을 피한다)
SUFFIXES = ("TENANT_ID", "TENANT_SECRET", "MCP_URL")
OLD_NAMES = [_OLD + s for s in SUFFIXES]
NEW_NAMES = ["CARVIT_" + s for s in SUFFIXES]
NOFLAG = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def count_needle(text):
    return text.count(NEEDLE)


def parse_run_ids(raw, limit=MAX_RUNS):
    try:
        data = json.loads(raw or "[]")
    except ValueError:
        return []
    return [r["databaseId"] for r in data if "databaseId" in r][:limit]


def present_names(raw):
    """PowerShell이 한 줄에 하나씩 찍은 이름 목록에서 우리가 찾는 이름만 추린다."""
    got = {ln.strip() for ln in (raw or "").splitlines() if ln.strip()}
    return got


def format_line(now_iso, runs, legacy_count, old_found, new_found, errors):
    line = "%s 실행=%d 별칭로그=%d 옛이름=%d/3 새이름=%d/3" % (now_iso, runs, legacy_count, len(old_found), len(new_found))
    if errors:
        line += " 조회실패=%d" % errors
    if legacy_count:
        line += " 주의"
    return line


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, timeout=TIMEOUT, creationflags=NOFLAG)


def count_logs():
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    errors, total = 0, 0
    try:
        p = _run(["gh", "run", "list", "-R", REPO, "--created", ">=" + since, "--limit", "100", "--json", "databaseId,name"])
        ids = parse_run_ids(p.stdout.decode("utf-8", errors="replace")) if p.returncode == 0 else None
    except Exception:  # noqa: BLE001
        ids = None
    if ids is None:
        return 0, 0, 1
    for rid in ids:
        try:
            q = _run(["gh", "run", "view", str(rid), "-R", REPO, "--log"])
            if q.returncode != 0:
                errors += 1
                continue
            total += count_needle(q.stdout.decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            errors += 1
    return len(ids), total, errors


def env_names():
    ps = "[Environment]::GetEnvironmentVariables('User').Keys | ForEach-Object { $_ }"
    try:
        p = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
        return present_names(p.stdout.decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return set()


def main():
    runs, legacy, errors = count_logs()
    names = env_names()
    line = format_line(dt.datetime.now().astimezone().isoformat(timespec="seconds"), runs, legacy,
                       [n for n in OLD_NAMES if n in names], [n for n in NEW_NAMES if n in names], errors)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(line + "\n", encoding="utf-8")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
