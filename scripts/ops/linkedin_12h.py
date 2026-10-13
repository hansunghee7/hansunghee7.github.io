# -*- coding: utf-8 -*-
"""링크드인 게시 후 12시간 전용 읽기: 순수 함수 모음(시험 대상). 설계서 C:/work/_ops/linkedin_collect/design.md 추천 A, 사장님 승인 2026-10-13.
왜: 정기 읽기가 하루 1번(21:05)이라 글마다 12시간 값이 12~22시간 사이로 흔들린다. 게시 시각은 화면('4일')이 아니라 예약 장부에서 가져온다.
이 파일은 링크드인에 접속하지 않는다. 접속은 기존 read_maya_linkedin.py 가 한다(읽기 로직 불변).
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
WINDOW_MIN = 60          # 12시간 시점 이후 이 안에 읽는다
JITTER_MIN = 15          # 읽는 시각 흔들기 범위(±)
MAX_READS_PER_DAY = 2    # 하루 읽기 상한(설계서: 정기 1 + 12시간 전용 1)
FAIL_DAYS_TO_PAUSE = 2   # 연속 실패 일수
PAUSE_DAYS = 3
REGULAR_HM = (21, 5)     # 정기 읽기 시각(구PC cron). 창과 겹치면 정기 읽기가 갈음한다
BLOCK_MARKERS = ("로그인", "authwall", "login", "현재 활동 없음", "보안 확인", "captcha", "checkpoint", "3개 미만")


def published_at(p):
    """장부 글의 게시 시각. published_at 우선, 없으면 planned 날짜 09:00 KST(maya_measure_due.due_at 과 같은 기준)."""
    if p.get("published_at"):
        return datetime.fromisoformat(p["published_at"]).astimezone(KST)
    return datetime.fromisoformat(p["planned"]).replace(hour=9, minute=0, tzinfo=KST)


def jitter_minutes(post_id, date_key=""):
    """글마다 고정된 -15..+15분 흔들림(같은 글은 크론이 여러 번 돌아도 같은 시각을 낸다)."""
    h = int(hashlib.sha256(f"{post_id}|{date_key}".encode()).hexdigest()[:8], 16)
    return (h % (2 * JITTER_MIN * 60 + 1)) / 60.0 - JITTER_MIN


def scheduled_read_time(p):
    """12시간 시점 + 창 중앙(30분) + 흔들림 -> 창 [target, target+60분] 안의 읽기 시각."""
    target = published_at(p) + timedelta(hours=12)
    return target + timedelta(minutes=WINDOW_MIN / 2 + jitter_minutes(p["post"], target.strftime("%Y%m%d")))


def overlaps_regular(t):
    reg = t.replace(hour=REGULAR_HM[0], minute=REGULAR_HM[1], second=0, microsecond=0)
    return abs((t - reg).total_seconds()) <= WINDOW_MIN * 60 / 2


def read_schedule(posts):
    """12시간 전용 읽기가 필요한 시각 목록: [(post, target, read_at, covered_by_regular)]. 취소 글·이미 12h 값이 있는 글은 제외."""
    out = []
    for p in posts:
        if p.get("status") == "cancelled" or (p.get("snaps") or {}).get("12h"):
            continue
        target = published_at(p) + timedelta(hours=12)
        at = scheduled_read_time(p)
        out.append((p["post"], target, at, overlaps_regular(at)))
    return sorted(out, key=lambda r: r[2])


def is_block_text(text):
    t = (text or "").lower()
    return any(m.lower() in t for m in BLOCK_MARKERS)


def decide(now, posts, state):
    """지금 읽어야 하나. (post 또는 None, 사유). state: {reads:{YYYY-MM-DD:[post..]}, blocked_date, fail_days:[날짜..], pause_until, done:[post..]}"""
    today = now.strftime("%Y-%m-%d")
    if state.get("pause_until") and now < datetime.fromisoformat(state["pause_until"]):
        return None, "쉬는 중(연속 실패)"
    if state.get("blocked_date") == today:
        return None, "오늘 차단 신호로 중지(같은 날 재시도 금지)"
    if len(state.get("reads", {}).get(today, [])) >= MAX_READS_PER_DAY:
        return None, "하루 상한"
    for post, target, at, covered in read_schedule(posts):
        if post in state.get("done", []):
            continue
        if at <= now <= target + timedelta(minutes=WINDOW_MIN):
            if covered:
                return None, f"{post}: 정기 읽기(21:05)가 갈음"
            return post, f"{post}: 12시간 창 안"
    return None, "읽을 글 없음"


def record_result(state, now, post, ok, blocked):
    """읽기 결과를 state 에 반영한다. 반환: 연속 실패로 쉬기 시작했는지."""
    today = now.strftime("%Y-%m-%d")
    state.setdefault("reads", {}).setdefault(today, []).append(post)
    if ok:
        state.setdefault("done", []).append(post)
        state["fail_days"] = []
        return False
    if blocked:
        state["blocked_date"] = today
    fd = state.setdefault("fail_days", [])
    if today not in fd:
        fd.append(today)
    d = sorted(datetime.strptime(x, "%Y-%m-%d") for x in fd)
    if len(d) >= FAIL_DAYS_TO_PAUSE and (d[-1] - d[-2]).days == 1:
        state["pause_until"] = (now + timedelta(days=PAUSE_DAYS)).isoformat(timespec="minutes")
        state["fail_days"] = []
        return True
    return False


# ---- 스냅샷 장부(jsonl)와 보간 ----
def snapshot_lines(read_rec, source):
    """읽기 결과를 글마다 한 줄 dict 로 바꾼다. tail 은 화면 형식이 바뀌어도 사후 재해석하도록 있으면 계속 남긴다."""
    at = datetime.strptime(read_rec["fetched_at_kst"], "%Y-%m-%d %H:%M").replace(tzinfo=KST).isoformat(timespec="minutes")
    return [{"at": at, "title": p.get("head") or p.get("title"), "age": p.get("age"), "likes": p.get("reactions", p.get("likes")),
             "impressions": p.get("impressions"), "extra_counts": p.get("extra_counts"), "tail": p.get("tail"), "source": source}
            for p in read_rec.get("posts", [])]


def append_snapshots(path, lines):
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for l in lines:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")


def load_snapshots(path):
    out = []
    try:
        for l in Path(path).read_text(encoding="utf-8").splitlines():
            if l.strip():
                out.append(json.loads(l))
    except FileNotFoundError:
        pass
    return out


def interpolate_at(snaps, title, target, tol_min=60):
    """target 시점 값. 창(target~+tol) 안에 실측이 있으면 그대로(보간 아님),
    없고 앞뒤 스냅샷이 있으면 선형 보간하며 interpolated=True 로 표기. 앞 또는 뒤가 없으면 None(값을 지어내지 않는다)."""
    key = (title or "")[:10]
    rows = []
    for s in snaps:
        if key and key in (s.get("title") or "") and s.get("likes") is not None and s.get("impressions") is not None:
            rows.append((datetime.fromisoformat(s["at"]).astimezone(KST), s))
    rows.sort(key=lambda r: r[0])
    for at, s in rows:
        if target <= at <= target + timedelta(minutes=tol_min):
            return {"likes": s["likes"], "impressions": s["impressions"], "at": at.isoformat(timespec="minutes"), "interpolated": False}
    before = [r for r in rows if r[0] < target]
    after = [r for r in rows if r[0] > target + timedelta(minutes=tol_min)]
    if not before or not after:
        return None
    (t0, a), (t1, b) = before[-1], after[0]
    f = (target - t0).total_seconds() / (t1 - t0).total_seconds()

    def lerp(x, y):
        return round(x + (y - x) * f)
    return {"likes": lerp(a["likes"], b["likes"]), "impressions": lerp(a["impressions"], b["impressions"]),
            "at": target.isoformat(timespec="minutes"), "interpolated": True,
            "note": f"보간({t0.strftime('%m-%d %H:%M')}~{t1.strftime('%m-%d %H:%M')} 스냅샷 선형)"}
