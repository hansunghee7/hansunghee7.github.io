#!/usr/bin/env python3
"""docs/진행상황.md의 오래된 절을 날짜별 아카이브 파일로 분리한다.

목적
----
모든 에이전트 세션이 아침 의식에서 진행상황.md를 읽으므로, 파일이 커질수록
세션 시작 비용이 커진다. 라이브 파일은 "지금 필요한 절"만 남기고, 나머지는
원문 그대로 docs/진행상황_아카이브/YYYY-MM-DD.md 로 옮긴다.

사용법
------
    python scripts/archive_progress.py                      # 드라이런(기본): 표만 출력
    python scripts/archive_progress.py --today 2026-09-19   # 기준일 지정
    python scripts/archive_progress.py --apply              # 실제로 옮김(무손실 검증 통과 시에만)
    --keep-title SUBSTR / --move-title SUBSTR               # 제목으로 특정 절을 수동 유지/이동(정확히 1개 일치해야 함)

라이브에 남기는 규칙(하나라도 해당하면 유지)
--------------------------------------------
1. 파일 머리말(첫 `## ` 앞의 줄들)
2. 페르소나별 가장 최신 "상태 인수인계" 절 1개씩
   (`[페르소나] 상태` 또는 `🟢/🟡/🔴 페르소나 상태` 제목)
3. `📢` 공지 절 전부. 다만 제목에 '종료'/'완료'가 있으면 이동 가능
   (이 경우 아래 날짜 규칙으로만 판단한다)
4. 응답이 없는 열린 `📥` 절. 같은 주제의 답(📤 또는 받는 사람의 보고)이
   확인되지 않으면 열린 것으로 본다. 판단이 애매하면 유지한다.
5. 최근 48시간 이내(기준일 전날 이후)의 절

무손실 원칙
-----------
- 절 본문은 한 글자도 바꾸지 않고 통째로 옮긴다.
- 옮긴 뒤 (라이브 + 아카이브에 새로 쓴 줄)의 다중집합이, 원본의 줄 + 스크립트가
  일부러 붙인 안내 줄(EXTRA)과 정확히 같아야 한다. 다르면 아무것도 쓰지 않고
  오류로 종료한다.
"""
import argparse
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIVE = REPO / "docs" / "진행상황.md"
ARCHIVE_DIR = REPO / "docs" / "진행상황_아카이브"
ARCHIVE_REL = "진행상황_아카이브/"

POINTER_MARK = "진행상황_아카이브/"
POINTER_LINE = (
    "> 지난 절은 [진행상황_아카이브/](진행상황_아카이브/)에 날짜별로 보관합니다 "
    "(scripts/archive_progress.py)."
)

DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")

# 페르소나 이름(길이 순: 긴 것부터 매칭). 사장님은 에이전트가 아니라서 제외.
PERSONA_ALIASES = {
    "페이블": "페이브",
    "숏감독": "숏",
    "클핏": "핏(클라우드)",
    "로컬핏": "핏(로컬)",
}
PERSONA_NAMES = ["숏감독", "클핏", "로컬핏", "헤르메스", "페이블", "페이브", "마야", "시안", "노트",
                 "렌드", "탐", "핏", "숏", "힐"]
PERSONA_RE = re.compile(
    "(" + "|".join(PERSONA_NAMES) + r")(?:\s*\((로컬|클라우드)[^)]*\))?"
)

STATE_RES = [
    re.compile(r"^\[([^\]]+)\]\s*상태"),
    re.compile(r"^(?:🟢|🟡|🔴)\s*(.+?)\s*상태"),
]

STOP_TOKENS = set("""
요청 완료 확인 회신 결과 지시 지시서 실측 검증 작업 상태 세션 마감 답변 정리 발행 반영 진행 착수
확정 기록 문제 대한 위한 관련 이후 이전 전체 신규 추가 수정 구현 설정 방법 계획 오늘 내일
""".split())

PERSONA_BASES = set(PERSONA_NAMES) | set(PERSONA_ALIASES.values())


def split_lines(text):
    """'\\n' 기준으로만 나눈다(줄 끝 문자 포함). splitlines()는 다른 구분자에서도 잘라서 쓰지 않는다."""
    parts = text.split("\n")
    out = [p + "\n" for p in parts[:-1]]
    if parts[-1] != "":
        out.append(parts[-1])
    return out


