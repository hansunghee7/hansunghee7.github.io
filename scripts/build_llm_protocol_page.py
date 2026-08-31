#!/usr/bin/env python3
"""멀티 LLM 협업 규약 페이지 생성기.

정본은 .claude/skills/multi-llm-handoff/SKILL.md 하나뿐이고,
insight-7b3e9f2c/llm-protocol.html은 이 스크립트가 뽑아낸 사본이다.
SKILL.md를 고쳤으면 이 스크립트를 다시 실행해 페이지를 갱신한 뒤
둘을 같이 커밋한다 — 페이지를 손으로 고치면 다음 실행 때 되돌아간다.

필요 패키지: pip install markdown
"""

import pathlib
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    import markdown
except ImportError:
    sys.exit("python -m pip install markdown 후 다시 실행하세요.")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / ".claude" / "skills" / "multi-llm-handoff" / "SKILL.md"
OUT = ROOT / "insight-7b3e9f2c" / "llm-protocol.html"
KST = timezone(timedelta(hours=9))

# .doc 패턴 정본은 STYLE_GUIDE.md "긴 마크다운 문서를 페이지로 렌더링할 때" 절.
# 이 폴더는 Jekyll 밖(include 불가)이라 스타일 블록을 페이지마다 품는다.
TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>멀티 LLM 협업 규약 - Simplifier</title>

<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="referrer" content="no-referrer">
<link rel="icon" type="image/png" href="/favicon-32x32.png" sizes="32x32">
<link rel="stylesheet" href="/insight-7b3e9f2c/studio.css">

<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
  .doc{font-size:15px; line-height:1.75; color:var(--dim);}
  .doc > *:first-child{margin-top:0;}
  .doc h2{
    font-family:'Pretendard Variable',sans-serif; font-size:21px; font-weight:700;
    color:var(--ink); margin:40px 0 14px; padding-top:22px; border-top:1px solid var(--line-soft);
  }
  .doc h2:first-of-type{margin-top:0; padding-top:0; border-top:none;}
  .doc h3{font-size:16.5px; font-weight:700; color:var(--ink); margin:28px 0 10px;}
  .doc h4{font-size:14px; font-weight:700; color:var(--dim); margin:20px 0 8px;}
  .doc p{margin:0 0 14px;}
  .doc ul, .doc ol{margin:0 0 14px; padding-left:22px;}
  .doc li{margin-bottom:6px;}
  .doc li > ul, .doc li > ol{margin-top:6px;}
  .doc strong{color:var(--ink); font-weight:700;}
  .doc a{color:var(--ink); text-decoration:underline; text-decoration-color:var(--line); text-underline-offset:2px;}
  .doc a:hover{text-decoration-color:var(--ink);}
  .doc code{
    font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:12.5px;
    background:var(--line-soft); padding:1px 6px; border-radius:4px; color:var(--dim);
  }
  .doc pre{background:var(--line-soft); padding:14px 16px; border-radius:8px; overflow-x:auto; font-size:12.5px; line-height:1.6;}
  .doc pre code{background:none; padding:0;}
  .doc blockquote{
    margin:0 0 20px; padding:12px 18px; border-left:3px solid var(--line);
    background:var(--line-soft); border-radius:0 8px 8px 0; color:var(--dim); font-size:14px;
  }
  .doc blockquote p:last-child{margin-bottom:0;}
  .doc hr{border:none; border-top:1px solid var(--line-soft); margin:32px 0;}
  .doc .table-wrap{overflow-x:auto; margin:0 0 20px; border:1px solid var(--line-soft); border-radius:8px;}
  .doc table{border-collapse:collapse; width:100%; font-size:13px;}
  .doc th, .doc td{padding:9px 12px; border-bottom:1px solid var(--line-soft); text-align:left; vertical-align:top;}
  .doc th{background:#f7f6f2; font-weight:700; color:var(--ink); white-space:nowrap;}
  .doc tr:last-child td{border-bottom:none;}
</style>
</head>
<body class="has-shell-nav">
<nav id="adminShellNav"></nav>
<div class="wrap">
  <header>
    <h1>멀티 LLM 협업 규약<button type="button" class="info-dot" aria-label="설명 보기">ⓘ<span class="info-text">정본은 <code>.claude/skills/multi-llm-handoff/SKILL.md</code>입니다. 이 페이지는 그 파일에서 스크립트가 자동 생성한 사본이라 직접 고치면 다음 실행 때 되돌아갑니다 — 정본을 고쳤으면 <code>scripts/build_llm_protocol_page.py</code>를 재실행해 페이지를 갱신한 뒤 같이 커밋하세요.</span></button></h1>
    <span class="meta-text">자동 생성 __STAMP__</span>
  </header>
  <article class="doc">
__BODY__
  </article>
</div>
<script src="/insight-7b3e9f2c/studio.js"></script>
</body>
</html>
"""


def main():
    text = SRC.read_text(encoding="utf-8")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)  # 프론트매터 제거
    text = re.sub(r"^# .*\n", "", text, count=1, flags=re.M)  # H1은 페이지 header가 담당
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = body.replace("<table>", '<div class="table-wrap"><table>')
    body = body.replace("</table>", "</table></div>")
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    html = TEMPLATE.replace("__STAMP__", stamp).replace("__BODY__", body)
    OUT.write_text(html, encoding="utf-8")
    print(f"OK -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
