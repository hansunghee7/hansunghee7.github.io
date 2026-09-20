#!/usr/bin/env python3
"""card.py: 작업 카드(글 한 편 = 파일 한 장) 만들기·갱신·조회.

규격: docs/작업카드_규격_초안.md (2026-09-20). 에이전트는 카드 파일을 손으로 고치지 않고 이 도구로만 갱신한다.
  - 시각은 이 도구가 기록한다(모델이 쓴 시각을 믿지 않는다. 지원사업 보고서 접속 시각 사고).
  - 담당·다음 담당만 카드를 넘길 수 있다(남의 단계를 대신 넘기지 않는다). 예외는 --force.
  - 사장님차례 알림은 CLAUDE.md 튜터 원칙 7(마야 형식): 제목=결정 대상, 본문 한 줄=선택지 수와 추천, --ask=할 일 한 줄.

사용:
  card.py new <짧은이름> --title "글 제목" --by 마야 [--next 헤르메스]
  card.py advance <id> --stage 수집 --by 헤르메스 [--next 제미나이] [--out 경로] [--note "한 줄"]
  card.py ask-boss <id> --by 마야 --need "1~3번 중 하나를 골라 알려 주세요" [--notify --decision "..." --summary "..."]
  card.py block <id> --by 헤르메스 --reason "이유 한 줄"
  card.py done <id> --by 마야
  card.py show [<id>]

환경변수(시험용): CARDS_DIR(기본 C:\\work\\solar-bible\\cards), MAILBOX_PY(기본 C:\\work\\solar-bible\\mailbox\\mailbox.py)
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CARDS = Path(os.environ.get("CARDS_DIR", r"C:\work\solar-bible\cards"))
MAILBOX = os.environ.get("MAILBOX_PY", r"C:\work\solar-bible\mailbox\mailbox.py")
STATES = ["접수", "진행", "사장님차례", "완료", "실패", "취소"]
STAGES = ["의뢰", "수집", "검증", "질의", "수정", "집필", "확정"]
KEYS = ["id", "제목", "상태", "단계", "담당", "다음", "막힘", "사장님 할 일"]
TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)$")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def path_of(card_id):
    return CARDS / f"{card_id}.md"


def read_card(card_id):
    p = path_of(card_id)
    if not p.exists():
        die(f"카드가 없습니다: {card_id}")
    meta, outs, hist, mode = {}, [], [], "front"
    for line in p.read_text(encoding="utf-8").splitlines():
        if mode == "front":
            if line.strip() == "---" and meta:
                mode = "body"
            elif line.strip() == "---":
                continue
            elif line.startswith("  - "):
                outs.append(line[4:].strip())
            elif ":" in line and not line.startswith("산출물"):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        elif TS.match(line):
            hist.append(line)
    return meta, outs, hist


def write_card(meta, outs, hist):
    lines = ["---"] + [f"{k}: {meta.get(k, '')}" for k in KEYS] + ["산출물:"] + [f"  - {o}" for o in outs]
    lines += ["---", "## 이력 (도구가 자동 기록. 손으로 고치지 않는다)"] + hist
    p = path_of(meta["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def die(msg):
    print(f"[오류] {msg}")
    sys.exit(2)


def check_turn(meta, by, force):
    if force:
        return
    allowed = {meta.get("담당"), meta.get("다음")}
    if by not in allowed:
        die(f"지금은 {meta.get('담당')}(다음: {meta.get('다음') or '없음'}) 차례입니다. {by}는 넘길 수 없습니다(--force로 예외).")


def cmd_new(a):
    card_id = f"{time.strftime('%Y%m%d')}-{a.name}"
    if path_of(card_id).exists():
        die(f"이미 있는 카드입니다: {card_id}")
    meta = {"id": card_id, "제목": a.title, "상태": "접수", "단계": "의뢰", "담당": a.by,
            "다음": a.next or "", "막힘": "없음", "사장님 할 일": "없음"}
    write_card(meta, [], [f"{now()} 접수 {a.by}"])
    print(f"만들었습니다: {card_id}")


def cmd_advance(a):
    if a.stage not in STAGES:
        die(f"단계는 {'/'.join(STAGES)} 중 하나입니다.")
    meta, outs, hist = read_card(a.id)
    check_turn(meta, a.by, a.force)
    meta.update({"상태": "진행", "단계": a.stage, "담당": a.by, "다음": a.next or "", "막힘": "없음", "사장님 할 일": "없음"})
    if a.out:
        outs.append(a.out)
    hist.append(f"{now()} {a.stage} 진행 {a.by}" + (f" | {a.note}" if a.note else ""))
    write_card(meta, outs, hist)
    print(f"{a.id}: {a.stage} 진행 ({a.by})")


def cmd_ask_boss(a):
    meta, outs, hist = read_card(a.id)
    check_turn(meta, a.by, a.force)
    meta.update({"상태": "사장님차례", "담당": a.by, "사장님 할 일": a.need})
    hist.append(f"{now()} 사장님차례 {a.by} | {a.need}")
    write_card(meta, outs, hist)
    print(f"{a.id}: 사장님차례 ({a.by})")
    if a.notify:
        if not (a.decision and a.summary):
            die("--notify에는 --decision(무엇에 대한 결정)과 --summary(선택지 수와 추천 한 줄)가 필요합니다.")
        r = subprocess.run([sys.executable, MAILBOX, "send", "사장님", a.decision, "--from", a.by,
                            "--body", a.summary, "--ask", a.need], capture_output=True, text=True, encoding="utf-8")
        print("알림 발송:", "성공" if r.returncode == 0 else f"실패({(r.stderr or r.stdout).strip()[:120]})")


def cmd_block(a):
    meta, outs, hist = read_card(a.id)
    check_turn(meta, a.by, a.force)
    meta.update({"상태": "실패", "담당": a.by, "막힘": a.reason})
    hist.append(f"{now()} 실패 {a.by} | {a.reason}")
    write_card(meta, outs, hist)
    print(f"{a.id}: 실패 ({a.by}) {a.reason}")


def cmd_done(a):
    meta, outs, hist = read_card(a.id)
    check_turn(meta, a.by, a.force)
    meta.update({"상태": "완료", "담당": a.by, "다음": "", "막힘": "없음", "사장님 할 일": "없음"})
    hist.append(f"{now()} 완료 {a.by}")
    write_card(meta, outs, hist)
    print(f"{a.id}: 완료 ({a.by})")


def secs(a, b):
    f = "%Y-%m-%d %H:%M:%S"
    return int(time.mktime(time.strptime(b, f)) - time.mktime(time.strptime(a, f)))


def cmd_show(a):
    if not a.id:
        for p in sorted(CARDS.glob("*.md")):
            meta, _, hist = read_card(p.stem)
            last = TS.match(hist[-1]).group(1) if hist else "-"
            todo = "" if meta.get("사장님 할 일") in ("", "없음") else f" | 👉 {meta['사장님 할 일']}"
            print(f"{meta['id']} | {meta['상태']} | {meta['단계']} | {meta['담당']}→{meta.get('다음') or '-'} | {last}{todo}")
        return
    meta, outs, hist = read_card(a.id)
    print(f"{meta['제목']} ({meta['id']})")
    print(f"상태 {meta['상태']} / 단계 {meta['단계']} / 담당 {meta['담당']} → 다음 {meta.get('다음') or '-'}")
    if meta.get("막힘") not in ("", "없음"):
        print(f"막힘: {meta['막힘']}")
    if meta.get("사장님 할 일") not in ("", "없음"):
        print(f"👉 사장님 할 일: {meta['사장님 할 일']}")
    prev = None
    for h in hist:
        t = TS.match(h).group(1)
        gap = f"  (+{secs(prev, t)}초)" if prev else ""
        print(f"  {h}{gap}")
        prev = t
    if len(hist) > 1:
        print(f"전체 {secs(TS.match(hist[0]).group(1), TS.match(hist[-1]).group(1))}초, 산출물 {len(outs)}건")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="작업 카드 도구")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        s = sub.add_parser(name)
        s.set_defaults(fn=fn)
        s.add_argument("--force", action="store_true")
        return s

    s = add("new", cmd_new)
    s.add_argument("name")
    s.add_argument("--title", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--next")
    s = add("advance", cmd_advance)
    s.add_argument("id")
    s.add_argument("--stage", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--next")
    s.add_argument("--out")
    s.add_argument("--note")
    s = add("ask-boss", cmd_ask_boss)
    s.add_argument("id")
    s.add_argument("--by", required=True)
    s.add_argument("--need", required=True)
    s.add_argument("--notify", action="store_true")
    s.add_argument("--decision")
    s.add_argument("--summary")
    s = add("block", cmd_block)
    s.add_argument("id")
    s.add_argument("--by", required=True)
    s.add_argument("--reason", required=True)
    s = add("done", cmd_done)
    s.add_argument("id")
    s.add_argument("--by", required=True)
    s = add("show", cmd_show)
    s.add_argument("id", nargs="?")
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