def norm_persona(raw):
    """제목의 페르소나 표기를 정규화한다. 못 찾으면 None. 사장님은 None."""
    if not raw:
        return None
    m = PERSONA_RE.search(raw)
    if not m:
        return None
    base, variant = m.group(1), m.group(2)
    base = PERSONA_ALIASES.get(base, base)
    if "(" in base:  # 별칭이 이미 변형을 포함(클핏 등)
        return base
    return f"{base}({variant})" if variant else base


def base_of(name):
    return name.split("(")[0] if name else None


class Section:
    def __init__(self, idx, lines, start_line):
        self.idx = idx
        self.lines = lines
        self.start_line = start_line  # 원본 1-based 줄 번호
        self.title = lines[0].rstrip("\n")[3:].strip()
        self.body = "".join(lines[1:])
        self.date, self.date_src = self._find_date()
        self.kind, self.persona, self.targets = self._classify()
        self.reason = None  # 유지 이유(없으면 이동)

    def _find_date(self):
        m = DATE_RE.search(self.title)
        if m:
            return date.fromisoformat(m.group(0)), "title"
        m = DATE_RE.search(self.body)
        if m:
            try:
                return date.fromisoformat(m.group(0)), "body"
            except ValueError:
                pass
        return None, None

    def _classify(self):
        t = self.title
        if t.startswith("📢"):
            return "공지", norm_persona(t), []
        for r in STATE_RES:
            m = r.match(t)
            if m:
                return "상태", norm_persona(m.group(1)), []
        if t.startswith("📥") or t.startswith("📤"):
            kind = "요청" if t.startswith("📥") else "답신"
            rest = t[1:].strip()
            if "→" in rest:
                left, right = rest.split("→", 1)
                right = re.split(r"[:：]", right, maxsplit=1)[0]
                targets = sorted({base_of(norm_persona(x)) for x in re.split(r"[/·,]", right)
                                  if norm_persona(x)})
                if "사장님" in right and not targets:
                    targets = ["사장님"]
                elif "사장님" in right:
                    targets.append("사장님")
                return kind, norm_persona(left), targets
            head = re.split(r"[:：(]", rest, maxsplit=1)[0]
            return kind, norm_persona(head) or norm_persona(rest), []
        # 기타: 제목 앞쪽(첫 콜론/괄호 전 우선, 없으면 전체)에서 첫 페르소나
        head = re.split(r"[:：]", t, maxsplit=1)[0]
        return "기타", norm_persona(head) or norm_persona(t), []

    @property
    def nlines(self):
        return len(self.lines)


def parse(text):
    lines = split_lines(text)
    preamble = []
    sections = []
    cur = None
    in_fence = False
    for n, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if line.startswith("## ") and not in_fence:
            if cur is not None:
                sections.append(Section(len(sections), cur[1], cur[0]))
            cur = (n, [line])
        elif cur is None:
            preamble.append(line)
        else:
            cur[1].append(line)
    if cur is not None:
        sections.append(Section(len(sections), cur[1], cur[0]))
    return preamble, sections


def tokens(title):
    t = DATE_RE.sub(" ", title)
    t = re.sub(r"[🟢🟡🔴✅⚙️📌📢📥📤⚠️]", " ", t)
    words = re.findall(r"[A-Za-z0-9.]+|[가-힣]+", t)
    out = set()
    for w in words:
        w = w.lower()
        if len(w) < 2 or w in STOP_TOKENS or w in PERSONA_BASES or w in ("로컬", "클라우드", "사장님"):
            continue
        if w.isdigit():
            continue
        out.add(w)
    return out


def overlap(a, b):
    """제목 토큰 겹침 점수. 버전 토큰(v9, v10.1 등) 일치는 2점."""
    score = 0
    used = set()
    for x in a:
        for y in b:
            if y in used:
                continue
            is_ver = re.fullmatch(r"v\d+(\.\d+)*[a-z]?", x) is not None
            # 버전 토큰(v10 대 v10.1)은 정확히 같을 때만 같은 주제로 본다.
            same = x == y or (not is_ver and len(x) >= 3 and len(y) >= 3
                              and (x.startswith(y) or y.startswith(x)))
            if same:
                score += 2 if is_ver else 1
                used.add(y)
                break
    return score


