#!/usr/bin/env python3
"""Vertex 제미나이로 비티 질문을 받는 경로(2026-10-03 탐, 대장 N120).

왜: 비티(안티그래비티)가 주간 한도로 막혀도 검토를 이어가려고. 개인 GCP 결제 계정 010823의 무료 체험 크레딧을 쓴다
    (사장님 10/3: 무료 키 먼저, 막히면 GCP 크레딧. 카빗 계정 크레딧은 건드리지 않는다).
인증: gcloud 토큰(hansunghee7 계정). 키 값 없음. 질문 파일에는 고객 정보·비밀값·가격·전략을 넣지 않는다.
관문(코드로 강제): 하루 호출 수 상한(DAY_CALLS)·하루 추정 비용 상한(DAY_KRW)·몫별 상한(WHO_KRW, 검색 SEARCH_KRW)을 넘으면 멈춘다(종료 코드 3).
기록: C:/work/_ops/vertex_usage.csv (호출마다 토큰·검색 횟수·추정 비용). 추정 단가는 실측 전 값이라
      PRICE_* 환경변수로 고치고, 실제 비용은 결제 보고서(프로젝트별)로 대조한다.

사용: python scripts/ops/ask_vertex.py <질문파일> [출력파일] [--search] [--who 탐] [--model gemini-3.6-flash]
종료 코드: 0 성공 / 2 호출 실패 / 3 하루 상한 초과
"""
import argparse, csv, json, os, shutil, subprocess, sys, urllib.error, urllib.request
from datetime import datetime
from pathlib import Path

PROJECT = "project-e59cbc25-e96a-44f5-ac6"  # My First Project(개인 계정, 무료 체험 크레딧)
REGION = "global"  # vertex_research.py와 같은 경로(gemini-3.6-flash는 global에서 200, 9/26 실측)
ACCOUNT = "hansunghee7@gmail.com"
LOG = Path("C:/work/_ops/vertex_usage.csv")
DAY_CALLS = int(os.environ.get("VERTEX_DAY_CALLS", "100000"))  # 사장님 10/5: 호출 수 상한은 사실상 없앤다(전체 금액의 일 상한만 건다)
DAY_KRW = float(os.environ.get("VERTEX_DAY_KRW", "4100"))  # 사장님 10/5: 잔액 ₩326,145 전부를 12/23 만료까지 쓰는 일 상한(÷78일). 추정 단가가 실측 전이라 아래 누적 상한도 같이 건다
TOTAL_KRW = float(os.environ.get("VERTEX_TOTAL_KRW", "277000"))  # 10/5부터 누적 추정 비용 상한(잔액의 85%). 추정이 실제보다 낮게 나올 위험에 대한 안전판, 결제 화면 대조(대장 N160) 뒤에 조정
# 몫별 하루 상한(원, 사장님 승인 10/4, 대장 N120): 합계 DAY_KRW와 함께 코드로 강제한다. who가 목록에 없으면 예비 몫.
WHO_KRW = {}  # 사장님 10/5: 사람별 몫 상한을 없앴다(모두가 최대한 쓰고 전체 일 상한만 건다). 예전 값: 지투·비티 500, 타미 300, 헤르메스 1000
RESERVE_KRW = float("inf")
SEARCH_KRW = float("inf")  # 검색 몫 상한도 없앰
# 추정 단가(원, 백만 토큰당·검색 1건당). [추정] 실측 전 값. 결제 보고서와 대조해 고친다.
PRICE_IN = float(os.environ.get("PRICE_IN_KRW_PER_M", "450"))
PRICE_OUT = float(os.environ.get("PRICE_OUT_KRW_PER_M", "3500"))
PRICE_SEARCH = float(os.environ.get("PRICE_SEARCH_KRW", "50"))
HEAD = "time,who,model,search,in_tok,out_tok,search_q,est_krw,sec,rc"


def token():
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    return subprocess.run([exe, "auth", "print-access-token", f"--account={ACCOUNT}"], capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60).stdout.strip()


def bucket(who):
    return who if who in WHO_KRW else "예비"


