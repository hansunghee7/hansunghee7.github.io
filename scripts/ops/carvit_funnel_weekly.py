"""Carvit 퍼널 주간 집계 (mcp.carvit.ai Cloud Run 요청 로그, 읽기 전용).

목적: 방문 -> 연결 시작 -> 가입 -> 첫 연결 퍼널의 기준선을 만든다.
      /login?next=connect, /connect, /access 요청 수를 일 단위·주 단위로 센다.
      지투(제품 책임)가 주간 KPI 루프에서 weekly.md 를 읽는다.

읽기 전용: `gcloud logging read` 만 쓴다. 설정 변경(config set)·로그 쓰기 없음.
개인정보: 쿼리 문자열은 허용 목록 키(next=connect)만 남기고 버린다.
          IP·사용자 식별 정보는 읽지도 저장하지도 않는다. 봇/헬스체크는 별도 열로 제외한다.

사용: python scripts/ops/carvit_funnel_weekly.py --days 7
출력: C:/work/_ops/carvit_funnel/daily.csv, C:/work/_ops/carvit_funnel/weekly.md
종료 코드: 0 성공, 2 로그 읽기 실패(인증 만료·권한 등)
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

ACCOUNT = "simon@simplifier.co.kr"
PROJECT = "saegim-mcp"
OUT_DIR = Path("C:/work/_ops/carvit_funnel")
CATEGORIES = ["login_next_connect", "connect", "access"]
BOT_RE = re.compile(r"bot|crawl|spider|uptime|health|monitor|probe|curl|python-requests|go-http", re.I)
ALLOWED_QUERY = {"next": {"connect"}}  # 키 -> 허용 값


def mask_query(query):
    """허용 목록 키=값만 남긴다. 나머지는 버린다."""
    kept = [f"{k}={v}" for k, v in parse_qsl(query, keep_blank_values=True)
            if k in ALLOWED_QUERY and v in ALLOWED_QUERY[k]]
    return "&".join(kept)


def classify(url):
    """URL -> (구분 or None, 마스킹된 쿼리). 기타는 None."""
    parts = urlsplit(url or "")
    path = parts.path.rstrip("/") or "/"
    q = mask_query(parts.query)
    if path == "/login":
        return ("login_next_connect" if q == "next=connect" else None), q
    if path == "/connect":
        return "connect", q
    if path == "/access":
        return "access", q
    return None, q


def is_bot(user_agent):
    return not user_agent or bool(BOT_RE.search(user_agent))


def fetch_logs(days):
    """gcloud logging read (읽기 전용). 필요한 필드만 뽑는다. 실패 시 RuntimeError."""
    flt = ('resource.type="cloud_run_revision" AND httpRequest.requestUrl:* AND '
           '(httpRequest.requestUrl:"/login" OR httpRequest.requestUrl:"/connect" '
           'OR httpRequest.requestUrl:"/access")')
    cmd = [shutil.which("gcloud") or "gcloud.cmd", f"--account={ACCOUNT}", f"--project={PROJECT}", "logging", "read", flt,
           f"--freshness={days}d", "--limit=100000", "--format=json(timestamp,httpRequest.requestUrl,httpRequest.userAgent)"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[0] if r.stderr.strip() else "gcloud 실패")
    return json.loads(r.stdout or "[]")


def aggregate(entries):
    """로그 -> {(날짜, 구분): [전체, 봇 제외]} (KST 기준 날짜)."""
    kst = timezone(timedelta(hours=9))
    agg = defaultdict(lambda: [0, 0])
    for e in entries:
        hr = e.get("httpRequest") or {}
        cat, _ = classify(hr.get("requestUrl"))
        if not cat:
            continue
        ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone(kst)
        cell = agg[(ts.date().isoformat(), cat)]
        cell[0] += 1
        if not is_bot(hr.get("userAgent")):
            cell[1] += 1
    return agg


def write_daily(agg, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["날짜", "경로구분", "요청수", "봇제외요청수"])
        for (d, c) in sorted(agg):
            w.writerow([d, c, agg[(d, c)][0], agg[(d, c)][1]])


def window_sum(agg, start, end):
    """[start, end) 날짜 구간 합계 {구분: [전체, 봇제외]}"""
    s = {c: [0, 0] for c in CATEGORIES}
    for (d, c), v in agg.items():
        if start <= d < end:
            s[c][0] += v[0]
            s[c][1] += v[1]
    return s


def write_weekly(agg, today, days_seen, path):
    d = datetime.fromisoformat(today).date()
    this_s, prev_s, end = (d - timedelta(days=7)).isoformat(), (d - timedelta(days=14)).isoformat(), d.isoformat()
    cur = window_sum(agg, this_s, end)
    prev = window_sum(agg, prev_s, this_s)
    lines = [f"# Carvit 퍼널 주간 ({this_s} ~ {(d - timedelta(days=1)).isoformat()}, KST)", "",
             "- 구분별 요청 수 (괄호는 봇 제외, 전주 대비는 봇 제외 기준)"]
    for c in CATEGORIES:
        diff = cur[c][1] - prev[c][1]
        lines.append(f"- {c}: {cur[c][0]} ({cur[c][1]}), 전주 {prev[c][0]} ({prev[c][1]}), 증감 {diff:+d}")
    lines += ["", "## 한계",
              f"- 로그에서 확인된 날짜 수: {days_seen}일. 7일 미만이면 로그 보존 기간 때문에 있는 만큼만 집계했고, 전주 값은 비어 있을 수 있다.",
              "- 요청 수이지 사람 수가 아니다(같은 사람의 새로고침·재시도 포함). 가입·첫 연결은 이 로그로 알 수 없다.",
              "- 봇 판정은 userAgent 문자열 기준이라 완전하지 않다. IP·사용자 식별 정보는 저장하지 않는다."]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # 전주 대비를 위해 2배 기간을 읽는다
        entries = fetch_logs(a.days * 2)
    except Exception as ex:
        print(f"로그 읽기 실패: {ex}", file=sys.stderr)
        return 2
    agg = aggregate(entries)
    write_daily(agg, OUT_DIR / "daily.csv")
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    write_weekly(agg, today, len({d for d, _ in agg}), OUT_DIR / "weekly.md")
    print(f"완료: 로그 {len(entries)}건, 집계 {sum(v[0] for v in agg.values())}건 -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
