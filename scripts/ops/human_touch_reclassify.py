#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사람 개입 기록 재분류 (NVIDIA 인사이트 ⑦).

이미 쌓인 human_touch_log.jsonl(훅이 `[사람 개입 필요: 사유]` 표시를 자동
적재한 곳)을 역추적해, 사람이 "실제로 판단"한 개입과 "분류·전달만" 한 개입을
가른다. 후자는 사람이 결정을 내린 게 아니라 규칙·기능 한계 때문에 손을 거친
것이라 **자동화(제품으로 없애기) 1순위 후보**다.

핵심 원칙(비티·덱스 슈퍼리뷰 보강): 사장님이 주간 로그를 손으로 쓰게 하지
않는다. 입력은 전적으로 이미 쌓인 기록이며, 이 스크립트는 읽기 전용이다.

사용 예:
    python scripts/ops/human_touch_reclassify.py            # 최근 7일
    python scripts/ops/human_touch_reclassify.py --days 30  # 최근 30일
    python scripts/ops/human_touch_reclassify.py --days 0   # 전체 기간
    python scripts/ops/human_touch_reclassify.py --json      # 기계용 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta

DEFAULT_LOG = r"C:/work/_ops/human_touch_log.jsonl"
TS_FMT = "%Y-%m-%d %H:%M:%S"

# ---- 분류 규칙 --------------------------------------------------------------
# CLAUDE.md 에이전틱 원칙의 사람 개입 4종에서 출발한다.
#   ① 자격증명  ② 비가역·돈 승인  ③ 제품·방향 결정  ④ 규칙상 금지(계정생성·외부발신·결제)
#
# 분류는 4개:
#   "실제 판단"       = 사람이 무언가를 고르거나 승인하는 결정을 내린 것.
#   "분류·전달만"     = 사람이 결정한 게 아니라 규칙·기능 한계 탓에 기계적으로 손을
#                       거친 것(외부 발신 대리, 계정 생성 등) → 자동화(제품으로 없애기) 1순위 후보.
#   "위임불가가능"    = 자격증명. OTP·2FA·CAPTCHA·실제 외부 로그인처럼 에이전트가
#                       대신 못 하는 개입이 섞여 있어, 자동화 후보 집계에서 빼고
#                       사람이 직접 봐야 할 "확인 필요"로 둔다(비티·덱스 슈퍼리뷰 ①).
#   "미분류"          = 뭉뚱그린 "규칙상 금지" 등. 명확한 신호가 없으면 여기 남긴다.
#
# 자동화 1순위 후보 Top은 "분류·전달만"에서만 뽑는다(자격증명 제외).

JUDGMENT = {"제품 결정", "방향 결정", "비가역", "돈"}
RELAY = {"외부 발신", "계정 생성"}
BLOCKED = {"자격증명"}  # 위임 불가 가능 → 자동화 후보에서 제외

JUDGMENT_LABEL = "실제 판단"
RELAY_LABEL = "분류·전달만"
BLOCKED_LABEL = "위임불가가능"
UNSURE_LABEL = "미분류"

# "규칙상 금지" 같은 모호 카테고리의 line 기반 재분류는 보수적으로 한다(슈퍼리뷰 ②).
# 아래 구체 구절은 하나만 있어도 "분류·전달만"으로 본다(명확한 신호).
RELAY_STRONG_PHRASES = (
    "복사해서 붙여넣", "복사해 붙여넣", "복사하여 붙여넣",
    "PIN 입력", "PIN을 입력", "인증번호 입력", "인증번호를 입력",
    "외부로 전송", "외부로 발신", "메일을 보내", "메일 발송", "메일 발신",
)
# 약한 키워드는 '입력'·'전달' 하나만으로 승격시키지 않는다. 둘 이상 동시에 있을 때만 이동.
RELAY_WEAK_KEYWORDS = (
    "발신", "전송", "메일", "이메일", "계정 생성", "로그인",
    "복사", "붙여넣", "붙여 넣", "전달", "입력", "PIN", "인증번호",
    "OAuth", "동의", "결제", "업로드", "게시",
)
JUDGMENT_KEYWORDS = (
    "결정", "판단", "선택", "승인", "할까요", "골라", "고르", "어느 것",
)


def classify(reason, line=""):
    """(category, bucket) 순수 함수. 부작용 없음.

    category: '실제 판단' | '분류·전달만' | '위임불가가능' | '미분류'
    bucket:   집계용 라벨(사유값 또는 '미분류').
    """
    reason = (reason or "").strip()
    line = line or ""

    if reason in JUDGMENT:
        return JUDGMENT_LABEL, reason
    if reason in BLOCKED:
        return BLOCKED_LABEL, reason
    if reason in RELAY:
        return RELAY_LABEL, reason

    # 알려진 카테고리가 아니거나 "규칙상 금지"처럼 모호한 경우: 본문 기반 재분류는
    # 과승격을 막기 위해 명확한 신호일 때만 이동하고, 애매하면 미분류로 남긴다.
    strong = any(p in line for p in RELAY_STRONG_PHRASES)
    weak_hits = sum(1 for k in RELAY_WEAK_KEYWORDS if k in line)
    if strong or weak_hits >= 2:
        return RELAY_LABEL, reason or "(사유없음)"
    if any(k in line for k in JUDGMENT_KEYWORDS):
        return JUDGMENT_LABEL, reason or "(사유없음)"

    return UNSURE_LABEL, reason or "(사유없음)"


