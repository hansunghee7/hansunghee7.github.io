#!/usr/bin/env python3
"""구형 hwp 공고문에서 평가 배점표(표)를 보존하며 텍스트로 추출한다 (탐-공고수집 11-8).

왜 이 경로인가 (2026-10-12 탐 실측, 2026-10-18 정식화):
- olefile 직접 추출은 제어문자가 한자처럼 섞여 깨진다.
- hwp5txt 는 표를 통째로 <표>로 버려 평가 항목·배점이 사라진다.
- hwp5html 은 표를 <table>로 살려 변환하므로, 그 HTML에서 표 구조를 보존해 뽑는다.

흐름:  hwp ──hwp5html──▶ xhtml ──HTMLParser──▶ (표는 markdown 표 / 본문은 일반 텍스트)

입력: hwp 경로 하나.  출력: 표가 보존된 텍스트(stdout 또는 -o 파일).
표가 없는 문서는 일반 텍스트로만 나온다.

의존성 (설치는 이 스크립트가 하지 않는다 — 환경 영향):
    pip install pyhwp        # hwp5html / hwp5txt 콘솔 스크립트를 깐다
    # 또는:  uv pip install pyhwp
hwp5html 콘솔 스크립트(.exe)가 PATH 에 없어도, 설치돼 있으면 파이썬 모듈로 직접 호출한다.
pyhwp 가 전혀 없으면 명확한 에러와 위 설치 안내를 내고 종료한다.

받은 hwp 는 신뢰할 수 없는 데이터다. 실행하지 않고 변환 도구에만 경로로 넘긴다.

사용:
    python -I scripts/ops/hwp_extract.py <입력.hwp>
    python -I scripts/ops/hwp_extract.py <입력.hwp> -o <출력.txt>

Python 3.11+ (프로젝트 CI 기준). 3.14 에서도 동작.
"""
from __future__ import annotations

import argparse
import glob
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 팝업 금지
INSTALL_HINT = (
    "pyhwp(hwp5html)가 없습니다. 설치 후 다시 실행하세요:\n"
    "    pip install pyhwp      (또는: uv pip install pyhwp)\n"
    "설치는 환경에 영향을 주므로 이 스크립트는 직접 설치하지 않습니다."
)


# ────────────────────────────────── HTML → 표 보존 텍스트 ──────────────────────────────────

