"""홈페이지 글 하나에서 SNS 큐 "초안" 항목(페이스북·인스타)을 만든다.

왜: 원칙(사장님 2026-09-29) 월·수 홈페이지 글은 화·목에 SNS로 예약한다. 손으로 큐를 채우다 보니
원본이 없거나 잊어서 슬롯이 비었다. 이 스크립트는 글이 있으면 초안을 자동으로 만들어 준다.

안전장치: 만든 항목은 status="draft", approved_by 없음이다. publish_sns_queue.py 는 approved_by가 있는
pending 항목만 등록하므로 이 초안은 사장님 승인 전에는 절대 등록되지 않는다. 승인하면
status를 "pending"으로, approved_by/approved_quote를 채워 커밋한다.

규칙(실측 2026-09-29): AItoEarn 링크드인은 이미지 1장을 거부(최소 2장)해 사진 없이 나갔다. 대표 이미지는
필수라(사장님 2026-09-28·10-02) 링크드인은 이 큐에서 빼고 링크드인 자체 예약 기능으로 올린다
(마야_프로세스표.md). 페이스북·인스타는 표지
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
    # 페이스북 Simplifier 페이지는 폐지(사장님 2026-10-06): 팔로워 0, Meta 368 미게시. 개인 프로필은 크롬 직접 게시.
    ("ig", "instagram", "instagram_17841401170630001", {"media_type": "IMAGE"}, True),
]


def add_utm(body, source, post_no):
    """본문 속 simplifier.co.kr 글 링크에 UTM을 붙인다(docs/UTM_규칙.md, 2026-10-06 마야).

    왜: 링크에 UTM이 없으면 GA4에서 어느 글·채널이 방문을 만들었는지 못 나눈다(마야 KPI: 좋아요·조회수를
    홈페이지 유입으로 연결). campaign은 이 SNS 글의 홈페이지 원본 번호(new_<번호>), content는 링크가 가리키는 글 번호.
    """
    def repl(m):
        url, link_id, query = m.group(0), m.group(1), m.group(2) or ""
        if "utm_" in query:
            return url
        base = f"https://simplifier.co.kr/logs/{link_id}" + ("/" if url.rstrip("?").split("?")[0].endswith("/") else "")
        extra = (query[1:] + "&") if query else ""
        return (f"{base}?{extra}utm_source={source}&utm_medium=social"
                f"&utm_campaign=new_{post_no}&utm_content=post_{link_id}")
    return re.sub(r"https://simplifier\.co\.kr/logs/(\d+)/?(\?\S*)?", repl, body)


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
    # 본문 끝에 "from 원문 링크" 줄을 붙이지 않는다(사장님 지시 2026-09-30, 글 안 콜투액션 링크로 충분)
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
        content = {"title": title, "body": add_utm(body, plat, a.post_no)}
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
