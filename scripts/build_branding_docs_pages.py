#!/usr/bin/env python3
"""퍼스널 브랜딩 가이드 · SNS 라이팅 가이드 스튜디오 페이지 생성기.

정본은 docs/퍼스널_브랜딩_가이드.md · docs/SNS_라이팅_가이드.md 둘이고,
insight-7b3e9f2c/personal-brand-guide.html · sns-writing-guide.html은 이
스크립트가 뽑아낸 사본이다. 정본 마크다운을 고쳤으면 이 스크립트를 다시
실행해 페이지를 갱신한 뒤 셋(마크다운 + 페이지 둘)을 같이 커밋한다 —
페이지를 손으로 고치면 다음 실행 때 되돌아간다. (scripts/build_llm_protocol_page.py
와 같은 패턴, STYLE_GUIDE.md ".doc 패턴" 절이 정본.)

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
KST = timezone(timedelta(hours=9))

# 이 세 페이지가 하나의 "브랜드" 묶음이다 -- 기존 brand-guide.html(2026-08-30,
# Simplifier 서비스 브랜드: 슬로건·에셋·카피 원칙)에 이 스크립트가 만드는 둘을
# .doc-nav로 엮는다. brand-guide.html은 정본 마크다운이 없는 손수 관리 페이지라
# 이 스크립트가 건드리지 않는다 -- .doc-nav 줄만 별도 커밋으로 맞춰 넣는다.
BUNDLE_NAV = [
    ("/insight-7b3e9f2c/brand-guide.html", "브랜드 가이드 (서비스)"),
    ("/insight-7b3e9f2c/personal-brand-guide.html", "퍼스널 브랜딩 가이드"),
    ("/insight-7b3e9f2c/sns-writing-guide.html", "SNS 라이팅 가이드"),
]

PAGES = [
    {
        "src": ROOT / "docs" / "퍼스널_브랜딩_가이드.md",
        "out": ROOT / "insight-7b3e9f2c" / "personal-brand-guide.html",
        "title": "퍼스널 브랜딩 가이드",
        "info": (
            "정본은 <code>docs/퍼스널_브랜딩_가이드.md</code>입니다. 이 페이지는 그 "
            "파일에서 스크립트가 자동 생성한 사본이라 직접 고치면 다음 실행 때 "
            "되돌아갑니다 — 정본을 고쳤으면 "
            "<code>scripts/build_branding_docs_pages.py</code>를 재실행해 페이지를 "
            "갱신한 뒤 같이 커밋하세요. 587편 전체 조사(2026-09-03)로 근거를 보강했습니다."
        ),
    },
    {
        "src": ROOT / "docs" / "SNS_라이팅_가이드.md",
        "out": ROOT / "insight-7b3e9f2c" / "sns-writing-guide.html",
        "title": "SNS 라이팅 가이드",
        "info": (
            "정본은 <code>docs/SNS_라이팅_가이드.md</code>입니다. 이 페이지는 그 "
            "파일에서 스크립트가 자동 생성한 사본이라 직접 고치면 다음 실행 때 "
            "되돌아갑니다 — 정본을 고쳤으면 "
            "<code>scripts/build_branding_docs_pages.py</code>를 재실행해 페이지를 "
            "갱신한 뒤 같이 커밋하세요."
        ),
    },
]

# .doc 패턴 정본은 STYLE_GUIDE.md "긴 마크다운 문서를 페이지로 렌더링할 때" 절.
# 이 폴더는 Jekyll 밖(include 불가)이라 스타일 블록을 페이지마다 품는다.
TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ - Simplifier</title>

<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="referrer" content="no-referrer">
<link rel="icon" type="image/png" href="/favicon-32x32.png" sizes="32x32">
<link rel="stylesheet" href="/insight-7b3e9f2c/studio.css">

<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css" rel="stylesheet">
<!-- Studio 메뉴 타이틀(h1)은 명조체 큰 제목으로 통일합니다. -->
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400&display=swap" rel="stylesheet">

<style>
  .doc{font-size:15px; line-height:1.75; color:var(--dim);}
  .doc > *:first-child{margin-top:0;}
  .doc h2{
    font-family:'Noto Serif KR',serif; font-weight:400; font-size:22px;
    color:var(--ink); margin:48px 0 14px; padding-top:22px; border-top:1px solid var(--line-soft);
  }
  .doc h2:first-of-type{margin-top:0; padding-top:0; border-top:none;}
  .doc h3{font-size:15.5px; font-weight:700; color:var(--ink); margin:26px 0 10px;}
  .doc p{margin:0 0 14px;}
  .doc ul, .doc ol{margin:0 0 14px; padding-left:22px;}
  .doc li{margin-bottom:6px;}
  .doc li > ul, .doc li > ol{margin-top:6px;}
  .doc strong{color:var(--ink); font-weight:700;}
  .doc a{color:var(--ink); text-decoration:underline; text-decoration-color:var(--line); text-underline-offset:2px;}
  .doc a:hover{text-decoration-color:var(--ink);}
  .doc code{
    font-family:ui-monospace,'SFMono-Regular',Menlo,monospace; font-size:0.88em;
    background:#f7f6f2; padding:1.5px 5px; border-radius:4px; color:var(--dim);
  }
  .doc pre{background:#f7f6f2; padding:14px 16px; border-radius:8px; overflow-x:auto; font-size:12.5px; line-height:1.6;}
  .doc pre code{background:none; padding:0;}
  .doc blockquote{
    margin:0 0 20px; padding:12px 18px; border-left:3px solid var(--line);
    background:#f7f6f2; border-radius:0 8px 8px 0; color:var(--dim); font-size:14px;
  }
  .doc blockquote p:last-child{margin-bottom:0;}
  .doc hr{border:none; border-top:1px solid var(--line-soft); margin:32px 0;}
  .doc .table-wrap{overflow-x:auto; margin:0 0 20px; border:1px solid var(--line-soft); border-radius:8px;}
  .doc table{border-collapse:collapse; width:100%; font-size:13px;}
  .doc th, .doc td{padding:9px 12px; border-bottom:1px solid var(--line-soft); text-align:left; vertical-align:top;}
  .doc th{background:#f7f6f2; font-weight:700; color:var(--ink); white-space:nowrap;}
  .doc tr:last-child td{border-bottom:none;}

  .doc-nav{display:flex; gap:8px; flex-wrap:wrap; margin:0 0 28px;}
  .doc-nav a{
    font-size:12.5px; font-weight:600; color:var(--dim); text-decoration:none;
    padding:6px 12px; border:1px solid var(--line); border-radius:999px;
  }
  .doc-nav a:hover{background:var(--line-soft);}
  .doc-nav a.current{background:var(--ink); color:#fff; border-color:var(--ink);}
</style>
</head>
<body class="has-shell-nav">
<nav id="adminShellNav"></nav>
<div class="wrap">
  <header>
    <h1>__TITLE__<button type="button" class="info-dot" aria-label="설명 보기">ⓘ<span class="info-text">__INFO__</span></button></h1>
    <span class="meta-text">자동 생성 __STAMP__</span>
  </header>
  <nav class="doc-nav">__DOCNAV__</nav>
  <article class="doc">
__BODY__
  </article>
</div>
<script src="/insight-7b3e9f2c/studio.js"></script>
</body>
</html>
"""


def render_docnav(current_href):
    parts = []
    for href, label in BUNDLE_NAV:
        cls = ' class="current"' if href == current_href else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    return "".join(parts)


def main():
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    for page in PAGES:
        text = page["src"].read_text(encoding="utf-8")
        text = re.sub(r"^# .*\n", "", text, count=1, flags=re.M)  # H1은 페이지 header가 담당
        body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
        body = body.replace("<table>", '<div class="table-wrap"><table>')
        body = body.replace("</table>", "</table></div>")
        current_href = "/insight-7b3e9f2c/" + page["out"].name
        html = (
            TEMPLATE
            .replace("__TITLE__", page["title"])
            .replace("__INFO__", page["info"])
            .replace("__STAMP__", stamp)
            .replace("__DOCNAV__", render_docnav(current_href))
            .replace("__BODY__", body)
        )
        page["out"].write_text(html, encoding="utf-8")
        print(f"OK -> {page['out'].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