def find_reply(req, sections):
    """열린 📥 판정: 받는 사람이 같은 주제로 답한 절이 있으면 그 절을 돌려준다."""
    if req.date is None or not req.targets or req.targets == ["사장님"]:
        return None
    rtok = tokens(req.title)
    best = None
    for s in sections:
        if s is req or s.kind in ("요청", "공지") or s.date is None or s.date < req.date:
            continue
        if base_of(s.persona) not in req.targets:
            continue
        sc = overlap(rtok, tokens(s.title))
        if sc >= 2 and (best is None or sc > best[0]):
            best = (sc, s)
    return best[1] if best else None


def pick_by_title(sections, substr, label):
    """제목에 substr가 든 절을 정확히 1개 찾는다. 0개나 2개 이상이면 오류로 종료한다."""
    hits = [s for s in sections if substr in s.title]
    if len(hits) != 1:
        raise SystemExit(f"{label} '{substr}': 제목이 일치하는 절이 {len(hits)}개입니다(정확히 1개여야 함).")
    return hits[0]


def decide(preamble, sections, today, keep_reports=False, keep_titles=(), move_titles=()):
    cutoff = today - timedelta(days=1)
    forced_move = set()
    for t in move_titles:
        forced_move.add(pick_by_title(sections, t, "--move-title").idx)
    # 페르소나별 최신 상태 절 (bare 이름은 같은 base의 변형이 있으면 제외)
    states = [s for s in sections if s.kind == "상태" and s.persona and s.date]
    variants_of = {}
    for s in states:
        if "(" in s.persona:
            variants_of.setdefault(base_of(s.persona), set()).add(s.persona)
    latest = {}
    for s in states:
        key = s.persona
        if "(" not in key and key in variants_of:
            continue
        cur = latest.get(key)
        if cur is None or (s.date, -s.idx) > (cur.date, -cur.idx):
            latest[key] = s
    for key, s in latest.items():
        s.reason = f"② {key} 최신 상태"
    # '상태' 제목을 안 쓰는 페르소나의 최신 세션 보고(🟢/🟡/🔴/✅ 로 시작하는 기타 절) 후보
    has_state = set(latest) | {base_of(k) for k in latest}
    reports = {}
    for s in sections:
        if s.kind != "기타" or not s.persona or not s.date or not re.match(r"[🟢🟡🔴✅]", s.title):
            continue
        if s.persona in has_state or (base_of(s.persona) in variants_of and "(" not in s.persona):
            continue
        cur = reports.get(s.persona)
        if cur is None or (s.date, -s.idx) > (cur.date, -cur.idx):
            reports[s.persona] = s
    if keep_reports:
        for key, s in reports.items():
            s.reason = f"②' {key} 최신 보고"
    notes = {"open_req": [], "closed_req": [], "ambiguous_req": [], "undated": [], "reports": reports}
    for t in keep_titles:
        s = pick_by_title(sections, t, "--keep-title")
        if not s.reason:
            s.reason = "⑥ 수동 유지"
    for s in sections:
        if s.reason or s.idx in forced_move:
            continue
        if s.kind == "공지" and not re.search(r"종료|완료", s.title):
            s.reason = "③ 공지"
        elif s.date is not None and s.date >= cutoff:
            s.reason = "⑤ 최근 48시간"
        elif s.kind == "요청":
            reply = find_reply(s, sections)
            if reply is None:
                s.reason = "④ 열린 요청"
                if s.targets and s.targets != ["사장님"] and s.date is not None:
                    notes["open_req"].append(s)
                else:
                    notes["ambiguous_req"].append(s)
            else:
                notes["closed_req"].append((s, reply))
        elif s.date is None:
            notes["undated"].append(s)
    return latest, notes


