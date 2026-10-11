#!/usr/bin/env python3
"""교신 규약 3번의 중지 확인 관문(공용). 반복 작업은 매 단계 전에 이 함수로 PR 댓글 목록을 확인한다.

사용:
  python chatroom_stopcheck.py --test                   가짜 입력으로 자체 시험(사전 점검, 원본 출력을 PR에 붙인다)
  python chatroom_stopcheck.py <기준시각 ISO(Z 또는 +09:00)>  stdin의 gh api 댓글 JSON에서 기준 시각 이후 '중지' 수를 출력
기준 시각을 읽지 못하면 '확인 불가'를 stderr에 내고 종료 코드 2로 끝난다. 호출부는 이를 '멈춤'으로 처리해야 한다(안전 쪽).
"""
import json
import sys
from datetime import datetime, timezone


class StopCheckUnavailable(Exception):
    """기준 시각을 읽지 못해 중지 확인이 불가능함. 호출부는 '멈춤'으로 처리한다(종료 코드 2)."""


def _ts(iso):
    """시각 정규화 규칙: 끝의 Z만 +00:00으로 바꿔 읽고, 오프셋이 없는 시각(naive)은 UTC로 간주해 aware로 만든다."""
    t = iso.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    d = datetime.fromisoformat(t)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def _is_stop(body):
    body = body.strip()
    if body.startswith("중지"):
        return True
    return body.startswith("[") and "]" in body and body.split("]", 1)[1].strip().startswith("중지")


def count_stop(comments, after_iso):
    """after_iso 이후(같은 순간 포함)에 달린 '중지' 댓글 수. 말머리(`[사장→전체] 중지`) 형식도 센다.
    기준 시각 파싱 실패 -> StopCheckUnavailable. 댓글 시각 파싱 실패 행은 건너뛰지 않고 경고를 남기며,
    중지 형식이면 시각과 무관하게 센다(안전 쪽)."""
    try:
        after = _ts(after_iso)
    except Exception as e:
        raise StopCheckUnavailable(f"기준 시각 판독 불가: {after_iso!r} ({e})")
    n = 0
    for x in comments:
        try:
            late = _ts(x["created_at"]) >= after
        except Exception:
            print(f"경고: 댓글 시각 판독 불가 {x.get('created_at')!r}, 중지 형식이면 센다", file=sys.stderr)
            late = True
        if late and _is_stop(x["body"]):
            n += 1
    return n


def _self_test():
    after = "2026-10-08T08:20:00Z"
    start = {"created_at": "2026-10-08T08:20:00Z", "body": "[탐→핏 #5] 시작"}
    kst = "2026-10-08T17:20:00+09:00"
    cases = [
        ("목록A(중지 있음, 기준 이후)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "중지"}], 1),
        ("목록B(중지 없음)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "[핏→탐 #5-1] 시험 메시지"}], 0),
        ("목록C(옛 중지만)", [{"created_at": "2026-10-08T07:32:19Z", "body": "중지"}, start], 0),
        ("목록D(말머리 달린 중지)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "[사장→전체] 중지"}], 1),
        ("목록E(기준 +09:00, 중지 이후)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "중지"}], 1, kst),
        ("목록F(기준 +09:00, 옛 중지)", [start, {"created_at": "2026-10-08T08:19:00Z", "body": "중지"}], 0, kst),
        ("목록G(기준 naive=UTC 간주)", [start, {"created_at": "2026-10-08T08:21:00Z", "body": "중지"}], 1, "2026-10-08T08:20:00"),
        ("목록H(같은 순간 중지도 센다)", [{"created_at": "2026-10-08T08:20:00Z", "body": "중지"}], 1),
        ("목록I(댓글 시각 깨짐+중지)", [{"created_at": "???", "body": "중지"}], 1),
        ("목록J(중간 Z 금지, 깨짐 처리)", [{"created_at": "2026-10-08Z08:21:00", "body": "중지"}], 1),
        ("목록K(댓글 naive도 비교)", [{"created_at": "2026-10-08T08:21:00", "body": "중지"}], 1),
    ]
    ok = True
    for name, data, want, *alt in cases:
        got = count_stop(data, alt[0] if alt else after)
        ok &= got == want
        print(f"{name:28s} 기대 {want} → 결과 {got}")
    print("기준 시각 깨짐 기대 확인불가 →", end=" ")
    try:
        count_stop([], "garbage")
        print("예외 없음(실패)")
        ok = False
    except StopCheckUnavailable:
        print("확인 불가")
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
        sys.exit("사용: chatroom_stopcheck.py --test | <기준시각 ISO> (stdin에 댓글 JSON)")
    if sys.argv[1] == "--test":
        sys.exit(_self_test())
    try:
        print(count_stop(json.load(sys.stdin), sys.argv[1]))
    except StopCheckUnavailable as e:
        print(f"확인 불가: {e}", file=sys.stderr)
        sys.exit(2)
