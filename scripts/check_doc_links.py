#!/usr/bin/env python3
"""docs/ 아래 마크다운의 상대 경로 링크 중 가리키는 파일이 저장소에 없는 것을 찾는다(읽기 전용, 파일을 고치지 않는다).

- 대상: `[글자](경로)`, `![글자](경로)` 형식. http(s)·mailto·#앵커만 있는 링크, 코드 블록·인라인 코드 안은 건너뛴다.
- 깨짐 판정: 링크가 있는 파일 기준으로 풀어 낸 경로가 git 추적 파일·폴더에 없음(`.md` 생략형도 허용).
- 후보: 같은 이름의 추적 파일이 저장소 전체에 하나뿐이면 "후보 1개"(이름만 옮겨진 것이 분명한 경우), 없거나 여럿이면 애매한 것.
- 사용: python3 scripts/check_doc_links.py [--json] [--include-archive]
  기본은 제외 대상(진행상황.md, 진행상황_아카이브/, 폴리싱_기록.md)의 깨진 링크를 따로 센다.
"""
import json
import os
import posixpath
import re
import subprocess
import sys
import urllib.parse
from collections import defaultdict

EXCL_FILES = {"docs/진행상황.md", "docs/폴리싱_기록.md"}
EXCL_PREFIX = ("docs/진행상황_아카이브/",)
LINK = re.compile(r'(?<!\!)\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\s*\)|!\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)')


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout.decode("utf-8")
    return [f for f in out.split("\0") if f]  # -z: 한글 파일명이 이스케이프되지 않게


def strip_code(text):
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            out.append("")
            continue
        out.append("" if fence else re.sub(r"`[^`]*`", "``", line))
    return out


def find_broken(files):
    fileset = set(files)
    dirs = {""}
    for f in files:
        d = posixpath.dirname(f)
        while d and d not in dirs:
            dirs.add(d)
            d = posixpath.dirname(d)
    by_base = defaultdict(list)
    for f in files:
        by_base[posixpath.basename(f)].append(f)
    res = []
    for f in files:
        if not (f.startswith("docs/") and f.endswith(".md")):
            continue
        for n, line in enumerate(strip_code(open(f, encoding="utf-8", errors="replace").read()), 1):
            for m in LINK.finditer(line):
                raw = (m.group(1) or m.group(2)).strip("<>")
                if re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*:|#|//|\{\{)", raw):
                    continue
                path = urllib.parse.unquote(raw.partition("#")[0].split("?")[0])
                if not path or path.startswith("/"):
                    continue  # 사이트 루트 기준(/로 시작) 링크는 상대 경로가 아니라 이번 점검 밖
                tgt = posixpath.normpath(posixpath.join(posixpath.dirname(f), path))
                if not tgt.startswith("..") and (tgt in fileset or tgt in dirs or tgt + ".md" in fileset):
                    continue
                res.append({"file": f, "line": n, "link": raw, "target": tgt, "candidates": by_base.get(posixpath.basename(path.rstrip("/")), []),
                            "excluded": f in EXCL_FILES or f.startswith(EXCL_PREFIX)})
    return res


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    res = find_broken(tracked())
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    live = [r for r in res if not r["excluded"] or "--include-archive" in sys.argv]
    skipped = len(res) - len([r for r in res if not r["excluded"]])
    for r in live:
        c = r["candidates"]
        hint = f"후보 1개: {c[0]}" if len(c) == 1 else ("후보 없음" if not c else f"후보 {len(c)}개(애매)")
        print(f"{r['file']}:{r['line']}: {r['link']} -> {hint}")
    print(f"깨진 링크 {len(live)}건(제외 대상 파일의 {skipped}건은 {'포함' if '--include-archive' in sys.argv else '따로 집계, --include-archive로 표시'})")
    return 1 if [r for r in res if not r["excluded"]] else 0


if __name__ == "__main__":
    sys.exit(main())
