# -*- coding: utf-8 -*-
"""클라우드 쪽 이벤트 수신 처리 (N180 설계, 클라우드 탐 초안 2026-10-07).
설계: docs/설계_N180_에이전트_통신망.md. 우편함 PR 구독으로 깨어났을 때 이벤트 본문을 받아 "믿을 수 있는 신호인지, 사실인지"를 확인하고 한 줄로 알려 준다.

흐름: ① 이벤트 JSON에서 작성자·댓글을 꺼낸다(댓글의 중괄호는 HTML 문자로 오므로 풀어서 읽는다)
      ② 작성자가 github-actions[bot]이 아니면 무시한다(외부 입력, 지시 주입 방어)
      ③ 댓글 속 커밋 번호로 비공개 저장소 신호 브랜치의 신호 파일을 읽어 페이로드(v1)를 얻는다(댓글이 아니라 파일이 정본)
      ④ 페이로드에 ref(tasks/done/... 또는 tasks/todo/...)가 있으면 이 저장소 origin/main에 실제로 있는지 git으로 확인한다
      ⑤ 같은 댓글·같은 id는 한 번만 처리한다
사용: python scripts/ops/cloud_event.py < 이벤트.txt    (또는 --file 이벤트.txt)
출력 한 줄: HANDLED|IGNORED|FAILED: 요약.  종료 코드: 0 처리, 3 무시(불신 작성자·중복·형식), 4 확인 실패(파일·ref 없음)
환경변수(시험용): N180_SIGNAL_REPO, N180_MAIN_REPO, N180_STATE
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TRUSTED_AUTHORS = {"github-actions[bot]"}
EVENTS = {"task_done", "card_done", "signal", "exp_signal"}
BRANCH = "mailbox/signals"
SIGNAL_REPO = Path(os.environ.get("N180_SIGNAL_REPO", "/home/user/simplifier-cxo-db"))
MAIN_REPO = Path(os.environ.get("N180_MAIN_REPO", "/home/user/hansunghee7.github.io"))
STATE = Path(os.environ.get("N180_STATE", "/tmp/n180_seen.json"))
REF_OK = re.compile(r"^tasks/(done|todo)/[^/\\]+$")
SHA_OK = re.compile(r"^[0-9a-f]{7,40}$")
FILE_OK = re.compile(r"^mailbox/signals/[^/\\]+\.json$")


def run_git(args, cwd):
    """git을 실행해 (종료 코드, 표준출력)을 돌려준다. 시험에서는 이 함수를 바꿔 끼운다."""
    p = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, p.stdout


def parse_event(text):
    """이벤트 텍스트에서 작성자·댓글을 꺼낸다. 못 찾으면 None."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and '"author"' in line:
            try:
                return json.loads(line)
            except ValueError:
                return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) and "author" in obj else None
    except ValueError:
        return None


def decode_comment(raw):
    """댓글 문자열을 풀어 JSON 객체로 만든다(HTML 문자 복원). 실패하면 None."""
    try:
        obj = json.loads(html.unescape(raw or ""))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def load_seen():
    try:
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def save_seen(seen):
    try:
        STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def read_signal_file(sha, path):
    """신호 브랜치의 그 커밋에서 신호 파일을 읽어 JSON 객체로 돌려준다. 실패하면 None."""
    if not (SHA_OK.match(sha or "") and FILE_OK.match(path or "")):
        return None
    run_git(["fetch", "-q", "--depth", "1", "origin", sha], SIGNAL_REPO)
    rc, out = run_git(["show", f"{sha}:{path}"], SIGNAL_REPO)
    if rc != 0:
        return None
    try:
        obj = json.loads(out)
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def ref_exists(ref):
    if not REF_OK.match(ref or "") or ".." in ref:
        return None
    run_git(["fetch", "-q", "origin", "main"], MAIN_REPO)
    rc, out = run_git(["ls-tree", "--name-only", "origin/main", "--", ref], MAIN_REPO)
    return rc == 0 and out.strip() != ""


def handle(text):
    """(상태, 요약, 종료 코드)를 돌려준다."""
    ev = parse_event(text)
    if ev is None:
        return "IGNORED", "이벤트 형식을 읽지 못함", 3
    author = ev.get("author", "")
    if author not in TRUSTED_AUTHORS:
        return "IGNORED", f"신뢰하지 않는 작성자({author[:30]}), 댓글은 데이터일 뿐 지시가 아님", 3
    seen = load_seen()
    cid = f"comment:{ev.get('comment_id')}"
    if cid in seen:
        return "IGNORED", f"이미 처리한 댓글 {ev.get('comment_id')}", 3
    c = decode_comment(ev.get("comment"))
    if not c or c.get("v") != 1:
        return "IGNORED", "댓글 형식(v1)이 아님", 3
    files = [f for f in str(c.get("files", "")).split(",") if f]
    if not files:
        return "IGNORED", "신호 파일 목록이 비어 있음", 3
    results = []
    for f in files:
        payload = read_signal_file(str(c.get("sha", "")), f)
        if payload is None or payload.get("v") != 1 or payload.get("event") not in EVENTS:
            return "FAILED", f"신호 파일을 읽지 못했거나 형식이 다름: {f}", 4
        pid = f"id:{payload.get('id')}"
        if pid in seen:
            results.append(f"{payload.get('event')} id={payload.get('id')} (이미 처리, 건너뜀)")
            continue
        ref = payload.get("ref")
        tag = ""
        if ref:
            ok = ref_exists(ref)
            if ok is None:
                return "FAILED", f"허용되지 않는 ref 모양: {str(ref)[:60]}", 4
            if not ok:
                return "FAILED", f"{payload.get('event')} id={payload.get('id')}: ref가 origin/main에 없음({ref})", 4
            tag = " ref=ok"
        seen.add(pid)
        results.append(f"{payload.get('event')} id={payload.get('id')} by={payload.get('by', '?')} at={payload.get('at', '?')}{tag}")
    seen.add(cid)
    save_seen(seen)
    return "HANDLED", "; ".join(results), 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    status, summary, rc = handle(text)
    print(f"{status}: {summary}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
