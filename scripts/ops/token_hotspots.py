#!/usr/bin/env python3
"""token_hotspots.py: 클로드 코드 대화 기록에서 "토큰을 크게 태우는 습관"을 찾는다(탐의 다이어트 발굴용, 2026-09-22).

세 가지를 본다:
 1) 도구별 결과 크기 합계(어느 도구가 컨텍스트를 부풀리나). 결과 1바이트는 이후 모든 호출에서 캐시읽기로 다시 계산된다.
 2) 세션 길이별 호출당 평균 컨텍스트(긴 세션일수록 한 번 호출이 비싸다).
 3) 반복 명령 상위(폴링·중복 조회 후보).
사용: python scripts/ops/token_hotspots.py [--days 4] [--match hansunghee7-github-io]
"""
import argparse, collections, datetime, json, re, sys
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"


def rlen(c):
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return sum(len(x.get("text", "")) if isinstance(x, dict) else len(str(x)) for x in c)
    return 0


def norm(cmd):
    cmd = re.sub(r"\s+", " ", cmd.strip())
    return re.sub(r"\d{3,}", "N", cmd)[:90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--match", default="hansunghee7-github-io")
    a = ap.parse_args()
    since = datetime.datetime.now().timestamp() - a.days * 86400
    tool_n = collections.Counter(); tool_b = collections.Counter(); big = []
    cmds = collections.Counter(); cmd_b = collections.Counter()
    sess = []
    for proj in ROOT.iterdir():
        if a.match not in proj.name:
            continue
        for f in proj.glob("*.jsonl"):
            if f.stat().st_mtime < since:
                continue
            names = {}; calls = 0; ctx = 0; seen = set()
            for line in open(f, encoding="utf-8", errors="replace"):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                m = r.get("message") or {}
                c = m.get("content")
                if r.get("type") == "assistant":
                    u = m.get("usage")
                    k = (m.get("id"), r.get("requestId"))
                    if u and k not in seen:
                        seen.add(k); calls += 1
                        ctx += u.get("cache_read_input_tokens", 0) + u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                    if isinstance(c, list):
                        for x in c:
                            if isinstance(x, dict) and x.get("type") == "tool_use":
                                names[x["id"]] = (x["name"], (x.get("input") or {}).get("command") or (x.get("input") or {}).get("file_path") or "")
                elif r.get("type") == "user" and isinstance(c, list):
                    for x in c:
                        if isinstance(x, dict) and x.get("type") == "tool_result":
                            n, arg = names.get(x.get("tool_use_id"), ("?", ""))
                            L = rlen(x.get("content"))
                            tool_n[n] += 1; tool_b[n] += L
                            if L > 20000:
                                big.append((L, n, str(arg)[:80]))
                            if n == "Bash" and arg:
                                cmds[norm(arg)] += 1; cmd_b[norm(arg)] += L
            if calls:
                sess.append((calls, ctx / calls))
    print("== 1) 도구별 결과 크기 (글자수 합, 건수)")
    for n, b in tool_b.most_common(8):
        print(f"  {n:22} {b/1e6:7.2f}M자  {tool_n[n]:5d}건  평균 {b//max(1,tool_n[n]):6d}자")
    print("== 1-b) 2만 자 넘는 단건 결과 상위")
    for L, n, arg in sorted(big, reverse=True)[:8]:
        print(f"  {L/1e3:7.0f}K자  {n}  {arg}")
    print("== 2) 세션 길이별 호출당 평균 컨텍스트(토큰)")
    for lo, hi in ((0, 100), (100, 250), (250, 400), (400, 10**9)):
        xs = [c for n, c in sess if lo <= n < hi]
        if xs:
            print(f"  호출 {lo}~{hi if hi < 10**9 else '+'}: 세션 {len(xs):3d}개, 호출당 평균 {sum(xs)/len(xs)/1e3:6.0f}K")
    print("== 3) 반복 Bash 명령 상위(건수, 결과 글자수)")
    for c, n in cmds.most_common(12):
        print(f"  {n:4d}건 {cmd_b[c]/1e3:7.0f}K자  {c}")


if __name__ == "__main__":
    sys.exit(main())
