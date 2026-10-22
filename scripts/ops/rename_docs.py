#!/usr/bin/env python3
"""docs·지시서 옛 이름(saegim·새김) 문서 일괄 치환 도구 (공정 카드 탐-슈퍼글로벌 #159, 2-4).
[옛이름 허용: 치환 도구라 옛 이름 패턴 자체를 다뤄야 함]

범위: docs/ 아래 .md 파일(지시서 폴더 docs/지시서 포함). 파일 이름은 바꾸지 않는다(내용만).

분류:
  history  날짜 파일명(YYYY-MM-DD_*.md)의 지시서 — 과거 기록이라 문구를 고치지 않는다(이름_정책.md).
  explain  옛 이름 정책·소거 작업을 설명하는 문서(이름_정책.md 등) 전체, 또는 [옛이름 허용: ...]가
           적힌 줄 — 정책 설명상 그대로 둬야 하는 언급.
  skip     saegim-pass, simplifier-saegim 같은 복합 식별자(시스템 ID, docs/이름_정책.md 3층) —
           표준 낱말 경계 밖이라 일괄 치환 대상이 아니다(손대면 실제 저장소·경로 이름과 어긋난다).
  replace  나머지: 본문에 단어로 쓰인 saegim/새김 — carvit/카빗로 치환 후보.

사용:
  python scripts/ops/rename_docs.py --dry-run            전체 docs 스캔, 파일별 줄 미리보기 + 건수
  python scripts/ops/rename_docs.py --apply              실제 치환(링크 깨짐 위험 있는 줄은 건너뛰고 보고)
  python scripts/ops/rename_docs.py --dry-run --root docs/지시서   범위 좁히기
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# saegim은 영문 식별자라 앞뒤에 식별자 문자(영문·숫자·_·-·.·/)가 붙으면 복합 식별자(시스템 ID)로 보고
# 건드리지 않는다(saegim-mcp, saegim_courier.py, simplifier-saegim, mcp__saegim__agents 등).
# 새김은 한글이라 조사가 델리미터 없이 바로 붙으므로(새김이라고, 새김도) 한글 인접은 경계로 보지 않는다.
EN_TOKEN = re.compile(r"[A-Za-z0-9_.\-/]*saegim[A-Za-z0-9_.\-]*", re.IGNORECASE)
EN_BARE = re.compile(r"(?<![A-Za-z0-9_.\-/])saegim(?![A-Za-z0-9_.\-])", re.IGNORECASE)
KO_CHAR = re.compile(r"(?<![A-Za-z0-9_.\-])새김(?![A-Za-z0-9_.\-])")
ANY_HIT = re.compile(r"saegim|새김", re.IGNORECASE)


class _CombinedPattern:
    """두 패턴(영문 bare, 한글)의 매치를 위치순으로 합쳐 re.Pattern처럼 쓰기 위한 얇은 래퍼."""

    def __init__(self, patterns):
        self.patterns = patterns

    def finditer(self, s):
        ms = []
        for p in self.patterns:
            ms.extend(p.finditer(s))
        ms.sort(key=lambda m: m.start())
        return ms

    def search(self, s):
        ms = self.finditer(s)
        return ms[0] if ms else None

    def findall(self, s):
        return [m.group(0) for m in self.finditer(s)]


# 표준 낱말 경계: 복합 식별자가 아닌 "그 자체로 쓰인" saegim/새김만 치환 후보로 잡는다.
WORD = _CombinedPattern([EN_BARE, KO_CHAR])

ESCAPE = "[옛이름 허용:"
HISTORY_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_.*\.md$", re.IGNORECASE)

# 옛 이름 정책·소거 작업 자체를 설명해야 하는 문서(전체 허용). repo-relative, '/' 구분.
EXPLAIN_FILES = {
    "docs/이름_정책.md",
    "docs/옛이름_소거_슈퍼프로젝트.md",
}


def apply_case(repl, original):
    if original.isupper():
        return repl.upper()
    if original[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def rel(path):
    return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")


def is_history_path(relpath):
    parts = relpath.split("/")
    return any(HISTORY_NAME.match(p) for p in parts)


def is_explain_path(relpath):
    return relpath in EXPLAIN_FILES


def find_md_files(root):
    root = Path(root)
    out = []
    for p in root.rglob("*.md"):
        if not p.is_file():
            continue
        parts = p.parts
        if any(seg in (".git", "node_modules", "__pycache__", ".claude") for seg in parts):
            continue
        out.append(p)
    return sorted(out)


def scan_line(line):
    """[옛이름 허용: 치환 도구라 패턴 예시를 그대로 적어야 함]
    한 줄의 옛 이름 적중을 (분류, 매치객체) 리스트로, 글자 위치 순으로 나눈다.
    영문 복합 식별자(접두·접미가 붙은 형태)는 skip, 그 자체로 쓰인 낱말은 replace."""
    out = []
    for m in EN_TOKEN.finditer(line):
        out.append(("replace" if m.group(0).lower() == "saegim" else "skip", m))
    for m in KO_CHAR.finditer(line):
        out.append(("replace", m))
    out.sort(key=lambda t: t[1].start())
    return out


def heading_slug(text):
    """GitHub 스타일에 가까운 단순 슬러그(완전 호환은 아니고 변경 여부 비교용)."""
    t = unicodedata.normalize("NFC", text).strip().lower()
    t = re.sub(r"[^\w\s가-힣-]", "", t)
    t = re.sub(r"\s+", "-", t)
    return t


def build_link_index(md_files):
    """repo-relative(확장자 제외 파일명) -> [(링크를_건_파일, 앵커), ...]"""
    link_re = re.compile(r"\[[^\]]*\]\(([^)\s]+\.md)(#[^)\s]*)?\)")
    idx = {}
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        src = rel(f)
        for m in link_re.finditer(text):
            target, anchor = m.group(1), (m.group(2) or "").lstrip("#")
            name = Path(target).name
            idx.setdefault(name, []).append((src, anchor))
    return idx


def headings_in(lines):
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            out.append((i, m.group(2).strip()))
    return out


def process_file(path, link_index, apply_changes):
    relpath = rel(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    history_file = is_history_path(relpath)
    explain_file = is_explain_path(relpath)

    file_report = {"path": relpath, "lines": [], "counts": {"history": 0, "explain": 0, "skip": 0, "replace": 0}, "blocked": []}
    before_headings = headings_in([l.rstrip("\n") for l in lines])
    changed = False

    for i, raw in enumerate(lines):
        bare = raw.rstrip("\n")
        if ANY_HIT.search(bare) is None:
            continue
        if history_file:
            file_report["counts"]["history"] += len(ANY_HIT.findall(bare))
            continue
        if explain_file or ESCAPE in bare:
            file_report["counts"]["explain"] += len(ANY_HIT.findall(bare))
            continue

        hits = scan_line(bare)
        file_report["counts"]["skip"] += sum(1 for c, _ in hits if c == "skip")
        n_replace = sum(1 for c, _ in hits if c == "replace")
        if n_replace == 0:
            continue
        file_report["counts"]["replace"] += n_replace

        new_bare = bare
        offset = 0
        for cat, m in hits:
            if cat != "replace":
                continue
            start, end = m.start() + offset, m.end() + offset
            # [옛이름 허용: 치환 도구라 원문 토큰과 비교해야 함]
            repl = apply_case("carvit", m.group(0)) if m.group(0).lower() == "saegim" else "카빗"
            new_bare = new_bare[:start] + repl + new_bare[end:]
            offset += len(repl) - (end - start)

        is_heading = bool(re.match(r"^(#{1,6})\s+", bare))
        blocked = False
        if is_heading:
            heading_text_before = re.sub(r"^#{1,6}\s+", "", bare)
            heading_text_after = re.sub(r"^#{1,6}\s+", "", new_bare)
            slug_before, slug_after = heading_slug(heading_text_before), heading_slug(heading_text_after)
            if slug_before != slug_after:
                refs = link_index.get(path.name, [])
                hit_refs = [r for r in refs if r[1] and r[1].lower() == slug_before]
                if hit_refs:
                    blocked = True
                    file_report["blocked"].append({
                        "line": i + 1, "slug_before": slug_before, "slug_after": slug_after,
                        "linked_from": sorted({src for src, _ in hit_refs}),
                    })

        file_report["lines"].append({"line": i + 1, "before": bare, "after": new_bare, "blocked": blocked})
        if apply_changes and not blocked:
            lines[i] = new_bare + ("\n" if raw.endswith("\n") else "")
            changed = True

    if apply_changes and changed:
        path.write_text("".join(lines), encoding="utf-8")
    return file_report


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="docs·지시서 옛 이름 문서 일괄 치환")
    ap.add_argument("--root", default="docs", help="스캔 루트(저장소 상대 경로), 기본 docs")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    root = (REPO_ROOT / a.root).resolve()
    if not root.is_dir():
        print("루트 폴더 없음: %s" % root, file=sys.stderr)
        return 2

    md_files = find_md_files(root)
    link_index = build_link_index(find_md_files(REPO_ROOT / "docs"))

    reports = [process_file(p, link_index, apply_changes=a.apply) for p in md_files]

    total = {"history": 0, "explain": 0, "skip": 0, "replace": 0}
    blocked_total = 0
    touched_files = 0
    for r in reports:
        for k in total:
            total[k] += r["counts"][k]
        blocked_total += len(r["blocked"])
        if r["lines"]:
            touched_files += 1
            print("## %s" % r["path"])
            for ln in r["lines"]:
                mark = " [링크 위험: 적용 안 함]" if ln["blocked"] else ""
                print("  L%d%s" % (ln["line"], mark))
                print("    - %s" % ln["before"])
                print("    + %s" % ln["after"])
            if r["blocked"]:
                for b in r["blocked"]:
                    print("  ! L%d 헤딩 슬러그 %s -> %s, 참조: %s" % (b["line"], b["slug_before"], b["slug_after"], ", ".join(b["linked_from"])))
            print()

    print("=== 요약 (%s) ===" % ("적용" if a.apply else "미리보기"))
    print("대상 파일: %d개, 치환 줄 포함 파일: %d개" % (len(md_files), touched_files))
    print("치환 후보(replace): %d건, 링크 위험으로 건너뜀: %d건" % (total["replace"], blocked_total))
    print("건드리지 않음 — 히스토리: %d건, 설명(허용): %d건, 시스템 ID(skip): %d건" % (total["history"], total["explain"], total["skip"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