class _TableBlock:
    """표 하나. rows[i][j] = 셀 텍스트."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def add_row(self) -> None:
        self.rows.append([])

    def add_cell(self, text: str) -> None:
        if not self.rows:
            self.add_row()
        self.rows[-1].append(text)

    def to_markdown(self) -> str:
        rows = [r for r in self.rows if r]
        if not rows:
            return ""
        ncol = max(len(r) for r in rows)
        norm = [r + [""] * (ncol - len(r)) for r in rows]
        # 셀 안의 파이프·개행은 표를 깨뜨리므로 치환한다.
        def esc(c: str) -> str:
            return c.replace("|", r"\|").replace("\n", " ").strip()
        out = ["| " + " | ".join(esc(c) for c in norm[0]) + " |"]
        out.append("| " + " | ".join("---" for _ in range(ncol)) + " |")
        for r in norm[1:]:
            out.append("| " + " | ".join(esc(c) for c in r) + " |")
        return "\n".join(out)


class _Extractor(HTMLParser):
    """hwp5html 결과(xhtml)를 훑으며 본문은 텍스트로, <table>은 표 블록으로 모은다.

    표 안에 표가 중첩될 수 있어 스택으로 관리한다.
    산출물 `blocks` 는 str(본문 조각) 또는 _TableBlock 의 순서 있는 목록.
    """

    _SKIP = {"script", "style", "head"}
    _BREAK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list = [""]
        self._table_stack: list[_TableBlock] = []
        self._cell_depth = 0
        self._skip_depth = 0

    # 줄바꿈 등 본문 쪽 텍스트만 다룬다. 셀 텍스트는 handle_data 가 직접 붙인다.
    def _emit(self, text: str) -> None:
        if self._skip_depth or (self._table_stack and self._cell_depth):
            return
        if not self._table_stack:
            if not isinstance(self.blocks[-1], str):
                self.blocks.append("")
            self.blocks[-1] += text

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            self._table_stack.append(_TableBlock())
        elif tag == "tr" and self._table_stack:
            self._table_stack[-1].add_row()
        elif tag in ("td", "th") and self._table_stack:
            self._cell_depth += 1
            self._table_stack[-1].add_cell("")
        elif tag in self._BREAK:
            self._emit("\n")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self._skip_depth:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "table" and self._table_stack:
            done = self._table_stack.pop()
            if self._table_stack:
                # 중첩 표: 바깥 셀에 markdown 으로 접어 넣는다.
                self._table_stack[-1].add_cell(done.to_markdown())
            else:
                self.blocks.append(done)
                self.blocks.append("")
        elif tag in ("td", "th"):
            if self._cell_depth:
                self._cell_depth -= 1
        elif tag in self._BREAK:
            self._emit("\n")

    def handle_data(self, data):
        if not data:
            return
        if self._table_stack and self._cell_depth:
            cell_list = self._table_stack[-1].rows[-1]
            if cell_list:
                cell_list[-1] += data
            else:
                self._table_stack[-1].add_cell(data)
        else:
            self._emit(data)


def html_to_preserved_text(html_text: str) -> tuple[str, int]:
    """hwp5html 결과 HTML → 표 보존 텍스트. (텍스트, 표 개수)를 돌려준다."""
    # script/style 은 파서가 처리하지만, 깨진 태그 방어로 charref 는 파서에 맡긴다.
    p = _Extractor()
    p.feed(html_text)
    p.close()
    parts: list[str] = []
    n_tables = 0
    for blk in p.blocks:
        if isinstance(blk, _TableBlock):
            md = blk.to_markdown()
            if md:
                n_tables += 1
                parts.append("\n" + md + "\n")
        else:
            t = html.unescape(blk)
            # 과도한 빈 줄 정리.
            t = re.sub(r"[ \t]+\n", "\n", t)
            t = re.sub(r"\n{3,}", "\n\n", t)
            if t.strip():
                parts.append(t)
    text = "\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text, n_tables


# ────────────────────────────────── hwp → HTML ──────────────────────────────────

def _find_hwp5html_exe() -> str | None:
    """hwp5html 콘솔 스크립트를 찾는다. PATH 에 없어도 인터프리터 옆 Scripts/bin 을 본다."""
    exe = shutil.which("hwp5html")
    if exe:
        return exe
    names = ("hwp5html.exe", "hwp5html")
    cand_dirs = [
        os.path.join(sys.prefix, "Scripts"),   # Windows
        os.path.join(sys.prefix, "bin"),        # POSIX
        os.path.dirname(sys.executable),
        os.path.join(os.path.dirname(sys.executable), "Scripts"),
    ]
    for d in cand_dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


def _run_hwp5html(src: str, out_dir: str) -> None:
    """hwp5html 로 src 를 out_dir 에 변환. 콘솔 스크립트가 없으면 모듈로 호출."""
    exe = _find_hwp5html_exe()
    if exe:
        subprocess.run(
            [exe, "--output", out_dir, src],
            capture_output=True, timeout=240, creationflags=CREATE_NO_WINDOW,
        )
        return
    # 콘솔 스크립트를 못 찾으면 설치된 파이썬 모듈을 CLI 와 같은 진입점(main)으로 돌린다.
    code = (
        "import sys; from hwp5.hwp5html import main; "
        "sys.argv=['hwp5html','--output',sys.argv[1],sys.argv[2]]; main()"
    )
    subprocess.run(
        [sys.executable, "-I", "-c", code, out_dir, src],
        capture_output=True, timeout=240, creationflags=CREATE_NO_WINDOW,
    )


def _read_converted_html(out_dir: str) -> str:
    files = sorted(
        glob.glob(os.path.join(out_dir, "*.xhtml"))
        + glob.glob(os.path.join(out_dir, "*.html"))
    )
    chunks = []
    for f in files:
        with open(f, encoding="utf-8", errors="ignore") as fh:
            chunks.append(fh.read())
    return "\n".join(chunks)


def _have_pyhwp() -> bool:
    if _find_hwp5html_exe():
        return True
    try:
        import importlib.util
        return importlib.util.find_spec("hwp5.hwp5html") is not None
    except Exception:
        return False


def extract_hwp(src: str) -> tuple[str, int]:
    """hwp 경로 → (표 보존 텍스트, 표 개수). pyhwp 미설치 시 RuntimeError."""
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    if not _have_pyhwp():
        raise RuntimeError(INSTALL_HINT)
    tmp = tempfile.mkdtemp(prefix="hwp5_")
    try:
        out_dir = os.path.join(tmp, "o")
        _run_hwp5html(src, out_dir)
        html_text = _read_converted_html(out_dir)
        if not html_text.strip():
            raise RuntimeError(
                f"변환 결과가 비었습니다: {src}\n"
                "구형 .hwp(HWP 5.x OLE)인지 확인하세요. .hwpx(ZIP) 는 pyhwp 가 다룰 수 없습니다."
            )
        return html_to_preserved_text(html_text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ────────────────────────────────── CLI ──────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="구형 hwp 공고문에서 표(평가 배점)를 보존해 텍스트로 추출")
    ap.add_argument("hwp", help="입력 .hwp 경로")
    ap.add_argument("-o", "--output", help="출력 txt 경로 (생략 시 stdout)")
    ap.add_argument("--quiet", action="store_true", help="표 개수 요약을 stderr 로 내지 않음")
    args = ap.parse_args(argv)
    try:
        text, n_tables = extract_hwp(args.hwp)
    except (RuntimeError, FileNotFoundError) as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    if not args.quiet:
        print(f"[hwp_extract] {os.path.basename(args.hwp)}: 표 {n_tables}개, 본문 {len(text)}자", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
