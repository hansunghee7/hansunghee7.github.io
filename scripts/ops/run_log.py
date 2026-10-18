#!/usr/bin/env python3
"""주기·위임 작업 실행 기록 한 줄 표준 (NVIDIA 인사이트 ①, 탐 N192).

페르소나가 직접 모는 작업은 proc.py run(start/done/skip, 증거 강제)이 이미 표준이다.
이 모듈은 그 빈틈 - 헤르메스 크론·백그라운드 스크립트·서브에이전트처럼 사람 손을
안 거치는 주기·위임 작업 - 의 실행을 "누가/입력/도구/결과·실패" 한 줄로 남긴다.
신규 모니터링 도구가 아니라 기존 _ops 로그 자리에 공통 규격 한 줄을 얹는 것이다.

설계 원칙(비티·덱스 슈퍼리뷰 보강):
- 로깅 실패가 본 작업을 절대 멈추지 않는다(모든 쓰기를 try/except로 감싸고, 실패 시
  조용히 넘어간다 - 기록은 보조이지 본 작업의 전제가 아니다).
- **날짜별 파일 분리**(run_log_YYYYMMDD.jsonl, KST): 파일 회전을 아예 없앤다.
  크론·서브에이전트가 동시에 돌아도 append 전용이라 회전 레이스로 로그가 유실될
  일이 없다(비티·덱스 둘 다 회전 동시성 유실을 지적 -> 회전 제거로 대응).
- 읽기(tail/query)는 그 디렉터리의 run_log*.jsonl 을 날짜 순으로 합쳐 본다.

쓰는 법(둘 다 됨):
  from run_log import append
  append(who="hermes:todo-detector", task="todo 감지", tool="script",
         status="ok", result="3건 처리")
  python scripts/ops/run_log.py log --who hermes:x --task "..." --tool script \
      --status ok --result "..."
읽기:
  python scripts/ops/run_log.py tail --n 20
  python scripts/ops/run_log.py query --who hermes:todo-detector --n 50
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

# KST(+09:00) 고정 - 이 운영은 한국 시간 기준.
KST = timezone(timedelta(hours=9))

# 로그가 쌓이는 디렉터리(날짜별 파일). 환경변수로 시험 때 갈아끼울 수 있게.
DEFAULT_DIR = os.environ.get("RUN_LOG_DIR", r"C:\work\_ops")
# 파일 접두어. 하루치 = <PREFIX>YYYYMMDD.jsonl
FILE_PREFIX = "run_log_"
FILE_GLOB = FILE_PREFIX + "*.jsonl"

_ALLOWED_STATUS = ("ok", "fail", "skip", "partial")


def _now_kst_iso():
    return datetime.now(KST).isoformat(timespec="seconds")


def _day_stamp(at=None):
    """기록 시각에서 KST 날짜(YYYYMMDD)를 뽑는다. at 없으면 지금."""
    if at:
        try:
            dt = datetime.fromisoformat(at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            dt = dt.astimezone(KST)
        except ValueError:
            dt = datetime.now(KST)
    else:
        dt = datetime.now(KST)
    return dt.strftime("%Y%m%d")


def _day_path(day_dir=None, at=None):
    return os.path.join(day_dir or DEFAULT_DIR, FILE_PREFIX + _day_stamp(at) + ".jsonl")


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
        for k, v in extra.items():
            if k not in entry:    # 예약 키 보호
                entry[k] = v
    return entry


def append(who, task, tool, status="ok", result="", path=None, day_dir=None,
           at=None, extra=None):
    """실행 한 줄을 그날 파일에 append. 실패해도 예외를 올리지 않는다(True/False).

    path 를 명시하면 그 파일에 바로 쓴다(시험·특수용). 아니면 day_dir(기본 DEFAULT_DIR)
    안의 그날 파일(run_log_YYYYMMDD.jsonl)에 쓴다. 회전 없음 -> 동시 실행 안전.
    """
    entry = build_entry(who, task, tool, status=status, result=result, at=at, extra=extra)
    target = path or _day_path(day_dir, at)
    try:
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False)
        with open(target, "a", encoding="utf-8") as f:
            f.write(line + "\n")      # append 전용: 동시 실행에도 줄 단위로 안전
        return True
    except Exception:
        # 로깅은 보조다. 어떤 이유로든 실패하면 본 작업을 멈추지 않는다.
        return False


def _read_one(path):
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


def read_entries(path=None, day_dir=None):
    """기록을 읽어 ts 순으로 돌려준다. path 명시면 그 파일만, 아니면 day_dir의
    run_log*.jsonl 전부를 날짜(파일명) 순으로 합친다."""
    if path:
        return _read_one(path)
    files = sorted(glob.glob(os.path.join(day_dir or DEFAULT_DIR, FILE_GLOB)))
    merged = []
    for fp in files:
        merged.extend(_read_one(fp))
    merged.sort(key=lambda e: e.get("ts", ""))
    return merged


def _print_rows(rows, as_json):
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for e in rows:
        print(f"{e.get('ts','?')} [{e.get('status','?')}] {e.get('who','?')} / "
              f"{e.get('task','?')} ({e.get('tool','?')}) :: {e.get('result','')}")


def _parse_date(value):
    """Parse a YYYY-MM-DD query boundary, with an argparse-friendly error."""
    try:
        if (not isinstance(value, str) or len(value) != 10
                or value[4] != "-" or value[7] != "-"):
            raise ValueError
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"invalid date {value!r}; expected YYYY-MM-DD"
        )


def filter_by_date(rows, since=None, until=None):
    """Keep rows whose ts calendar date falls within inclusive boundaries."""
    since = _parse_date(since) if isinstance(since, str) else since
    until = _parse_date(until) if isinstance(until, str) else until
    filtered = []
    for row in rows:
        ts = row.get("ts", "")
        try:
            row_date = date.fromisoformat(ts[:10])
        except (TypeError, ValueError):
            continue
        if since is not None and row_date < since:
            continue
        if until is not None and row_date > until:
            continue
        filtered.append(row)
    return filtered


def _cmd_log(args):
    ok = append(args.who, args.task, args.tool, status=args.status, result=args.result,
                path=args.path, day_dir=args.dir)
    print("기록함" if ok else "기록 실패(본 작업엔 영향 없음)")
    return 0


def _cmd_tail(args):
    rows = read_entries(path=args.path, day_dir=args.dir)[-args.n:]
    if not rows:
        print("기록 없음")
        return 0
    _print_rows(rows, args.json)
    return 0


def _cmd_query(args):
    rows = read_entries(path=args.path, day_dir=args.dir)
    rows = filter_by_date(rows, args.since, args.until)
    if args.who:
        rows = [e for e in rows if e.get("who") == args.who]
    if args.status:
        rows = [e for e in rows if e.get("status") == args.status]
    rows = rows[-args.n:]
    if not rows:
        print("해당 기록 없음")
        return 0
    _print_rows(rows, args.json)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="주기·위임 작업 실행 기록 한 줄 표준")
    p.add_argument("--path", default=None, help="특정 파일 직접 지정(기본은 날짜별 파일)")
    p.add_argument("--dir", default=None, help="로그 디렉터리(기본 RUN_LOG_DIR)")
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
    pq.add_argument("--since", type=_parse_date, default=None, metavar="YYYY-MM-DD",
                    help="포함할 시작 날짜")
    pq.add_argument("--until", type=_parse_date, default=None, metavar="YYYY-MM-DD",
                    help="포함할 마지막 날짜")
    pq.add_argument("--n", type=int, default=50)
    pq.add_argument("--json", action="store_true")
    pq.set_defaults(func=_cmd_query)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
