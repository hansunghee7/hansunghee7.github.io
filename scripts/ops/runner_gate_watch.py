"""자체 실행기(goosolar) job 시작 게이트 관측 (읽기 전용).

job_started.sh 훅이 메모리 부족·크레딧 리셋 창으로 job을 거절('30분 대기 뒤 포기')해도
runner_watch.py는 online만 보므로 못 본다. 이 도구는 훅 로그를 읽어 그 사각지대를 한 줄로 보여준다.
관측 전용: 어떤 경우에도 exit 0, 우회 로직(runner_watch.py)은 건드리지 않는다.
"""
import re
import subprocess
import sys
from datetime import datetime, timedelta

LOG_CMD = "tail -200 ~/actions-runner/_diag/job_gate.log"
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$")
GIVEUP_MARK = "30분 대기 뒤 포기"
WAITING_WINDOW = timedelta(minutes=2)
GIVEUP_WINDOW = timedelta(hours=6)


def _parse_line(line: str):
    m = TS_RE.match(line.strip())
    if not m:
        return None
    try:
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return ts, m.group(2)


def parse_gate_log(lines: list[str], now: datetime) -> dict:
    """로그 줄과 기준 시각만으로 판정한다(네트워크 없음)."""
    last_outcome = "없음"
    last_time = None
    last_ts = None
    giveup = 0
    for line in lines:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        ts, body = parsed
        if GIVEUP_MARK in body:
            outcome = "포기"
            if now - GIVEUP_WINDOW <= ts <= now:
                giveup += 1
        elif body.startswith("통과"):
            outcome = "통과"
        elif body.startswith("대기"):
            outcome = "대기중"
        else:
            continue
        last_outcome = outcome
        last_ts = ts
        last_time = ts.strftime("%Y-%m-%d %H:%M:%S")
    if last_outcome == "대기중" and not (timedelta(0) <= now - last_ts <= WAITING_WINDOW):
        # 마지막이 오래된 '대기'는 진행 중이 아님: 종료 기록이 없는 상태로 본다
        last_outcome = "없음"
    return {"last_outcome": last_outcome, "last_time": last_time, "giveup_6h": giveup}


def summarize(result: dict) -> str:
    when = result["last_time"][:16] if result["last_time"] else "-"
    return f"게이트: 마지막={result['last_outcome']}({when}), 최근6h 포기 {result['giveup_6h']}건"


def fetch_lines() -> list[str]:
    proc = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", "goosolar", LOG_CMD],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip()[:120] or f"ssh exit {proc.returncode}")
    return proc.stdout.splitlines()


def main() -> int:
    try:
        lines = fetch_lines()
        print(summarize(parse_gate_log(lines, datetime.now())))
    except subprocess.TimeoutExpired:
        print("게이트 조회 실패: ssh 30초 시간 초과")
    except Exception as exc:  # 관측 전용: 어떤 실패도 붉음을 만들지 않는다
        print(f"게이트 조회 실패: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
