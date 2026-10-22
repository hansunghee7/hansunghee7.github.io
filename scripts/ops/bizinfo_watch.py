#!/usr/bin/env python3
"""기업마당(bizinfo) 지원사업 공고 감시(2026-10-15 탐, 공정 카드 탐-공고수집 #2의 출처 두 번째, 사장님: 타미 전담·오케스트레이션 2.0).
kstartup_watch.py와 같은 방식: 목록 페이지에서 새 공고를 찾아 상태 파일에 기록하고, 관심 키워드 공고는 텔레그램으로 알린다.
첫 실행은 기준선만 저장하고 알리지 않는다. 읽기 전용, 30초 타임아웃, 사람 빈도(하루 2회). 종료 코드 1 = 목록을 못 읽음(파싱 0건).
판정은 하지 않는다(새 공고 찾기와 키워드 일치 표시까지). 자격 판단은 별도 단계(탐-공고수집 #3~#4)."""
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
URL = "https://www.bizinfo.go.kr/sii/siia/selectSIIA200View.do"
DETAIL = "https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId="
STATE = Path("C:/work/_ops/grants_prep/biz_seen.json")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
from notice_filter import classify, record_digest  # noqa: E402  분류 규칙은 notice_filter.py 한 곳에서 고친다


def parse(raw):
    """HTML에서 (공고번호, 제목) 목록을 뽑는다. 링크 title 속성에 제목이 들어 있다."""
    out = {}
    for m in re.finditer(r'pblancId=(PBLN_\d+)"\s+title="([^"]*)"', raw):
        out.setdefault(m.group(1), html.unescape(m.group(2)).strip())
    return list(out.items())


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def main():
    items = parse(fetch())
    if not items:
        print("목록 파싱 0건: 페이지 구조가 바뀌었을 수 있음")
        return 1
    old = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    cur = {k: v for k, v in items}
    if old is None:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"seen": cur, "at": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False), encoding="utf-8")
        print(f"기준선 저장 {len(cur)}건(알림 없음)")
        return 0
    new = {k: v for k, v in cur.items() if k not in old["seen"]}
    old["seen"].update(cur)
    old["at"] = time.strftime("%Y-%m-%d %H:%M")
    STATE.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    print(f"새 공고 {len(new)}건")
    hot = []
    for k, v in new.items():
        tier = classify(v)
        print(f"- {k} {v}" + (f" [{tier}]" if tier else ""))
        if tier == "core":
            hot.append(f"{v}\n{DETAIL}{k}")
        elif tier == "digest":
            record_digest("기업마당", k, v, f"{DETAIL}{k}")
    if hot:
        msg = "기업마당 새 공고(핵심 프로그램, 지원 여부 결정이 필요할 수 있음):\n" + "\n\n".join(hot)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "ops" / "tg_boss.py"), "text", msg, "--persona", "마야"],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
