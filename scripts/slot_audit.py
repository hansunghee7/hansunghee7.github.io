"""발행 슬롯 감사: 월·수·금 홈페이지 글과 화·목 SNS 등록이 비었는지 표 한 장으로 보인다.

원칙(사장님 2026-09-29): 한 주 전 토요일에 다음 주 월·수·금 글 3편을 만들어 예약하고,
월·수 글은 화·목에 SNS로 예약한다. 이 스크립트는 그 원칙을 어기면(슬롯이 비면) 종료코드 1과
빈 슬롯 목록을 낸다. 읽기 전용이라 아무것도 등록하지 않는다.

기준(정본은 저장소 파일):
- 홈페이지: log_assets/markdown/*.md 의 date(KST)가 그 날이고 published 또는 scheduled 가 켜진 글
- SNS: assets/data/sns_publish_queue.json 에서 publishAt(KST)이 그 날이고 status 가 cancelled/error 가
  아닌 항목. 채널별로 본다(SNS_CHANNELS).
- 예약 불가 채널(MANUAL_CHANNELS)은 당일 세션이 수동으로 올리므로 "오늘 수동 대상"으로 따로 낸다.

사용법: python scripts/slot_audit.py [--days 14] [--today 2026-09-29]
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
HOME_DOW = {0, 2, 4}  # 월 수 금
SNS_DOW = {1, 3}  # 화 목
SNS_CHANNELS = ["linkedin", "facebook", "instagram"]
MANUAL_CHANNELS = ["로켓펀치", "리멤버 커넥트"]
DOW_KO = "월화수목금토일"


def front_matter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            if k and not line.startswith(" "):
                meta[k.strip()] = v.strip().strip("\"'")
    return meta


def home_posts(root):
    posts = {}
    for p in sorted((root / "log_assets/markdown").glob("*.md")):
        meta = front_matter(p)
        raw = meta.get("date", "")
        try:
            d = datetime.fromisoformat(raw).astimezone(KST).date()
        except ValueError:
            continue
        live = meta.get("published") == "true" or meta.get("scheduled") == "true"
        if live:
            posts.setdefault(d, []).append(meta.get("title", p.name))
    return posts


def draft_dates(root):
    """status가 draft인 큐 항목의 게시일(KST) 집합(승인 전 초안)."""
    q = json.loads((root / "assets/data/sns_publish_queue.json").read_text(encoding="utf-8"))
    out = set()
    for it in q:
        if it.get("status") == "draft":
            try:
                out.add(datetime.fromisoformat(it["publishAt"].replace("Z", "+00:00")).astimezone(KST).date())
            except (KeyError, ValueError):
                pass
    return out


def sns_items(root):
    items = {}
    q = json.loads((root / "assets/data/sns_publish_queue.json").read_text(encoding="utf-8"))
    for it in q:
        if it.get("status") not in ("registered", "pending"):  # draft(승인 전)·cancelled·error는 등록으로 세지 않는다
            continue
        try:
            d = datetime.fromisoformat(it["publishAt"].replace("Z", "+00:00")).astimezone(KST).date()
        except (KeyError, ValueError):
            continue
        items.setdefault(d, set()).add(it["platform"])
    return items


def main():
    try:  # 윈도우 기본 인코딩(cp949)에서 이모지·한글 출력이 깨지지 않게(훅에서 파이프로 받을 때)
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--today", default=None)
    ap.add_argument("--brief", action="store_true", help="한 줄 요약만(세션 시작 훅용)")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    today = date.fromisoformat(args.today) if args.today else datetime.now(KST).date()
    homes, sns, drafts = home_posts(root), sns_items(root), draft_dates(root)
    rows, gaps = [], []  # gaps: (날짜, 종류, 설명, 제안)
    for i in range(-1, args.days + 1):
        d = today + timedelta(days=i)
        dow = d.weekday()
        if dow in HOME_DOW:
            titles = homes.get(d)
            rows.append(f"  {d} {DOW_KO[dow]} 홈페이지 : " + ("OK " + " / ".join(titles) if titles else "비어 있음"))
            if not titles:
                gaps.append((d, "home", f"{d}({DOW_KO[dow]}) 홈페이지 글 없음",
                             "주제 후보를 뽑아 컨펌 ①부터 시작"))
        elif dow in SNS_DOW:
            have = sns.get(d, set())
            miss = [c for c in SNS_CHANNELS if c not in have]
            rows.append(f"  {d} {DOW_KO[dow]} SNS    : " + ("OK " + ", ".join(sorted(have)) if not miss else f"미등록 {', '.join(miss)}"))
            if miss:
                src = d - timedelta(days=1)  # 화·목 SNS의 원본은 전날(월·수) 홈페이지 글
                if d in drafts:
                    prop = "초안이 있음: 사장님 승인만 받으면 등록"
                elif src in homes:
                    prop = f"원본({src} 「{homes[src][0]}」)이 있음: 초안 생성 후 승인 요청"
                else:
                    prop = f"원본 글({src} 홈페이지)이 아직 없음: 그 글을 먼저 채워야 함"
                gaps.append((d, "sns", f"{d}({DOW_KO[dow]}) SNS 미등록 채널: {', '.join(miss)}", prop))
    next_mon = today + timedelta(days=7 - today.weekday())
    missing_week = [str(next_mon + timedelta(days=k)) for k in (0, 2, 4) if (next_mon + timedelta(days=k)) not in homes]
    future = sorted(g for g in gaps if g[0] >= today)  # 지난 슬롯은 참고만
    if args.brief:
        if not gaps:
            print("📅 발행 슬롯 감사: 빈 슬롯 없음")
        else:
            nh = sum(1 for g in future if g[1] == "home")
            ns = sum(1 for g in future if g[1] == "sns")
            print(f"📅 발행 슬롯 감사: 앞으로 빈 슬롯 {len(future)}개(홈페이지 {nh}, SNS {ns}). 마야 세션이면 첫 보고 전에 `python scripts/slot_audit.py`를 돌려 사장님께 제안할 것을 정한다.")
        return
    print(f"발행 슬롯 감사 (기준일 {today}, 앞으로 {args.days}일, 어제부터 봄)")
    print(chr(10).join(rows))
    print(f"  수동 채널(예약 불가, 당일 세션이 올림): {', '.join(MANUAL_CHANNELS)}")
    print(f"  다음 주({next_mon}~) 월·수·금 홈페이지: " + ("3편 모두 예약됨" if not missing_week else f"빠짐 {', '.join(missing_week)}"))
    if not gaps:
        print(chr(10) + "빈 슬롯 없음")
        return
    print(chr(10) + "빈 슬롯:")
    for g in sorted(gaps):
        print("  -", g[2], "<-", g[3])
    if future:
        top = future[0]
        print(chr(10) + f"오늘 사장님께 제안할 첫 번째(가장 가까운 슬롯): {top[2]}. {top[3]}.")
    sys.exit(1)


if __name__ == "__main__":
    main()
