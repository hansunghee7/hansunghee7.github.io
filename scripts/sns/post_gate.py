#!/usr/bin/env python3
"""SNS 게시 전 공용 관문(2026-10-15 마야, 공용-에이전트마찰개선 #5).

같은 규칙이 게시 경로마다 따로 적혀 있어(큐 등록 publish_sns_queue.py, 링크드인 직접 게시
post_linkedin_oldpc.py) 수동 채널(페이스북 개인, 로켓펀치, 리멤버)에는 관문이 없었다.
규칙을 이 파일 하나에 두고 모든 경로가 같은 검사를 통과하게 한다. 정본: 공정 마야-SNS게시 #2·#3.
  - 첫 줄 = 글 제목(제목을 줄 때만 검사)
  - 본문 링크는 딱 1개. 독자가 보고 싶은 곳으로 바로 건다(팀 페이지, 신청 페이지 등).
    우리 로그 글(simplifier.co.kr/logs/)을 걸 때만 9/28 확정 CTA 문구 "심플리파이어 로그를 함께 봐 주세요"가 필요하다.
    (사장님 2026-10-17, 공정 마야-SNS게시 #8: 두 번 클릭하게 하면 글 올린 사람을 싫어한다)
  - 원문 링크 줄("전문:", "from ...") 금지
  - 링크드인은 예외(사장님 2026-10-17, 공정 마야 #121): CTA 정본 문구와 "결론부터 말하면"을 쓰지 않는다.
    사장님이 쓴 글처럼 읽히지 않는 상투구라서다. 관련 글 링크 1개 규칙은 그대로다.

수동 채널에 붙여넣기 전: python scripts/sns/post_gate.py --file 본문.txt --title "글 제목"
STOP이면 종료 코드 1과 이유를 JSON으로 낸다. 구PC 작업실에서 쓰려면 이 파일을 post_linkedin.py 옆에 같이 복사한다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

CTA = "심플리파이어 로그를 함께 봐 주세요"
LOG_LINK = "simplifier.co.kr/logs/"
LINKEDIN_BANNED = (CTA, "결론부터 말하면")
# 신청 링크처럼 독자가 바로 갈 곳이 여럿인 글(사장님 10/19 크레딧 글: MS·AWS·NVIDIA)을 위해 직접 링크는 3개까지.
MAX_DIRECT_LINKS = 3


def is_linkedin(channel):
    c = (channel or "").lower()
    return "linkedin" in c or "링크드인" in c


def text_problems(text, title=None, channel=""):
    """규칙을 어긴 이유 목록을 돌려준다(빈 목록이면 통과). title이 있으면 첫 줄이 제목인지도 본다."""
    problems = []
    lines = text.strip().splitlines()
    if title is not None:
        first = lines[0].strip() if lines else ""
        if first != title.strip():
            problems.append("첫 줄이 글 제목과 다릅니다(제목을 첫 줄에 넣을 것)")
    urls = re.findall(r"https?://\S+", text)
    log_link = any(LOG_LINK in u for u in urls)
    # 인스타·스레드는 본문 링크가 안 걸리거나 늦게 달려 링크를 첫 댓글·답글로 단다(공정 마야-SNS게시 #9): 본문 0개 허용.
    link_in_comment = any(k in (channel or "").lower() for k in ("instagram", "인스타", "threads", "스레드"))
    if log_link and len(urls) != 1:
        problems.append(f"로그 글 링크를 걸 때는 링크가 딱 1개여야 합니다(지금 {len(urls)}개)")
    elif not urls and not link_in_comment:
        problems.append("본문 링크가 없습니다(독자가 갈 곳을 바로 걸 것)")
    elif len(urls) > MAX_DIRECT_LINKS:
        problems.append(f"본문 링크가 {len(urls)}개입니다(독자가 바로 갈 곳은 {MAX_DIRECT_LINKS}개까지)")
    if is_linkedin(channel):
        for phrase in LINKEDIN_BANNED:
            if phrase in text:
                problems.append(f"링크드인 글에 '{phrase}'가 있습니다(사장님이 안 쓴 것 같은 상투구, 공정 마야 #121)")
    elif log_link and CTA not in text:
        problems.append("CTA 정본 문구('혹시 ~궁금하시다면 심플리파이어 로그를 함께 봐 주세요')가 없습니다(공정 마야-SNS게시 #3)")
    if "전문:" in text or any(l.strip().startswith("from ") for l in lines):
        problems.append("원문 링크 줄('전문:'·'from')이 있습니다(공정 마야-SNS게시 #3)")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="SNS 게시 전 공용 관문")
    ap.add_argument("--file", required=True, help="게시할 본문 텍스트 파일(UTF-8)")
    ap.add_argument("--title", help="글 제목(주면 첫 줄과 같은지 검사)")
    ap.add_argument("--channel", default="", help="채널 이름(예: 페이스북 개인, linkedin). 링크드인이면 상투구 금지 규칙을 쓴다")
    a = ap.parse_args(argv)
    text = Path(a.file).read_text(encoding="utf-8")
    why = text_problems(text, a.title, a.channel)
    print(json.dumps({"status": "STOP" if why else "OK", "channel": a.channel, "why": why}, ensure_ascii=False))
    return 1 if why else 0


if __name__ == "__main__":
    sys.exit(main())
