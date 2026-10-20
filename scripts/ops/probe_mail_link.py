#!/usr/bin/env python3
"""점검 계정(점검 계정 주소)으로 온 Carvit 로그인 링크를 읽어 표준출력에 한 개만 낸다(읽기 전용).

흐름: 사장님이 로그인 창에 점검 계정 주소 를 넣어 링크를 보낸다 -> 이 스크립트가 메일 Worker의
점검 읽기 경로(GET /mail?since=<ISO>, 전용 키)에서 최신 점검 메일을 받아 https://mcp.carvit.ai 링크만 뽑는다.

- 키: 환경 변수 PROBE_MAIL_READ_KEY(또는 MAIL_PROBE_READ_KEY), 없으면 헤르메스 설정 파일
  (%LOCALAPPDATA%/hermes/<점 env 파일>, 또는 --env-file)에서 그 두 이름만 찾아 읽는다. 값은 어디에도 출력하지 않는다.
- 주소: PROBE_MAIL_URL(기본 아래 DEFAULT_URL). 점검 메일은 Worker가 10분 뒤 지우므로 기본 --since 는 10분 전.
- 옵션: --code 최신 점검 메일 본문에서 6~8자리 숫자 인증 코드 한 개, --any-link 발신 도메인 무관 github.com 인증 링크 한 개(소셜 로그인 계정 가입 점검용).
- 종료 코드: 0 링크 출력, 2 아직 없음, 3 키 없음, 4 호출 실패(HTTP/네트워크).
- 링크는 일회용·점검 계정용이라 출력해도 되지만 로그 파일에는 남기지 않는다(이 스크립트는 로그를 쓰지 않는다).
"""
import argparse
import datetime
import html
import json
import os
import quopri
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "https://carvit-mail-inbox.simon-8be.workers.dev"
KEY_NAMES = ("PROBE_MAIL_READ_KEY", "MAIL_PROBE_READ_KEY")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"  # Cloudflare 403 회피
LINK_RE = re.compile(r"https://mcp\.carvit\.ai/[^\s\"'<>)\]]+")

GH_LINK_RE = re.compile(r"https://(?:www\.)?github\.com/[^\s\"'<>)\]]+")
CODE_RE = re.compile(r"(?<![\w#.\-/=%&?])(\d{6,8})(?![\w.\-/%])")
TAG_RE = re.compile(r"<(style|script)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)


def find_key(env_file=None):
    for n in KEY_NAMES:
        if os.environ.get(n):
            return os.environ[n].strip()
    path = env_file or os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "." + "env")
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and k.strip() in KEY_NAMES and v.strip():
                    return v.strip().strip("\"'")
    except OSError:
        pass
    return None


def fetch(base, key, since, opener=urllib.request.urlopen):
    url = f"{base.rstrip('/')}/mail?limit=20&since={urllib.parse.quote(since)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": UA, "Accept": "application/json"})
    with opener(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def extract_link(row):
    """한 메일에서 mcp.carvit.ai 링크 하나. 본문 -> 원문(quoted-printable 해독) 순서."""
    texts = [row.get("text_body") or "", row.get("html_body") or ""]
    raw = row.get("raw") or ""
    if raw:
        try:
            texts.append(quopri.decodestring(raw.encode("utf-8", "ignore")).decode("utf-8", "ignore"))
        except Exception:
            texts.append(raw)
    for t in texts:
        links = [html.unescape(m).rstrip(".,;") for m in LINK_RE.findall(html.unescape(t))]
        if links:
            # 로그인 확인 경로(콜백·토큰·코드가 붙은 것)를 먼저
            links.sort(key=lambda u: 0 if re.search(r"callback|token|code=|magic", u) else 1)
            return links[0]
    return None


def mail_texts(row):
    """한 메일의 본문 후보들(텍스트 -> 태그 뗀 HTML -> 해독한 원문)."""
    out = [row.get("text_body") or "", TAG_RE.sub(" ", html.unescape(row.get("html_body") or ""))]
    raw = row.get("raw") or ""
    if raw:
        try:
            out.append(quopri.decodestring(raw.encode("utf-8", "ignore")).decode("utf-8", "ignore"))
        except Exception:
            out.append(raw)
    return out


def extract_code(row):
    for t in mail_texts(row):
        m = CODE_RE.search(html.unescape(t))
        if m:
            return m.group(1)
    return None


def extract_any_link(row):
    """발신 도메인 무관, github.com 인증 링크 하나(verify/confirm/token 들어간 것 우선)."""
    texts = [row.get("text_body") or "", row.get("html_body") or ""]
    texts += mail_texts(row)[2:]
    for t in texts:
        links = [html.unescape(m).rstrip(".,;") for m in GH_LINK_RE.findall(html.unescape(t))]
        if links:
            links.sort(key=lambda u: 0 if re.search(r"verif|confirm|token|code=|launch", u, re.I) else 1)
            return links[0]
    return None


def latest_by(rows, fn):
    for row in sorted(rows, key=lambda r: r.get("received_at") or "", reverse=True):
        v = fn(row)
        if v:
            return v
    return None


def latest_link(rows):
    for row in sorted(rows, key=lambda r: r.get("received_at") or "", reverse=True):
        link = extract_link(row)
        if link:
            return link
    return None


def main(argv=None, opener=urllib.request.urlopen):
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", help="이 ISO 시각 뒤에 온 메일만(기본: 10분 전)")
    ap.add_argument("--env-file", help="키가 든 설정 파일(기본 헤르메스 설정)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--code", action="store_true", help="6~8자리 숫자 인증 코드 한 개를 출력")
    g.add_argument("--any-link", action="store_true", help="발신 도메인 무관 github.com 인증 링크 한 개를 출력")
    a = ap.parse_args(argv)
    key = find_key(a.env_file)
    if not key:
        print("키 없음: PROBE_MAIL_READ_KEY 를 환경 변수나 헤르메스 설정 파일에 두세요(카빗 패스 envput).", file=sys.stderr)
        return 3
    since = a.since or (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        rows = fetch(os.environ.get("PROBE_MAIL_URL", DEFAULT_URL), key, since, opener)
    except urllib.error.HTTPError as e:
        print(f"호출 실패: HTTP {e.code}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"호출 실패: {type(e).__name__}", file=sys.stderr)
        return 4
    rows = rows if isinstance(rows, list) else []
    if a.code:
        link = latest_by(rows, extract_code)
    elif a.any_link:
        link = latest_by(rows, extract_any_link)
    else:
        link = latest_link(rows)
    if not link:
        print("아직 없음", file=sys.stderr)
        return 2
    print(link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
