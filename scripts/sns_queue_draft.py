"""홈페이지 글 하나에서 SNS 큐 "초안" 항목(링크드인·페이스북·인스타)을 만든다.

왜: 원칙(사장님 2026-09-29) 월·수 홈페이지 글은 화·목에 SNS로 예약한다. 손으로 큐를 채우다 보니
원본이 없거나 잊어서 슬롯이 비었다. 이 스크립트는 글이 있으면 초안을 자동으로 만들어 준다.

안전장치: 만든 항목은 status="draft", approved_by 없음이다. publish_sns_queue.py 는 approved_by가 있는
pending 항목만 등록하므로 이 초안은 사장님 승인 전에는 절대 등록되지 않는다. 승인하면
status를 "pending"으로, approved_by/approved_quote를 채워 커밋한다.

규칙(실측 2026-09-29): 링크드인은 이미지 1장이 규격 미달(최소 2장)이라 텍스트만, 페이스북·인스타는 표지
이미지를 저장소 파일(log_assets/images/...)로 넣는다(URL을 넣으면 확장자 없이 .bin으로 올라가 실패).

사용법: python scripts/sns_queue_draft.py 633 --date 2026-10-06 [--time 09:00]
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
CHANNELS = [
    ("li", "linkedin", "linkedin_uZRuHj0FqV", {}, False),
    ("fb", "facebook", "facebook_1276868818845114", {"content_category": "post"}, True),
    ("ig", "instagram", "instagram_17841401170630001", {"media_type": "IMAGE"}, True),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post_no")
    ap.add_argument("--date", required=True, help="SNS 게시일(KST) YYYY-MM-DD")
    ap.add_argument("--time", default="09:00")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    md = next((root / "log_assets/markdown").glob(f"{a.post_no}_*.md"), None)
    if md is None:
        sys.exit(f"{a.post_no}번 글 파일이 없습니다")
    text = md.read_text(encoding="utf-8")
    head, body = text.split("---\n", 2)[1], text.split("---\n", 2)[2].strip()
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M).group(1)
    body = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 \2", body)  # 마크다운 링크는 평문으로
    body += f"\n\nfrom https://simplifier.co.kr/logs/{a.post_no}/"
    cover = next((root / "log_assets/images").glob(f"{a.post_no}_*_cover.jpg"), None)
    if cover is None:
        m = re.search(r"^image:\s*'?\"?(https?://[^'\"\s]+)", head, re.M)
        if m:  # 표지가 외부 URL이면 저장소 파일로 받아 둔다(URL 그대로는 .bin으로 올라가 실패)
            import urllib.request
            cover = root / "log_assets/images" / f"{md.stem}_cover.jpg"
            req = urllib.request.Request(m.group(1), headers={"User-Agent": "simplifier-publisher/1.0"})
            cover.write_bytes(urllib.request.urlopen(req, timeout=30).read())
            print("표지 파일 저장:", cover.name)
        else:
            print("주의: 표지 이미지를 찾지 못했습니다. 페이스북·인스타는 표지 파일을 넣은 뒤 등록하세요.", file=sys.stderr)
    when = datetime.fromisoformat(f"{a.date}T{a.time}:00").replace(tzinfo=KST).astimezone(timezone.utc)
    q_path = root / "assets/data/sns_publish_queue.json"
    q = json.loads(q_path.read_text(encoding="utf-8"))
    existing = {x["id"] for x in q}
    added = []
    for pid, plat, acc, opt, needs_img in CHANNELS:
        item_id = f"{a.date}-{pid}-{a.post_no}"
        if item_id in existing:
            continue
        content = {"title": title, "body": body}
        if needs_img and cover:
            content["media_source"] = [str(cover.relative_to(root)).replace("\\", "/")]
        q.append({"id": item_id, "post_ref": a.post_no, "platform": plat, "accountId": acc, "option": opt,
                  "content": content, "publishAt": when.strftime("%Y-%m-%dT%H:%M:00.000Z"),
                  "status": "draft", "note": "초안(승인 전). 승인하면 status=pending, approved_by·approved_quote 기입"})
        added.append(item_id)
    q_path.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
    print("추가:", ", ".join(added) if added else "없음(이미 있음)")


if __name__ == "__main__":
    main()