def build_output(preamble, sections):
    live = list(preamble)
    if not any(POINTER_MARK in l for l in preamble):
        pos = None
        for i, l in enumerate(live):
            if l.startswith(">"):
                pos = i
        pointer = POINTER_LINE + "\n"
        if pos is None:
            live.append(pointer)
        else:
            live.insert(pos + 1, pointer)
        extras = [POINTER_LINE]
    else:
        extras = []
    moved = {}
    for s in sections:
        if s.reason:
            live.extend(s.lines)
        else:
            moved.setdefault(s.date.isoformat() if s.date else "미상", []).append(s)
    return live, moved, extras


def archive_new_lines(day, secs, existing_exists):
    out = []
    extras = []
    if not existing_exists:
        h = f"# 진행상황 아카이브 ({day})"
        out += [h + "\n", "\n"]
        extras += [h, ""]
    for s in secs:
        out.extend(s.lines)
    return out, extras


def strip_nl(lines):
    return [l[:-1] if l.endswith("\n") else l for l in lines]


def verify_lossless(orig_lines, live_lines, archive_added, extras):
    """(라이브 + 아카이브에 새로 쓴 줄) == (원본 + EXTRA) 를 줄 다중집합으로 확인한다."""
    got = Counter(strip_nl(live_lines)) + Counter(strip_nl(archive_added))
    want = Counter(strip_nl(orig_lines)) + Counter(extras)
    if got != want:
        lost = want - got
        gained = got - want
        raise SystemExit(
            f"무손실 검증 실패: 사라진 줄 {sum(lost.values())}, 늘어난 줄 {sum(gained.values())}. "
            f"아무것도 쓰지 않고 종료합니다."
        )


