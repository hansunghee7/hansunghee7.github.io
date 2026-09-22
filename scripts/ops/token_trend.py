#!/usr/bin/env python3
"""token_trend.py: 클로드 코드 대화 기록(~/.claude/projects)에서 프로젝트(폴더)별·날짜별 토큰 사용량을 집계한다.

왜: 주간 한도를 어디가 태우는지 추측이 아니라 숫자로 본다(탐의 다이어트 발굴용, 2026-09-22 사장님 지시로
핏의 소모 추이 관측). 사용량 가중은 API 단가 비율(입력 1 : 캐시쓰기 1.25 : 캐시읽기 0.1 : 출력 5)로 환산한
"입력 환산 토큰"을 함께 낸다(한도 소모의 근사치일 뿐 실제 한도 공식은 아니다).

사용: python scripts/ops/token_trend.py [--days 8] [--match shorts] [--projects]
  --match  폴더 이름에 이 문자열이 든 프로젝트만
  --projects  날짜 대신 프로젝트별 합계만
  --persona   세션 첫 메시지("하이 <이름>")로 페르소나를 판별해 날짜별로 집계(이 저장소·쇼츠랩 프로젝트만)
"""
import argparse
import collections
import datetime
import json
import sys
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
W = {"in": 1.0, "cw": 1.25, "cr": 0.1, "out": 5.0}


def scan(days, match):
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    seen = set()
    agg = collections.defaultdict(lambda: collections.defaultdict(lambda: dict.fromkeys(("in", "cw", "cr", "out", "msgs"), 0)))
    for proj in ROOT.iterdir():
        if not proj.is_dir() or (match and match not in proj.name):
            continue
        for f in proj.rglob("*.jsonl"):
            if f.stat().st_mtime < since.timestamp():
                continue
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    m = r.get("message") or {}
                    u = m.get("usage")
                    if r.get("type") != "assistant" or not u:
                        continue
                    key = (m.get("id"), r.get("requestId"))
                    if key in seen:
                        continue
                    seen.add(key)
                    ts = r.get("timestamp", "")
                    try:
                        t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                    except ValueError:
                        continue
                    if t < since:
                        continue
                    a = agg[proj.name][t.strftime("%m-%d")]
                    a["in"] += u.get("input_tokens", 0)
                    a["cw"] += u.get("cache_creation_input_tokens", 0)
                    a["cr"] += u.get("cache_read_input_tokens", 0)
                    a["out"] += u.get("output_tokens", 0)
                    a["msgs"] += 1
    return agg


PERSONAS = ("탐", "핏", "마야", "시안", "노트", "페이브", "헤르메스")


def persona_of(f):
    """세션 파일의 첫 사용자 메시지에서 페르소나 이름을 찾는다(없으면 '기타')."""
    with open(f, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") != "user":
                continue
            c = (r.get("message") or {}).get("content")
            text = c if isinstance(c, str) else (c[0].get("text", "") if c else "")
            for name in PERSONAS:
                if name in text[:40]:
                    return name
            return "기타"
    return "기타"


def scan_persona(days):
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    seen = set()
    agg = collections.defaultdict(lambda: collections.defaultdict(lambda: dict.fromkeys(("in", "cw", "cr", "out", "msgs"), 0)))
    for proj in ROOT.iterdir():
        if not proj.is_dir() or not ("hansunghee7-github-io" in proj.name or "shorts-lab" in proj.name):
            continue
        for f in proj.glob("*.jsonl"):  # 서브에이전트 파일은 부모 폴더 안에 있어 제외(부모 세션에 이미 요약 반영)
            if f.stat().st_mtime < since.timestamp():
                continue
            who = persona_of(f)
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    m = r.get("message") or {}
                    u = m.get("usage")
                    if r.get("type") != "assistant" or not u:
                        continue
                    key = (m.get("id"), r.get("requestId"))
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        t = datetime.datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00")).astimezone()
                    except ValueError:
                        continue
                    if t < since:
                        continue
                    a = agg[who][t.strftime("%m-%d")]
                    a["in"] += u.get("input_tokens", 0)
                    a["cw"] += u.get("cache_creation_input_tokens", 0)
                    a["cr"] += u.get("cache_read_input_tokens", 0)
                    a["out"] += u.get("output_tokens", 0)
                    a["msgs"] += 1
    return agg


def weighted(a):
    return sum(a[k] * W[k] for k in W)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--match", default="")
    ap.add_argument("--projects", action="store_true")
    ap.add_argument("--persona", action="store_true")
    args = ap.parse_args()
    if args.persona:
        agg = scan_persona(args.days)
        alld = sorted({d for v in agg.values() for d in v})
        print("페르소나  " + "  ".join(f"{d:>7}" for d in alld) + "   (단위 M환산)")
        for who, days in sorted(agg.items(), key=lambda kv: -sum(weighted(a) for a in kv[1].values())):
            print(f"{who:6}  " + "  ".join(f"{weighted(days[d])/1e6:7.1f}" if d in days else "      -" for d in alld))
        return
    agg = scan(args.days, args.match)
    if args.projects:
        rows = []
        for p, days in agg.items():
            tot = dict.fromkeys(("in", "cw", "cr", "out", "msgs"), 0)
            for a in days.values():
                for k in tot:
                    tot[k] += a[k]
            rows.append((weighted(tot), p, tot))
        for w, p, t in sorted(rows, reverse=True):
            print(f"{w/1e6:9.1f}M환산  호출 {t['msgs']:6d}  캐시읽기 {t['cr']/1e6:8.1f}M  출력 {t['out']/1e3:7.0f}K  {p}")
        return
    for p, days in sorted(agg.items(), key=lambda kv: -sum(weighted(a) for a in kv[1].values())):
        print(f"\n## {p}")
        for d in sorted(days):
            a = days[d]
            print(f"{d}  {weighted(a)/1e6:8.1f}M환산  호출 {a['msgs']:5d}  캐시읽기 {a['cr']/1e6:7.1f}M  캐시쓰기 {a['cw']/1e6:6.1f}M  출력 {a['out']/1e3:6.0f}K")


if __name__ == "__main__":
    sys.exit(main())
