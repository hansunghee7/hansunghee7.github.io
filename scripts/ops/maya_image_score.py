# -*- coding: utf-8 -*-
"""이미지 선정 조건 8개 채점 파일 만들기(마야, 2026-10-11). publish_sns_queue.py의 관문이 이 파일을 검사한다.
조건 정본: docs/질문하기_파이프라인.md 5-2절 (1 빅아이디어 필수, 2 정보 전달, 3 진짜 사물, 4 초점 하나·대비, 5 작게 봐도 식별,
6 제목과 맞고 궁금증, 7 규격·중앙 초점, 8 사람 사진은 실제 정면 응시/정보성은 사물). 후보는 반드시 열어 보고 채점한다.
사용: python scripts/ops/maya_image_score.py --queue-id <큐 항목 id> --image <저장소 안 이미지 경로> --source local-krea2
        --idea "빅아이디어 한 문장" --conds 1,1,1,1,1,1,1,0 [--note "약점"] [--out assets/data/image_scores/<id>.json]
conds는 1~8번 조건을 순서대로 0/1로 쓴다. 점수는 합계로 자동 계산한다(6/8 미만이거나 1번이 0이면 만들지 않는다).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("unsplash", "nano-banana", "local-krea2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-id", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--source", required=True, choices=SOURCES)
    ap.add_argument("--idea", required=True)
    ap.add_argument("--conds", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    vals = [int(x) for x in a.conds.split(",")]
    if len(vals) != 8 or any(v not in (0, 1) for v in vals):
        print("거부: --conds는 0/1 여덟 개(1~8번 조건 순서)")
        return 2
    if len(a.idea.strip()) < 10:
        print("거부: 빅아이디어 한 문장이 10자 미만")
        return 2
    total = sum(vals)
    if total < 6 or vals[0] != 1:
        print(f"거부: {total}/8, 1번={vals[0]} (6/8 이상이고 1번 필수). 다른 후보를 고른다")
        return 2
    img = (ROOT / a.image).resolve()
    img.relative_to(ROOT)
    rec = {"queue_id": a.queue_id, "image": a.image.replace("\\", "/"), "sha256": hashlib.sha256(img.read_bytes()).hexdigest(),
           "source": a.source, "idea": a.idea.strip(), "conditions": {str(i + 1): v for i, v in enumerate(vals)},
           "score": f"{total}/8", "note": a.note}
    out = ROOT / (a.out or f"assets/data/image_scores/{a.queue_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(ROOT)} score={rec['score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