def report(preamble, sections, latest, notes, live, moved, today, orig_lines):
    kept = [s for s in sections if s.reason]
    gone = [s for s in sections if not s.reason]
    p = print
    p(f"# 아카이브 드라이런 (기준일 {today}, 유지 기준 {today - timedelta(days=1)} 이후)")
    p()
    p("## 요약")
    p(f"- 전체 절: {len(sections)}  |  유지: {len(kept)}  |  이동: {len(gone)}")
    p(f"- 라이브 파일 줄 수: 현재 {len(orig_lines)} -> 예상 {len(live)} "
      f"({100 * len(live) / max(1, len(orig_lines)):.1f}%)")
    p(f"- 이동 줄 수 합계: {sum(s.nlines for s in gone)}")
    by = Counter(s.reason.split()[0] for s in kept)
    p("- 유지 이유별: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
    kinds = Counter(s.kind for s in sections)
    p("- 종류별 절 수: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
    p()
    p("## 아카이브 파일별 (절 수 / 줄 수)")
    p("| 파일 | 절 | 줄 |")
    p("|---|---|---|")
    for day in sorted(moved, key=lambda d: (d == "미상", d), reverse=False):
        secs = moved[day]
        p(f"| {day}.md | {len(secs)} | {sum(s.nlines for s in secs)} |")
    p()
    p(f"## 유지되는 절 전체 ({len(kept)}개)")
    p("| # | 원본 줄 | 줄 수 | 이유 | 날짜 | 제목 |")
    p("|---|---|---|---|---|---|")
    for s in kept:
        p(f"| {s.idx} | {s.start_line} | {s.nlines} | {s.reason} | {s.date or '미상'} | {s.title[:90]} |")
    p()
    p("## 이동 절 제목 (앞 40개)")
    for s in gone[:40]:
        p(f"- [{s.date or '미상'}|{s.kind}|{s.persona or '-'}] {s.title[:90]}")
    p(f"- ... 외 {max(0, len(gone) - 40)}개")
    p()
    p("## 페르소나별 최신 상태 인수인계 절")
    p("| 페르소나 | 유지된 절(원본 줄) | 날짜 |")
    p("|---|---|---|")
    for key in sorted(latest):
        s = latest[key]
        p(f"| {key} | L{s.start_line} {s.title[:60]} | {s.date} |")
    p()
    p("## '상태' 제목이 없는 페르소나의 최신 세션 보고 (기본은 유지, --no-keep-latest-report로 이동)")
    p("| 페르소나 | 원본 줄 | 줄 수 | 날짜 | 제목 |")
    p("|---|---|---|---|---|")
    for key in sorted(notes["reports"]):
        s = notes["reports"][key]
        p(f"| {key} | L{s.start_line} | {s.nlines} | {s.date} | {s.title[:70]} |")
    p()
    p("## 전원 확인 완료로 보이는 공지(제목에 ☐ 없음, 유지 중)")
    for s in sections:
        if s.kind == "공지" and s.reason and "☐" not in s.title and "☑" in s.title:
            p(f"- L{s.start_line} {s.date} {s.title[:80]}")
    p()
    p("## 열린 요청(📥) 판정")
    p(f"- 유지(답 없음 확인): {len(notes['open_req'])}건, 유지(받는 사람 불명확): "
      f"{len(notes['ambiguous_req'])}건, 답 확인되어 이동: {len(notes['closed_req'])}건")
    for s in notes["open_req"]:
        p(f"  - 유지 L{s.start_line} {s.date} {s.title[:80]}")
    for s in notes["ambiguous_req"]:
        p(f"  - 유지(불명확) L{s.start_line} {s.date} {s.title[:80]}")
    for s, r in notes["closed_req"]:
        p(f"  - 이동 L{s.start_line} {s.date} {s.title[:60]}  <= 답: L{r.start_line} {r.title[:50]}")
    p()
    p("## 날짜 없는 절(미상.md로 이동)")
    for s in notes["undated"]:
        p(f"- L{s.start_line} {s.title[:90]}")
    p()
    p("## 종류 판정 참고")
    for s in gone:
        if s.kind == "기타" and s.persona is None and s.date is not None:
            p(f"- 페르소나 미상 기타: L{s.start_line} {s.title[:80]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="기본 동작(파일 안 씀)")
    ap.add_argument("--apply", action="store_true", help="실제로 옮김(무손실 검증 통과 시에만)")
    ap.add_argument("--keep-latest-report", action=argparse.BooleanOptionalAction, default=True,
                    help="'상태' 제목이 없는 페르소나도 최신 세션 보고 1개를 유지(기본: 켬, 끄려면 --no-keep-latest-report)")
    ap.add_argument("--keep-title", action="append", default=[], metavar="SUBSTR",
                    help="제목에 SUBSTR가 든 절(정확히 1개)을 라이브에 유지(날짜 없는 절 등). 반복 가능")
    ap.add_argument("--move-title", action="append", default=[], metavar="SUBSTR",
                    help="제목에 SUBSTR가 든 절(정확히 1개)을 규칙과 무관하게 아카이브로 이동. 반복 가능")
    ap.add_argument("--today", default=None, help="기준일 YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--live", default=str(LIVE), help="라이브 파일 경로")
    ap.add_argument("--archive-dir", default=str(ARCHIVE_DIR), help="아카이브 폴더 경로")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    today = date.fromisoformat(args.today) if args.today else date.today()
    live_path = Path(args.live)
    arch_dir = Path(args.archive_dir)
    text = live_path.read_bytes().decode("utf-8")
    orig_lines = split_lines(text)
    preamble, sections = parse(text)
    latest, notes = decide(preamble, sections, today, args.keep_latest_report,
                           args.keep_title, args.move_title)
    live, moved, extras = build_output(preamble, sections)

    archive_added = []
    per_file = {}
    for day, secs in moved.items():
        exists = (arch_dir / f"{day}.md").exists()
        new, ex = archive_new_lines(day, secs, exists)
        per_file[day] = new
        archive_added += new
        extras += ex
    verify_lossless(orig_lines, live, archive_added, extras)

    if not args.apply:
        report(preamble, sections, latest, notes, live, moved, today, orig_lines)
        print()
        print("드라이런: 파일을 쓰지 않았습니다. 무손실 검증(메모리 내): 통과.")
        return

    arch_dir.mkdir(parents=True, exist_ok=True)
    for day, new in per_file.items():
        path = arch_dir / f"{day}.md"
        prior = path.read_bytes().decode("utf-8") if path.exists() else ""
        if prior and not prior.endswith("\n"):
            prior += "\n"
        path.write_bytes((prior + "".join(new)).encode("utf-8"))
    live_path.write_bytes("".join(live).encode("utf-8"))
    print(f"적용 완료: 라이브 {len(orig_lines)} -> {len(live)}줄, 아카이브 {len(per_file)}개 파일.")


if __name__ == "__main__":
    main()
