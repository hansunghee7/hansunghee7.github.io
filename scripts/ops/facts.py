#!/usr/bin/env python3
"""회사 자격 사실표(지원사업 자격 게이트용, 2026-10-14 탐, 사장님 지시: "정보 수집하고 DB테이블로 정리").

저장: 운영 DB tasks 표의 section='fact' 행(grants.py와 같은 방식, 새 표 없음, DDL 승인 불필요).
열 대응: no=F번호 · title=항목 · owner=게이트 분류 · status=확인됨|불일치|미확인 · result=값 · evidence=출처 · source_date=확인일 · next_action=다음 할 일
값 규칙: 화면·서류에서 직접 읽은 값만 '확인됨'. 못 읽었으면 '미확인'. 서류끼리 다르면 '불일치'. 비밀값(번호·키)은 거부한다.

사용:
  python scripts/ops/facts.py list [--md]
  python scripts/ops/facts.py set F03 --status 확인됨 --result "..." --src "인터넷등기소 열람" [--next "..."]
  python scripts/ops/facts.py seed        기본 항목 11개를 한 번 만든다(이미 있으면 건너뜀)
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
import opsdb  # noqa: E402

COLS = ("owner", "section", "no", "title", "status", "source_date", "next_action", "evidence", "result", "cost", "decider", "raw", "source")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z]{20,}|xox[bap]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|\b\d{6}-?\d{7}\b|\b\d{3}-\d{2}-\d{5}\b)")
STATUSES = ("확인됨", "불일치", "미확인")


def today():
    return time.strftime("%Y-%m-%d")


def clean(*texts):
    for t in texts:
        if t and SECRET.search(str(t)):
            sys.exit("비밀값·주민/사업자/법인등록번호 모양이 들어 있어 거부했습니다(번호는 기록에 쓰지 않습니다)")


def cell(s, n=50):
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def all_rows():
    return opsdb.select("tasks", "*", where={"section": "eq.fact"}, order="no.asc", limit=500)


def next_no(rows):
    n = [int(m.group(1)) for r in rows if (m := re.match(r"F(\d+)$", r.get("no") or ""))]
    return f"F{(max(n) + 1) if n else 1:02d}"


def mk(no, gate, title, status, result, src, nxt):
    r = {c: None for c in COLS}
    r.update(owner=gate, section="fact", no=no, title=title, status=status, source_date=today(), next_action=nxt, evidence=src, result=result, decider="사장님", raw="{}", source="facts.py")
    return r


SEED = [
    ("업력", "업력", "확인됨", "개업연월일 2023-04-24, 오늘 기준 약 3년 5개월", "사업자등록증(드라이브)", "초기창업패키지(3년 이내)는 제외, 7년 이내 사업은 해당"),
    ("법인 설립일", "업력", "미확인", "정관 제정 2023-04-18(등기 설립일은 아직 못 봄)", "개정정관(드라이브)", "법인 등기부 열람(유료)이나 사장님이 가진 등기부등본으로 확인"),
    ("소재지", "소재지", "불일치", "사업자등록증은 서울 강남구, 정관 제3조 본점은 성남시", "사업자등록증·정관(드라이브)", "법인 등기부의 본점 소재지가 정본, 서울·경기 지원사업 자격에 직결"),
    ("사업자 상태", "세무", "확인됨", "부가가치세 일반과세자, 계속사업자", "홈택스 사업자 상태 조회(2026-10-14)", "없음"),
    ("체납 여부", "세무", "미확인", "납세증명서로 확인해야 함", "홈택스 증명 발급 필요", "발급 신청은 양식 제출이라 사장님 허락 후"),
    ("중소기업 확인", "기업 확인", "미확인", "SMINFO가 내 브라우저 탭에서 로그인 상태가 아니라 못 읽음", "sminfo.mss.go.kr", "사장님이 로그인한 같은 탭 그룹으로 옮기거나, 확인서 PDF를 드라이브에 둠"),
    ("벤처기업 확인", "기업 확인", "미확인", "벤처인도 내 탭에서 비로그인", "smes.go.kr/venturein", "위와 같음"),
    ("창업기업 확인", "기업 확인", "미확인", "startup.go.kr 접속 오류(chrome-error)", "startup.go.kr", "주소·접속 재시도, 막히면 사장님 화면 값"),
    ("부채비율·자본잠식", "재무", "미확인", "표준재무제표증명이 필요함", "홈택스 증명 발급 필요", "발급 신청 허락 후, 못 받으면 결산서"),
    ("매출·근로자 수", "재무", "미확인", "부가세 과세표준증명·4대보험 가입자 수 필요", "홈택스·사회보험 EDI", "허락 후 조회"),
    ("자기부담 재원", "재원", "미확인", "사장님 결정 사항(제품·방향)", "사장님", "사장님이 정할 금액·방식"),
]


def cmd_list(a):
    rs = all_rows()
    if not rs:
        print("(자격 사실표가 비어 있습니다)")
        return
    print(f"## 회사 자격 사실표 ({today()} 기준, {len(rs)}건)\n")
    print("| 번호 | 분류 | 항목 | 상태 | 값 | 출처 | 다음 할 일 |")
    print("|---|---|---|---|---|---|---|")
    for r in rs:
        print(f"| {r['no']} | {r['owner']} | {cell(r['title'], 20)} | {r['status']} | {cell(r['result'], 50)} | {cell(r['evidence'], 30)} | {cell(r['next_action'], 40)} |")
    c = {}
    for r in rs:
        c[r["status"]] = c.get(r["status"], 0) + 1
    print("\n상태별: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))


def cmd_set(a):
    rs = opsdb.select("tasks", "*", where={"section": "eq.fact", "no": f"eq.{a.no}"}, limit=1)
    if not rs:
        sys.exit(f"{a.no} 를 찾지 못했습니다")
    clean(a.result, a.src, a.next)
    vals = {"source_date": today()}
    if a.status:
        if a.status not in STATUSES:
            sys.exit(f"상태는 {STATUSES} 중 하나")
        vals["status"] = a.status
    if a.result is not None:
        vals["result"] = a.result
    if a.src is not None:
        vals["evidence"] = a.src
    if a.next is not None:
        vals["next_action"] = a.next
    opsdb.patch("tasks", {"section": "eq.fact", "no": f"eq.{a.no}"}, vals)
    print(f"갱신: {a.no}")


def cmd_seed(a):
    rs = all_rows()
    have = {(r["title"] or "").strip() for r in rs}
    new = []
    for title, gate, st, res, src, nxt in SEED:
        if title in have:
            continue
        clean(res, src, nxt)
        new.append(mk(f"F{len(rs) + len(new) + 1:02d}", gate, title, st, res, src, nxt))
    if not new:
        print("옮길 새 행이 없습니다")
        return
    opsdb.insert("tasks", new)
    print(f"{len(new)}건 만듦")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--md", action="store_true"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("set"); s.add_argument("no")
    for k in ("status", "result", "src", "next"):
        s.add_argument("--" + k)
    s.set_defaults(f=cmd_set)
    s = sub.add_parser("seed"); s.set_defaults(f=cmd_seed)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