# ---- 로그 읽기 --------------------------------------------------------------
def load_entries(path):
    """jsonl을 안전하게 읽어 dict 리스트로. 없거나 비면 빈 리스트."""
    entries = []
    try:
        f = open(path, encoding="utf-8")
    except FileNotFoundError:
        return entries
    with f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except (ValueError, json.JSONDecodeError):
                continue
            if isinstance(o, dict):
                entries.append(o)
    return entries


def parse_ts(s):
    try:
        return datetime.strptime((s or "").strip(), TS_FMT)
    except (ValueError, TypeError):
        return None


def filter_days(entries, days, now=None):
    """days<=0 이면 전체. 타임스탬프 파싱 실패 항목은 포함(버리지 않음)."""
    if days is None or days <= 0:
        return entries
    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    kept = []
    for e in entries:
        ts = parse_ts(e.get("t"))
        if ts is None or ts >= cutoff:
            kept.append(e)
    return kept


# ---- 집계 -------------------------------------------------------------------
def summarize(entries):
    """분류별 건수 + 버킷별 세부 Counter를 담은 dict 반환."""
    cat_counts = Counter()
    relay_buckets = Counter()
    blocked_buckets = Counter()
    unsure_buckets = Counter()
    unsure_lines = []
    for e in entries:
        cat, bucket = classify(e.get("reason"), e.get("line"))
        cat_counts[cat] += 1
        if cat == RELAY_LABEL:
            relay_buckets[bucket] += 1
        elif cat == BLOCKED_LABEL:
            blocked_buckets[bucket] += 1
        elif cat == UNSURE_LABEL:
            unsure_buckets[bucket] += 1
            ln = (e.get("line") or "").strip()
            if ln and ln not in unsure_lines:
                unsure_lines.append(ln)
    return {
        "total": len(entries),
        "by_category": dict(cat_counts),
        "relay_buckets": relay_buckets,
        "blocked_buckets": blocked_buckets,
        "unsure_buckets": unsure_buckets,
        "unsure_lines": unsure_lines,
    }


# ---- 출력 -------------------------------------------------------------------
def render_text(summ, days, top):
    out = []
    win = "전체 기간" if (days is None or days <= 0) else f"최근 {days}일"
    out.append(f"[사람 개입 기록 재분류] {win} · 총 {summ['total']}건")
    if summ["total"] == 0:
        out.append("  데이터 없음 (로그가 비었거나 해당 기간에 기록이 없습니다).")
        return "\n".join(out)

    bc = summ["by_category"]
    j = bc.get(JUDGMENT_LABEL, 0)
    r = bc.get(RELAY_LABEL, 0)
    b = bc.get(BLOCKED_LABEL, 0)
    u = bc.get(UNSURE_LABEL, 0)
    out.append(
        f"  실제 판단 {j}건 · 분류·전달만 {r}건 · "
        f"위임불가가능(확인필요) {b}건 · 미분류 {u}건"
    )

    out.append("")
    out.append(f"■ 자동화 1순위 후보 (분류·전달만, 자격증명 제외) Top {top}")
    if summ["relay_buckets"]:
        for name, cnt in summ["relay_buckets"].most_common(top):
            out.append(f"    {cnt:>4}  {name}")
    else:
        out.append("    (없음)")

    out.append("")
    out.append(
        f"■ 위임불가가능 (자격증명 — OTP·2FA·실제 로그인 섞임, 사람 확인 필요) Top {top}"
    )
    if summ["blocked_buckets"]:
        for name, cnt in summ["blocked_buckets"].most_common(top):
            out.append(f"    {cnt:>4}  {name}")
    else:
        out.append("    (없음)")

    out.append("")
    out.append(f"■ 미분류 (사람이 직접 봐야 함) — 버킷 {len(summ['unsure_buckets'])}종")
    if summ["unsure_buckets"]:
        for name, cnt in summ["unsure_buckets"].most_common(top):
            out.append(f"    {cnt:>4}  {name}")
        shown = summ["unsure_lines"][:top]
        if shown:
            out.append("    — 미분류 본문 예시:")
            for ln in shown:
                out.append(f"      · {ln[:100]}")
    else:
        out.append("    (없음)")
    return "\n".join(out)


def render_json(summ, days, top):
    return json.dumps(
        {
            "window_days": (0 if (days is None or days <= 0) else days),
            "total": summ["total"],
            "by_category": summ["by_category"],
            "relay_top": summ["relay_buckets"].most_common(top),
            "blocked_top": summ["blocked_buckets"].most_common(top),
            "unsure_top": summ["unsure_buckets"].most_common(top),
            "unsure_line_samples": summ["unsure_lines"][:top],
        },
        ensure_ascii=False,
        indent=2,
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="사람 개입 기록 재분류(자동화 후보 추출)")
    ap.add_argument("--log", default=DEFAULT_LOG, help="human_touch_log.jsonl 경로")
    ap.add_argument("--days", type=int, default=7, help="최근 N일 (0=전체, 기본 7)")
    ap.add_argument("--top", type=int, default=10, help="Top 목록 개수 (기본 10)")
    ap.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    entries = load_entries(args.log)
    entries = filter_days(entries, args.days)
    summ = summarize(entries)

    if args.json:
        print(render_json(summ, args.days, args.top))
    else:
        print(render_text(summ, args.days, args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
