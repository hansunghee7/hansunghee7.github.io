#!/usr/bin/env python3
"""scripts/ops/jobs*.toml(감시 대장)이 파싱되는지 검사한다.

왜 이 검사가 있나
-----------------
2026-10-06 PR 1943에서 jobs.toml 한 줄에 제어 문자(세로탭 0x0b)가 들어가
파일 전체가 TOML 파싱에 실패했고 감시 대장 38건이 멈췄는데 CI가 못 잡았다.

무엇을 잡나
-----------
1. 줄바꿈(\\r \\n)과 탭 외의 제어 문자(0x00~0x1f): 파일명·줄 번호를 출력한다.
2. tomllib 파싱 오류.
3. [[job]]에 id·kind·name이 없는 경우.

사용법: python3 scripts/check_jobs_toml.py [파일...]  (인자 없으면 scripts/ops/jobs*.toml 전부)
"""
import re
import sys
import tomllib
from pathlib import Path

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
REQUIRED = ("id", "kind", "name")


def check(path: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    for no, line in enumerate(text.split("\n"), 1):
        for m in CTRL.finditer(line):
            errors.append(f"{path}:{no}: 제어 문자 0x{ord(m.group()):02x} (열 {m.start() + 1})")
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        errors.append(f"{path}: TOML 파싱 실패: {e}")
        return 0, errors
    jobs = data.get("job", [])
    for i, job in enumerate(jobs, 1):
        missing = [k for k in REQUIRED if not job.get(k)]
        if missing:
            errors.append(f"{path}: [[job]] #{i}({job.get('id', '?')}): 필수 키 없음 {', '.join(missing)}")
    return len(jobs), errors


def main() -> int:
    if len(sys.argv) > 1:
        files = [Path(a) for a in sys.argv[1:]]
    else:
        files = sorted((Path(__file__).parent / "ops").glob("jobs*.toml"))
    if not files:
        print("jobs*.toml 파일을 찾지 못했다")
        return 1
    failed = False
    for f in files:
        count, errors = check(f)
        if errors:
            failed = True
            print("\n".join(errors))
        else:
            print(f"OK {f}: 작업 {count}개")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
