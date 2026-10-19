#!/usr/bin/env python3
"""점검 계정 로그인 저장본 도구(N139, 사장님 10/20 공정자산 1순위).

왜: 지투가 로그인 후 화면(R-131~133 등)을 캡처할 때마다 사장님이 직접 로그인한 화면 한 장에 기댔다. 로그인 상태(쿠키 등)를 Playwright storage state로 한 번 저장해 두면
에이전트가 헤드리스로 로그인 후 화면을 사람 없이 열 수 있다. 저장은 사람이 진짜 로그인하는 1회(탐지 회피 도구는 안 씀, scripts/sns/playwright_login.py와 같은 원칙),
이후 `check`가 세션이 살아 있는지 매번 확인하고, 만료되면 종료 코드 3으로 알려 사람 1회만 다시 부른다.

사용:
  python scripts/ops/login_state.py save  <이름> <로그인 주소>            # 창이 뜨면 점검 계정으로 로그인, 끝나면 신호 파일 생성(아래)
  python scripts/ops/login_state.py check <이름> <로그인 후 주소> [--expect 글자] [--shot 경로.png]
  python scripts/ops/login_state.py status                                 # 저장본 목록과 나이

저장 위치: C:/work/_ops/login_state/<이름>.json (저장소 밖, git 대상 아님). 값은 화면·로그에 찍지 않는다.
save 신호: C:/work/_ops/login_state/.ready_<이름> 파일이 생기면 저장한다(최대 10분).
종료 코드: 0 정상, 2 사용법·저장본 없음, 3 세션 만료(로그인 화면으로 밀림 또는 기대 글자 없음), 4 실행 오류.
"""
import argparse
import json
import sys
import time
from pathlib import Path

STATE_DIR = Path("C:/work/_ops/login_state")
LOGIN_HINTS = ("login", "signin", "sign-in", "sign_in")
LOGIN_HOSTS = ("accounts.google.com", "login.microsoftonline.com", "appleid.apple.com")
import re  # noqa: E402
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


def state_path(name, base=STATE_DIR):
    # 이름은 영소문자·숫자·밑줄·하이픈만(비티·덱스 리뷰 10/20: 경로 이탈 문자로 저장 폴더 밖 파일을 만들거나 지우지 못하게)
    if not NAME_RE.match(name or ""):
        raise ValueError("이름은 영소문자·숫자·_·-만, 40자 이내")
    return Path(base) / f"{name}.json"


def looks_like_login(final_url, text, expect=None):
    """만료 판정: 로그인 화면(주소의 경로 마디나 로그인 호스트)으로 밀렸거나, 기대 글자가 주어졌는데 없으면 만료.
    기대 글자가 있어도 주소가 로그인 화면이면 만료다(리뷰 반영: 로그인 화면 본문에 기대 글자가 우연히 있어도 통과시키지 않는다)."""
    from urllib.parse import urlparse
    pu = urlparse(final_url or "")
    host = (pu.hostname or "").lower()
    segs = [s for s in pu.path.lower().split("/") if s]
    on_login = host in LOGIN_HOSTS or any(s in LOGIN_HINTS for s in segs)
    if expect and expect not in (text or ""):
        return True
    return bool(on_login)


def age_days(path):
    try:
        return round((time.time() - Path(path).stat().st_mtime) / 86400, 1)
    except OSError:
        return None


def cmd_status(base=STATE_DIR):
    rows = []
    for p in sorted(Path(base).glob("*.json")):
        rows.append({"name": p.stem, "age_days": age_days(p), "bytes": p.stat().st_size})
    print(json.dumps(rows, ensure_ascii=False))
    return 0


def cmd_save(name, url, base=STATE_DIR, timeout=600):
    from playwright.sync_api import sync_playwright
    Path(base).mkdir(parents=True, exist_ok=True)
    ready = Path(base) / f".ready_{name}"
    ready.unlink(missing_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        ctx.new_page().goto(url)
        print(f"[{name}] 창에서 점검 계정으로 직접 로그인하세요. 끝나면 {ready} 파일이 생기게 해 주세요(최대 {timeout}초).")
        waited = 0
        while not ready.exists() and waited < timeout:
            time.sleep(2)
            waited += 2
        if not ready.exists():
            print("시간 초과, 저장 안 함")
            browser.close()
            return 2
        ready.unlink(missing_ok=True)
        ctx.storage_state(path=str(state_path(name, base)))
        browser.close()
    print("저장 완료(값은 출력하지 않음):", state_path(name, base).name)
    return 0


def cmd_check(name, url, expect=None, shot=None, base=STATE_DIR):
    sp = state_path(name, base)
    if not sp.exists():
        print(f"저장본 없음: {sp.name} (먼저 save)", file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=str(sp))
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=45000)
            text = page.inner_text("body")
            final = page.url
            if looks_like_login(final, text, expect):
                browser.close()
                print(f"세션 만료로 보임: 최종 주소 {final.split('?')[0]}, 저장본 나이 {age_days(sp)}일", file=sys.stderr)
                return 3
            if shot:  # 로그인 화면(개인정보 노출 가능)은 찍지 않는다: 통과한 뒤에만(리뷰 반영)
                page.screenshot(path=shot, full_page=True)
            if not expect:
                print("※ --expect 없이는 접근 거부·오류 화면도 정상으로 볼 수 있음(주소만 판정). 화면에만 나오는 글자를 --expect로 주세요.", file=sys.stderr)
            ctx.storage_state(path=str(sp))  # 갱신된 쿠키를 다시 저장
            browser.close()
    except Exception as e:  # noqa: BLE001
        print(f"실행 오류: {type(e).__name__}", file=sys.stderr)
        return 4
    print(f"정상: 로그인 후 화면 확인, 저장본 갱신(나이 0일), 최종 주소 {final.split('?')[0]}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("save")
    s.add_argument("name")
    s.add_argument("url")
    c = sub.add_parser("check")
    c.add_argument("name")
    c.add_argument("url")
    c.add_argument("--expect")
    c.add_argument("--shot")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "save":
        return cmd_save(a.name, a.url)
    return cmd_check(a.name, a.url, a.expect, a.shot)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
