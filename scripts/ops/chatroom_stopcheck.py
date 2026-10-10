#!/usr/bin/env python3
"""교신 규약 3번의 중지 확인 관문(공용). 반복 작업은 매 단계 전에 이 함수로 PR 댓글 목록을 확인한다.

사용:
  python chatroom_stopcheck.py --test                 가짜 입력으로 자체 시험(사전 점검, 원본 출력을 PR에 붙인다)
  python chatroom_stopcheck.py <기준시각UTC ISO>       stdin의 gh api 댓글 JSON에서 기준 시각 이후 '중지' 수를 출력
판독에 실패하면 예외를 그대로 올린다. 호출부는 예외를 '멈춤'으로 처리해야 한다(안전 쪽).
"""
import json
import sys


def count_stop(comments, after_iso):
    """after_iso 이후(초과)에 달린, 첫 글자가 '중지'인 댓글 수. 말머리(`[사장→전체] 중지`)가 있는 형식도 센다."""
    n = 0
    for x in comments:
        if x["created_at"] <= after_iso:
            continue
        body = x["body"].strip()
        if body.startswith("중지"):
            n += 1
        elif body.startswith("[") and "]" in body and body.split("]", 1)[1].strip().startswith("중지"):
            n += 1
    return n


def _self_test():
    after = "2026-10-08T08:20:00Z"
    start = {"created_at": "2026-10-08T08:20:00Z", "body": "[탐→핏 #5] 시작"}
    cases = [
        ("목록A(중지 있음, 기준 이후)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "중지"}], 1),
        ("목록B(중지 없음)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "[핏→탐 #5-1] 시험 메시지"}], 0),
        ("목록C(옛 중지만)", [{"created_at": "2026-10-08T07:32:19Z", "body": "중지"}, start], 0),
        ("목록D(말머리 달린 중지)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "[사장→전체] 중지"}], 1),
    ]
    ok = True
    for name, data, want in cases:
        got = count_stop(data, after)
        ok &= got == want
        print(f"{name:28s} 기대 {want} → 결과 {got}")
    print("깨진 입력(JSON 아님)         기대 예외 →", end=" ")
    try:
        count_stop("not-json", after)
        print("예외 없음(실패)")
        ok = False
    except Exception as e:
        print("예외", type(e).__name__)
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용: chatroom_stopcheck.py --test | <기준시각UTC ISO> (stdin에 댓글 JSON)")
    if sys.argv[1] == "--test":
        sys.exit(_self_test())
    print(count_stop(json.load(sys.stdin), sys.argv[1]))