def today_use(who=None):
    """오늘 전체 호출 수·비용, 그리고 who 몫·검색 몫의 비용 합을 돌려준다."""
    if not LOG.exists():
        return 0, 0.0, 0.0, 0.0
    d = datetime.now().strftime("%Y-%m-%d")
    n, krw, mine, srch = 0, 0.0, 0.0, 0.0
    for r in csv.DictReader(LOG.open(encoding="utf-8")):
        if r["time"].startswith(d):
            n += 1
            c = float(r["est_krw"] or 0)
            krw += c
            if who is not None and bucket(r["who"]) == bucket(who):
                mine += c
            if r["search"] == "1":
                srch += c
    return n, krw, mine, srch


def total_since(start="2026-10-05"):
    """10/5부터 누적 추정 비용(원)."""
    if not LOG.exists():
        return 0.0
    return sum(float(r["est_krw"] or 0) for r in csv.DictReader(LOG.open(encoding="utf-8")) if r["time"][:10] >= start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("q")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--search", action="store_true", help="구글 검색 연동(호출당 추가 비용 가능성, 실측 대상)")
    ap.add_argument("--who", default="탐")
    ap.add_argument("--model", default="gemini-3.6-flash")
    a = ap.parse_args()
    out = Path(a.out) if a.out else Path(f"C:/work/_ops/bt/replies/vertex_{datetime.now():%Y%m%d_%H%M}.md")
    n, krw, mine, srch = today_use(a.who)
    cap = WHO_KRW.get(a.who, RESERVE_KRW)
    if mine >= cap:
        print(f"{a.who if a.who in WHO_KRW else '예비'} 몫 상한 초과: 오늘 약 ₩{mine:,.0f} (상한 ₩{cap:,.0f}).", file=sys.stderr)
        return 3
    if a.search and srch >= SEARCH_KRW:
        print(f"검색 몫 상한 초과: 오늘 약 ₩{srch:,.0f} (상한 ₩{SEARCH_KRW:,.0f}).", file=sys.stderr)
        return 3
    tot = total_since()
    if tot >= TOTAL_KRW:
        print(f"누적 상한 초과: 10/5부터 약 ₩{tot:,.0f} (상한 ₩{TOTAL_KRW:,.0f}). 결제 화면 대조 뒤 탐이 조정.", file=sys.stderr)
        return 3
    if n >= DAY_CALLS or krw >= DAY_KRW:
        print(f"하루 상한 초과: 오늘 {n}회·약 ₩{krw:,.0f} (상한 {DAY_CALLS}회·₩{DAY_KRW:,.0f}). 내일 다시 또는 상한 환경변수 조정은 탐이 판단.", file=sys.stderr)
        return 3
    prompt = Path(a.q).read_text(encoding="utf-8")
    url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/{a.model}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if a.search:
        body["tools"] = [{"googleSearch": {}}]
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    t0 = datetime.now()
    rc, text, usage, sq = 0, "", {}, 0
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=300).read())
        cand = (r.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        usage = r.get("usageMetadata", {})
        sq = len((cand.get("groundingMetadata") or {}).get("webSearchQueries", []))
    except urllib.error.HTTPError as e:
        rc = 2
        text = f"[호출 실패 HTTP {e.code}] {e.read().decode('utf-8', 'replace')[:500]}"
    except Exception as e:  # 네트워크·토큰 오류
        rc = 2
        text = f"[호출 실패 {type(e).__name__}] {e}"
    sec = int((datetime.now() - t0).total_seconds())
    tin, tout = int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    est = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT + sq * PRICE_SEARCH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with LOG.open("a", encoding="utf-8", newline="") as f:
        if new:
            f.write(HEAD + "\n")
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S},{a.who},{a.model},{int(a.search)},{tin},{tout},{sq},{est:.2f},{sec},{rc}\n")
    print(f"답 저장: {out} ({len(text)}자) 토큰 입력 {tin}·출력 {tout}·검색 {sq}건·추정 약 ₩{est:,.1f}·{sec}초", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
