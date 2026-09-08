#!/usr/bin/env python3
"""PostToolUse 훅(Write|Edit|MultiEdit): .md/.html 저장 직후 새로 들어간 줄에 긴 줄표(— –)가
있으면 exit 2로 알려 그 자리에서 고치게 한다. 기계가 치환하지 않는다(문맥 판단은 쓴 쪽).

- 검사 범위: HEAD 대비 새로 추가·변경된 줄만 (CI의 check_writing_style.py와 같은 기준).
  기존에 있던 줄표(예: 옛 문서)는 건드리지 않는다.
- 예외: 인용 블록(`>`로 시작하는 줄), 코드 펜스(``` ~ ```) 안, 줄표 예시를 설명하는 줄
  ("줄표(—)"처럼 문자를 예시로 보여주는 줄만 규칙 설명으로 본다).
- 검사기 오류·git 없음·대상 아님이면 항상 exit 0.
"""
import json, re, subprocess, sys, difflib, os

LONG_DASH = re.compile("[—–]")
EXT = (".md", ".html")

def head_lines(path):
    try:
        top = subprocess.run(["git","rev-parse","--show-toplevel"], cwd=os.path.dirname(path) or ".",
                             capture_output=True, text=True, check=True).stdout.strip()
        rel = os.path.relpath(path, top)
        out = subprocess.run(["git","-c","core.quotepath=false","show",f"HEAD:{rel}"], cwd=top,
                             capture_output=True, text=True)
        return out.stdout.splitlines() if out.returncode == 0 else []
    except Exception:
        return []

def new_lines(path):
    cur = open(path, encoding="utf-8", errors="replace").read().splitlines()
    old = head_lines(path)
    if not old: return list(enumerate(cur, 1))
    sm = difflib.SequenceMatcher(None, old, cur, autojunk=False)
    res = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            res.extend((j+1, cur[j]) for j in range(j1, j2))
    return res

def offenders(path):
    hits, fence = [], False
    all_lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    new = dict(new_lines(path))
    for n, line in enumerate(all_lines, 1):
        if line.strip().startswith("```"): fence = not fence; continue
        if fence or n not in new: continue
        s = line.lstrip()
        if s.startswith(">"): continue
        if re.search(r"(줄표|대시|dash)\s*\(", line, re.I): continue  # 예: 긴 줄표(—)는 … 규칙 설명
        if LONG_DASH.search(line): hits.append((n, line.strip()[:90]))
    return hits

if __name__ == "__main__":
    try:
        data = json.load(sys.stdin)
        path = (data.get("tool_input") or {}).get("file_path") or ""
        if not path.lower().endswith(EXT) or not os.path.isfile(path): sys.exit(0)
        hits = offenders(path)
    except SystemExit: raise
    except Exception: sys.exit(0)
    if not hits: sys.exit(0)
    print(f"{os.path.basename(path)}: 새로 쓴 줄에 긴 줄표(— –)가 {len(hits)}건 있습니다. 원칙 9(WAY#3c12). "
          "쌍점·쉼표·괄호·문장 나누기로 지금 고쳐 다시 저장하세요. 남의 문장을 그대로 옮긴 것이면 인용 블록(>)으로 감싸면 통과합니다.", file=sys.stderr)
    for n, l in hits[:5]: print(f"  {n}: {l}", file=sys.stderr)
    sys.exit(2)
