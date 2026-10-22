#!/usr/bin/env python3
"""지원사업 공고 알림 분류(2026-10-22 마야, 공정 카드 마야#204, 사장님: 알림 교통정리).
왜: 공고 감시(bizinfo_watch.py, kstartup_watch.py)가 키워드 "AI" 하나로 시설농업 AI로봇·농업 AX랩 같은 무관한 공고를
사장님 텔레그램으로 보냈다. 결정이 필요 없는 알림은 폰으로 보내지 않는다(CLAUDE.md 7번).
규칙(고치는 법은 아래 상수만 바꾼다):
- core: 우리가 이미 지원현황에서 따라가는 이름 있는 프로그램. 지원 여부 결정이 필요할 수 있어 텔레그램으로 알린다.
- digest: 우리 업종과 닿을 수 있는 키워드. 텔레그램에는 보내지 않고 notice_digest.jsonl에 쌓아 슈퍼인박스(마야)가 읽는다.
  "AI"·"인공지능"은 혼자서는 걸리지 않고 서비스·SaaS·플랫폼 같은 말과 함께 있어야 하며, 제외어(농업·제조 등)가 있으면 버린다.
사용: classify(title) -> "core" | "digest" | None. record_digest(source, pid, title, url)."""
import json
import time
from pathlib import Path

CORE = ("창업도약", "초격차", "DIPS", "창업중심대학", "TIPS", "팁스", "스케일업")
DIGEST_STRONG = ("SaaS", "에이전트", "클라우드", "바우처")
DIGEST_WITH_CONTEXT = ("AI", "인공지능")
CONTEXT = ("서비스", "솔루션", "플랫폼", "소프트웨어", "SW", "SaaS", "데이터", "스타트업", "창업", "바우처", "에이전트", "개발")
EXCLUDE = ("농업", "농식품", "축산", "수산", "어업", "임업", "의류", "섬유", "제조", "건설", "조선", "식품", "화장품",
           "뿌리산업", "금형", "의료기기", "바이오", "로봇")
DIGEST_FILE = Path("C:/work/_ops/grants_prep/notice_digest.jsonl")


def _has(title, words):
    t = title.lower()
    return [w for w in words if w.lower() in t]


def classify(title):
    if _has(title, CORE):
        return "core"
    if _has(title, EXCLUDE):
        return None
    if _has(title, DIGEST_STRONG):
        return "digest"
    if _has(title, DIGEST_WITH_CONTEXT) and _has(title, CONTEXT):
        return "digest"
    return None


def record_digest(source, pid, title, url, path=DIGEST_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": time.strftime("%Y-%m-%d %H:%M"), "source": source, "id": pid, "title": title, "url": url}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
