#!/usr/bin/env python3
"""주기·위임 작업 실행 기록 한 줄 표준 (NVIDIA 인사이트 ①, 탐 N192).

페르소나가 직접 모는 작업은 proc.py run(start/done/skip, 증거 강제)이 이미 표준이다.
이 모듈은 그 빈틈 - 헤르메스 크론·백그라운드 스크립트·서브에이전트처럼 사람 손을
안 거치는 주기·위임 작업 - 의 실행을 "누가/입력/도구/결과·실패" 한 줄로 한곳
(C:/work/_ops/run_log.jsonl)에 남긴다. 신규 모니터링 도구가 아니라 기존 _ops 로그
자리에 공통 규격 한 줄을 얹는 것이다.

설계 원칙(비티·덱스 슈퍼리뷰 보강):
- 로깅 실패가 본 작업을 절대 멈추지 않는다(모든 쓰기를 try/except로 감싸고, 실패 시
  조용히 넘어간다 - 기록은 보조이지 본 작업의 전제가 아니다).
- 장기 가동 대비 파일 회전(기본 5MB 넘으면 run_log.1.jsonl 로 밀고 새로 시작, 백업 1개).

쓰는 법(둘 다 됨):
  # 파이썬에서
  from run_log import append
  append(who="hermes:todo-detector", task="todo 감지", tool="script",
         status="ok", result="3건 처리")
  # 셸·크론에서
  python scripts/ops/run_log.py log --who hermes:x --task "..." \
      --tool script --status ok --result "..."
읽기:
  python scripts/ops/run_log.py tail --n 20
  python scripts/ops/run_log.py query --who hermes:todo-detector --n 50
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# KST(+09:00) 고정 - 이 운영은 한국 시간 기준.
KST = timezone(timedelta(hours=9))

# 정본 위치. 환경변수로 시험 때 갈아끼울 수 있게.
DEFAULT_PATH = os.environ.get("RUN_LOG_PATH", r"C:\work\_ops\run_log.jsonl")
ROTATE_BYTES = int(os.environ.get("RUN_LOG_ROTATE_BYTES", str(5 * 1024 * 1024)))

_ALLOWED_STATUS = ("ok", "fail", "skip", "partial")


def _now_kst_iso():
    return datetime.now(KST).isoformat(timespec="seconds")


def build_entry(who, task, tool, status="ok", result="", at=None, extra=None):
    """실행 기록 한 줄(dict)을 만든다. 순수 함수(파일 접근 없음)라 시험 가능."""
    entry = {
        "ts": at or _now_kst_iso(),
        "who": str(who),           # 누가(헤르메스 작업 id·스크립트명·서브에이전트명)
        "task": str(task),         # 무엇을(한 줄)
        "tool": str(tool),         # 어떤 도구로(script·hermes·subagent·gh_workflow 등)
        "status": status if status in _ALLOWED_STATUS else "ok",
        "result": str(result),     # 결과·실패 요약 한 줄
    }
    if extra:
        # 예약 키를 덮어쓰지 않게 보호.
        for k, v in extra.items():
            if k not in entry:
                entry[k] = v
    return entry


def _rotate_if_needed(path, rotate_bytes=ROTATE_BYTES):
    """파일이 상한을 넘으면 .1 로 밀어 1개만 백업으로 남긴다. 실패해도 조용히 넘어감."""
    try:
        if rotate_bytes and os.path.exists(path) and os.path.getsize(path) >= rotate_bytes:
            backup = path + ".1"
            try:
                if os.path.exists(backup):
                    os.remove(backup)
            except OSError:
                pass
            os.replace(path, backup)
    except OSError:
        # 회전 실패는 본 기록을 막지 않는다.
        pass


def append(who, task, tool, status="ok", result="", path=None, at=None, extra=None,
           rotate_bytes=ROTATE_BYTES):
    """실행 한 줄을 run_log 에 append. 실패해도 예외를 올리지 않는다(True/False 반환)."""
    path = path or DEFAULT_PATH
    entry = build_entry(who, task, tool, status=status, result=result, at=at, extra=extra)
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        _rotate_if_needed(path, rotate_bytes)
        line = json.dumps(entry, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception:
        # 로깅은 보조다. 어떤 이유로든 실패하면 본 작업을 멈추지 않는다.
        return False


def _read_entries(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def _cmd_log(args):
    ok = append(args.who, args.task, args.tool, status=args.status, result=args.result,
                path=args.path)
    print("기록함" if ok else "기록 실패(본 작업엔 영향 없음)")
    return 0


def _cmd_tail(args):
    entries = _read_entries(args.path or DEFAULT_PATH)
    rows = entries[-args.n:]
    if not rows:
        print("기록 없음")
        return 0
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    for e in rows:
        print(f"{e.get('ts','?')} [{e.get('status','?')}] {e.get('who','?')} / "
              f"{e.get('task','?')} ({e.get('tool','?')}) :: {e.get('result','')}")
    return 0


def _cmd_query(args):
    entries = _read_entries(args.path or DEFAULT_PATH)
    if args.who:
        entries = [e for e in entries if e.get("who") == args.who]
    if args.status:
        entries = [e for e in entries if e.get("status") == args.status]
    rows = entries[-args.n:]
    if not rows:
        print("해당 기록 없음")
        return 0
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    for e in rows:
        print(f"{e.get('ts','?')} [{e.get('status','?')}] {e.get('who','?')} / "
              f"{e.get('task','?')} ({e.get('tool','?')}) :: {e.get('result','')}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="주기·위임 작업 실행 기록 한 줄 표준")
    p.add_argument("--path", default=None, help="run_log 경로(기본 RUN_LOG_PATH)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("log", help="실행 한 줄 기록")
    pl.add_argument("--who", required=True)
    pl.add_argument("--task", required=True)
    pl.add_argument("--tool", required=True)
    pl.add_argument("--status", default="ok", choices=_ALLOWED_STATUS)
    pl.add_argument("--result", default="")
    pl.set_defaults(func=_cmd_log)

    pt = sub.add_parser("tail", help="최근 N건 보기")
    pt.add_argument("--n", type=int, default=20)
    pt.add_argument("--json", action="store_true")
    pt.set_defaults(func=_cmd_tail)

    pq = sub.add_parser("query", help="who/status 로 거르기")
    pq.add_argument("--who", default=None)
    pq.add_argument("--status", default=None, choices=[*_ALLOWED_STATUS, None])
    pq.add_argument("--n", type=int, default=50)
    pq.add_argument("--json", action="store_true")
    pq.set_defaults(func=_cmd_query)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
