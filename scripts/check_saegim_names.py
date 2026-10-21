#!/usr/bin/env python3
"""옛 이름(saegim, 새김) 재발 방지 검사 (2026-10-20 노트, 사장님 지시: 이름이 어디서 튀어나올지 모르게 되기 전에 없앤다).

원리: 저장소에 올라간 파일마다 옛 이름이 몇 번 나오는지 세어 기준표(docs/saegim_baseline.json)와 비교한다.
- 기준표에 없는 파일에 새로 나오면 실패한다.
- 기준표에 있는 파일에서 횟수가 늘면 실패한다.
- 횟수가 줄면 통과하고, --ratchet 으로 기준표를 줄인 값으로 갱신한다(늘리는 갱신은 못 한다).
정리 단계가 끝나 기준표가 비면 옛 이름은 완전히 사라진 것이다.

사용:
  python scripts/check_saegim_names.py            검사(실패하면 종료 코드 1)
  python scripts/check_saegim_names.py --init      기준표를 현재 상태로 새로 만든다(처음 한 번만)
  python scripts/check_saegim_names.py --ratchet   줄어든 만큼만 기준표를 낮춘다
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "docs" / "saegim_baseline.json"
PATTERN = re.compile(r"saegim|새김", re.IGNORECASE)
# 검사에서 빼는 것: 기준표 자신, 옛 기록(바꾸지 않는 역사), 이 검사와 시험
SKIP_PREFIXES = ("docs/진행상황_아카이브/",)
SKIP_FILES = {"docs/saegim_baseline.json", "scripts/check_saegim_names.py", "scripts/test_check_saegim_names.py",
              "scripts/ops/name_scan.py", "scripts/ops/name_scan_config.json", "scripts/test_name_scan.py"}


def tracked_files(root=ROOT):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "replace")
        if rel in SKIP_FILES or rel.startswith(SKIP_PREFIXES):
            continue
        yield rel


def count_text(text):
    return len(PATTERN.findall(text))


def scan(root=ROOT):
    counts = {}
    for rel in tracked_files(root):
        p = Path(root) / rel
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            continue  # 이진 파일
        n = count_text(data.decode("utf-8", "replace"))
        if n:
            counts[rel] = n
    return counts


def compare(current, baseline):
    """(늘어난 항목 {파일:(전,후)}, 줄어든 항목 {파일:(전,후)})"""
    worse, better = {}, {}
    for f, n in current.items():
        b = baseline.get(f, 0)
        if n > b:
            worse[f] = (b, n)
    for f, b in baseline.items():
        n = current.get(f, 0)
        if n < b:
            better[f] = (b, n)
    return worse, better


def load_baseline():
    return json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}


def save_baseline(data):
    BASELINE.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def main(argv):
    current = scan()
    if "--init" in argv:
        save_baseline(current)
        print(f"기준표 생성: {len(current)}개 파일, 합계 {sum(current.values())}곳")
        return 0
    baseline = load_baseline()
    worse, better = compare(current, baseline)
    if "--ratchet" in argv:
        new = {f: min(n, baseline.get(f, n)) for f, n in current.items() if f in baseline}
        save_baseline(new)
        print(f"기준표 낮춤: {len(baseline)}개 -> {len(new)}개 파일, 합계 {sum(baseline.values())} -> {sum(new.values())}")
        return 0
    if worse:
        print("옛 이름(saegim·새김)이 새로 생기거나 늘었습니다. carvit 이름을 쓰세요(docs/이름_정책.md):")
        for f, (b, n) in sorted(worse.items()):
            print(f"  {f}: {b} -> {n}")
        return 1
    print(f"통과: 옛 이름 {sum(current.values())}곳(기준 {sum(baseline.values())}곳), 줄어든 파일 {len(better)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
