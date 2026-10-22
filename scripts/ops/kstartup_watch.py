#!/usr/bin/env python3
"""K-Startup 모집중 공고 감시(2026-10-14 탐, 공정 카드 탐-공고수집 #2, 사장님 결정: 창업도약 다음 회차 준비).
목록 페이지(모집중)에서 새 공고를 찾아 상태 파일에 기록한다. 첫 실행은 기준선만 저장하고 알리지 않는다.
관심 키워드 공고가 새로 뜨면 텔레그램으로 알린다. 읽기 전용, 30초 타임아웃. 종료 코드 1 = 목록을 못 읽음(파싱 0건)."""
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
URL = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
STATE = Path("C:/work/_ops/grants_prep/ks_seen.json")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
from notice_filter import classify, record_digest  # noqa: E402  분류 규칙은 notice_filter.py 한 곳에서 고친다


def parse(raw):
    """HTML에서 (공고번호, 제목) 목록을 뽑는다."""
    out = []
    for m in re.finditer(r"go_view\((\d+)\)", raw):
        seg = raw[m.end(): m.end() + 900]
        t = re.search(r'<p class="tit">\s*(.*?)\s*</p>', seg, re.S)
        if t:
            out.append((m.group(1), html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip()))
    seen = {}
    for k, v in out:
        seen.setdefault(k, v)
    return list(seen.items())


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def main():
    raw = fetch()
    items = parse(raw)
    if not items:
        msg = "목록 파싱 0건: 페이지 구조가 바뀌었을 수 있음"
        try:
            dump = STATE.parent / ("ks_parse0_" + time.strftime("%Y%m%d_%H%M%S") + ".html")
            dump.parent.mkdir(parents=True, exist_ok=True)
            data = raw.encode("utf-8")
            dump.write_bytes(data)
            msg += f" (응답 {len(data)}바이트 저장: {dump})"
        except Exception:
            pass
        print(msg)
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
        url = f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={k}"
        print(f"- {k} {v}" + (f" [{tier}]" if tier else ""))
        if tier == "core":
            hot.append(f"{v}\n{url}")
        elif tier == "digest":
            record_digest("K-Startup", k, v, url)
    if hot:
        msg = "K-Startup 새 공고(핵심 프로그램, 지원 여부 결정이 필요할 수 있음):\n" + "\n\n".join(hot)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "ops" / "tg_boss.py"), "text", msg, "--persona", "마야"],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
