#!/usr/bin/env python3
"""PreToolUse 훅: 더빙 읽기 대본이 사장님께 가는 아티팩트에 섞이면 발행을 막는다(사장님 지시 2026-10-10, 핏 사고).

사고(2026-10-10 핏): lf05 음성 컨펌 페이지에 '삼 박 사 일', '일 초', '이십 도'처럼 동호가 읽는 한글 숫자 대본이 그대로 보였다
(정본 대본 subtitle.txt 변환 실패 + 페이지가 읽기 대본 줄을 씀). 규칙 문서만으로는 반복돼(CLAUDE#4e7b) 발행 경계에서 기계가 막는다.
규칙: Artifact 발행 파일(.html·.md·.txt·.json)에 ① 정본과 다른 읽기 대본 줄이 그대로 있거나 ② '일 점 팔 퍼센트'·'삼 박 사 일'·'이십 킬로그램' 같은
한글 숫자+단위가 있으면 막는다. 검사는 shorts-lab/tools/factory/reading_leak_guard.py(페이지 생성기와 같은 코드)를 쓴다.
통과: 환경변수 READING_GATE=off. 입력: stdin JSON. 막을 때 exit 2 + stderr."""
import json, os, sys

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, r"C:\work\shorts-lab\tools\factory")


def main():
    if os.environ.get("READING_GATE") == "off":
        return 0
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0
    if d.get("tool_name") != "Artifact":
        return 0
    inp = d.get("tool_input") or {}
    paths = []
    if inp.get("file_path"):
        paths.append(inp["file_path"])
    files = inp.get("files")
    if isinstance(files, dict):
        for v in files.values():
            if isinstance(v, str):
                paths.append(v)
            elif isinstance(v, dict) and v.get("from"):
                paths.append(v["from"])
    elif isinstance(files, list):
        paths += [x.get("path") for x in files if isinstance(x, dict) and x.get("path")]
    try:
        from reading_leak_guard import scan_text
    except Exception:
        return 0
    for p in paths:
        if not str(p).lower().endswith((".html", ".htm", ".md", ".txt", ".json")):
            continue
        try:
            text = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        hits = scan_text(text)
        if hits:
            sys.stderr.write("[읽기 대본 격리 관문] 더빙 읽기 대본이 사장님께 가는 화면에 섞였습니다: %s\n  %s\n"
                             "정본 대본(subtitle.txt, 아라비아 숫자)만 보여야 합니다. subtitle.txt를 고친 뒤 페이지를 다시 만들어 발행하세요"
                             "(핏-음성 #13). 도구: tools/factory/reading_leak_guard.py <파일>\n" % (p, "; ".join(str(h) for h in hits[:4])))
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
