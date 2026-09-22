#!/usr/bin/env python3
r"""drive_fetch_local.py: 구글 드라이브 파일을 클로드 컨텍스트에 직접 읽어들이지 않고,
전용 캐시 폴더로 복사한 뒤 로컬 LLM(Ollama)에게 요약시킨다.

배경(탐, 2026-09-22, 사장님 지시): Drive MCP(`read_file_content`)로 직접 읽으면 건당
평균 15,754자(4일 실측, 단건 최대 43K자)가 클로드 컨텍스트에 그대로 들어간다. 이 스크립트는
그 대신 (1) 구글 드라이브 데스크톱이 로컬에 동기화해 둔 G: 드라이브에서 파일을 전용 폴더로
복사하고, (2) 텍스트를 뽑아 로컬 Ollama 모델에게 요약을 시키고, (3) 요약 결과만 파일로 남긴다.
클로드는 이 스크립트의 표준출력(경로·글자수 요약)만 보고, 원문·요약 전문은 필요할 때 그 파일을
직접 연다.

⚠️ 전용 캐시 폴더만 쓴다(사장님 지시: 다운로드 폴더를 사장님 작업장으로 혼란스럽게 만들지 말 것).
기본 위치는 C:\work\_ops\drive-cache\이고, 사장님의 다운로드 폴더나 바탕화면에는 쓰지 않는다.

한계(정직하게 기록): 원본이 진짜 파일(.pdf/.docx/.txt/.md)일 때만 된다. 네이티브 구글 문서
(.gdoc/.gsheet/.gslides)는 G:\ 드라이브에 자리표시자만 있고 실제 내용이 없을 수 있어(오프라인
사용 설정 여부에 따라 다름) 이 스크립트는 그 경우를 지원 안 함으로 정직하게 보고하고 멈춘다
(내보내기가 필요하면 Drive API 별도 작업, 이번 범위 밖).

사용:
  python drive_fetch_local.py "<G: 드라이브 밑 경로 또는 절대경로>" [--model qwen2.5:32b]
                              [--prompt "요약 지시문"] [--max-chars 60000]
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

DRIVE_ROOT = Path(r"G:\내 드라이브")
CACHE_DIR = Path(r"C:\work\_ops\drive-cache")
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:32b"
DEFAULT_PROMPT = (
    "다음은 회사 문서 원문이다. 무엇에 관한 문서인지, 핵심 내용을 한국어로 6~10문장으로 "
    "요약해라. 숫자·날짜·금액은 원문 그대로 옮기고 추측하지 마라. 문서에 없는 내용은 "
    "지어내지 마라."
)
NATIVE_GOOGLE_EXT = {".gdoc", ".gsheet", ".gslides", ".gform", ".gscript"}
SUPPORTED_EXT = {".pdf", ".docx", ".txt", ".md"}


def resolve_source(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p
    candidate = DRIVE_ROOT / raw
    if candidate.exists():
        return candidate
    sys.exit(f"[오류] 원본을 찾지 못함: {raw} (절대경로도, G:\\내 드라이브 밑 경로도 아님)")


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == ".docx":
        import docx
        d = docx.Document(str(path))
        return "\n".join(para.text for para in d.paragraphs)
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    sys.exit(f"[오류] 지원 안 하는 형식: {ext} (지원: {sorted(SUPPORTED_EXT)})")


def ollama_generate(model: str, prompt: str, text: str, max_chars: int, timeout: int) -> str:
    body = json.dumps({
        "model": model,
        "prompt": f"{prompt}\n\n--- 문서 원문 ---\n{text[:max_chars]}",
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="G:\\ 드라이브 밑 상대경로 또는 절대경로")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--max-chars", type=int, default=60000)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    src = resolve_source(args.source)
    if src.suffix.lower() in NATIVE_GOOGLE_EXT:
        sys.exit(f"[지원 안 함] {src.name}은 네이티브 구글 문서라 G:\\ 드라이브에 실제 "
                 f"내용이 없을 수 있다. 이 스크립트 범위 밖(Drive API 내보내기 필요).")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cached = CACHE_DIR / f"{stamp}_{src.name}"
    shutil.copy2(src, cached)

    t0 = time.time()
    text = extract_text(cached)
    extract_sec = round(time.time() - t0, 1)
    if not text.strip():
        sys.exit(f"[오류] 텍스트 추출 결과가 비어있음: {cached}")

    t1 = time.time()
    summary = ollama_generate(args.model, args.prompt, text, args.max_chars, args.timeout)
    gen_sec = round(time.time() - t1, 1)

    summary_path = cached.with_suffix(cached.suffix + ".summary.md")
    summary_path.write_text(
        f"# {src.name} 로컬 요약 (모델: {args.model})\n\n"
        f"원본: {src}\n원문 글자수: {len(text)}자 (요약에 넣은 것: {min(len(text), args.max_chars)}자)\n\n"
        f"---\n\n{summary}\n",
        encoding="utf-8",
    )

    print(f"원본: {src}")
    print(f"캐시 복사본: {cached} ({cached.stat().st_size}바이트)")
    print(f"추출 텍스트: {len(text)}자 ({extract_sec}초)")
    print(f"로컬 요약({args.model}, {gen_sec}초): {summary_path} ({len(summary)}자)")


if __name__ == "__main__":
    main()
