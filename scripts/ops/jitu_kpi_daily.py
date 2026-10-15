#!/usr/bin/env python3
"""지투 일일 KPI 수집기(슈퍼프로세스 KPI 관리 공통 공정 ②, 2026-10-12 지투).

지투 KPI = 고객수. 퍼널(방문 → 연결 시작 → 가입 → 첫 연결 → 재호출) 숫자를 사람이 읽어 주지 않아도 쌓이게 한다.
하루 한 줄을 C:/work/_ops/jitu_po/kpi_daily.jsonl에 덧붙인다(같은 날은 덮어쓴다). 읽을 수 없는 칸은 None으로 둔다(지어내지 않는다).
  - inquiries_total / inquiries_7d: hello@ 문의 보관함(Worker, 읽기 전용, 키는 값을 출력하지 않는다)
  - visits_24h / views_24h: 탐이 적는 C:/work/_ops/jitu_po/방문_주간.md의 마지막 줄(없으면 None)
  - customers: jitu_po의 마지막 kpi 기록의 고객수(손으로 적은 값, customer_stats 연결 뒤 자동으로 바뀐다)
수동 실행: python scripts/ops/jitu_kpi_daily.py
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

OUT_DIR = os.environ.get("JITU_PO_DIR", "C:/work/_ops/jitu_po")
OUT = os.path.join(OUT_DIR, "kpi_daily.jsonl")
VISITS = os.path.join(OUT_DIR, "방문_주간.md")
MAIL_ENV = os.environ.get("CARVIT_MAIL_ENV", "C:/work/_ops/secrets/carvit_mail_read.env")


def read_env(path):
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    out[k] = v
    except OSError:
        pass
    return out


INVITE_REQ = None


def mail_counts():
    env = read_env(MAIL_ENV)
    if not env.get("MAIL_URL") or not env.get("MAIL_READ_KEY"):
        return None, None
    req = urllib.request.Request(env["MAIL_URL"].rstrip("/") + "/mail",
                                 headers={"Authorization": "Bearer " + env["MAIL_READ_KEY"], "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None, None
    items = data if isinstance(data, list) else data.get("mails") or data.get("items") or []
    # 사전체험(초대 요청)은 hello@로 오는 "[초대 요청]" 메일이다. 우리 도메인 주소는 내부 시험이라 뺀다(주소는 출력하지 않는다)
    global INVITE_REQ
    INVITE_REQ = sum(1 for m in items if "[초대 요청]" in str(m.get("subject") or "")
                     and "@simplifier.co.kr" not in str(m.get("preview") or "") and "@carvit.ai" not in str(m.get("preview") or ""))
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    recent = 0
    for m in items:
        ts = m.get("date") or m.get("received_at") or m.get("created_at")
        try:
            t = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            if t >= cutoff:
                recent += 1
        except Exception:
            continue
    return len(items), recent


def last_visits():
    try:
        with open(VISITS, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if re.search(r"\d{4}-\d{2}-\d{2}", l)]
    except OSError:
        return None, None
    if not lines:
        return None, None
    cells = [c.strip() for c in lines[-1].split("|")]
    nums = [int(c) for c in cells[2:] if c.isdigit()]
    if len(nums) >= 2:
        return nums[0], nums[1]
    return None, None


def last_customers():
    p = os.path.join(OUT_DIR, "kpi.jsonl")
    try:
        with open(p, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
    except OSError:
        return None
    for r in reversed(rows):
        if r.get("customers") is not None:
            return r["customers"]
    return None


def main():
    today = dt.date.today().isoformat()
    total, recent = mail_counts()
    views, visits = last_visits()
    row = {"date": today, "inquiries_total": total, "inquiries_7d": recent,
           "views_24h": views, "visits_24h": visits, "customers": last_customers(),
           "invite_requests_ext": INVITE_REQ}
    rows = []
    try:
        with open(OUT, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
    except OSError:
        pass
    rows = [r for r in rows if r.get("date") != today] + [row]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
