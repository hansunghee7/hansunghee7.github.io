#!/usr/bin/env python3
"""구PC SNS 읽기(sns_read.py) 결과와 크롬 확장 기록(저장소 공개 데이터)을 비교한다(2026-09-24 탐).

사장님 결정(2026-09-24): 매일 자동 수집을 걸고 확장과 3일 나란히 비교한 뒤, 맞으면 스튜디오 데이터에 연결하고
확장은 끈다. 이 스크립트는 판정하지 않고 차이만 표로 남긴다(판정은 탐 세션이 3일치를 보고 한다).

사용: python sns_compare.py out/sns/<날짜>.jsonl > out/sns/compare_<날짜>.md
비교 기준: 확장 기록 중 같은 날짜 값(없으면 가장 최근 값과 그 날짜를 같이 표시).
"""
import json, sys, urllib.request

RAW = "https://raw.githubusercontent.com/hansunghee7/hansunghee7.github.io/main/assets/data/"


def fetch(name):
    with urllib.request.urlopen(RAW + name, timeout=30) as r:
        return json.load(r)


def last(hist, date):
    same = [h for h in hist if h.get("date") == date]
    return (same or hist or [{}])[-1]


def main():
    mine = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    date = mine[0]["date"] if mine else ""
    insight, content = fetch("sns-insight.json"), fetch("naver-content.json")
    rows = []
    for r in mine:
        k = r["key"]
        if k in insight:
            e = last(insight[k], date)
            rows.append((k, "팔로워", r.get("followers"), e.get("count"), e.get("date")))
        elif k in content.get("channels", {}):
            e = last(content["channels"][k]["history"], date)
            for f in ("followers", "following", "likes"):
                if f in e or r.get(f) is not None:
                    rows.append((k, f, r.get(f) if f != "followers" else r.get("followers"), e.get(f), e.get("date")))
        items = r.get("items") or []
        if k in ("content_instagram", "content_tiktok") and items:
            same = diff = 0
            for it in items:
                h = content.get("clips", {}).get(f"{k}_{it['id']}", {}).get("history", [])
                if not h:
                    continue
                ev = last(h, date).get("views")
                if ev is None:
                    continue
                # 확장은 1.5만 → 15000처럼 크게 반올림한다. 5% 안이면 같은 값으로 본다
                (same := same + 1) if abs((it["views"] or 0) - ev) <= max(1, 0.05 * ev) else (diff := diff + 1)
            rows.append((k, f"게시물 조회수 {len(items)}개", f"일치 {same}", f"차이 {diff}", date))
        if k == "naver_clip" and items:
            ext = [c for c in content.get("clips", {}) if c.startswith("naver_clip_")]
            rows.append((k, "클립 수", len(items), len(ext), date))
    print(f"# SNS 읽기 비교 {date} (구PC vs 크롬 확장)\n")
    print("| 채널 | 항목 | 구PC | 확장 | 확장 기록 날짜 |")
    print("|---|---|---|---|---|")
    for row in rows:
        print("| " + " | ".join(str(x) for x in row) + " |")


if __name__ == "__main__":
    main()
