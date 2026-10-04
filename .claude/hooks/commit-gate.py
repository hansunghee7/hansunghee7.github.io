#!/usr/bin/env python3
"""Stop 훅: "진행하겠습니다"라고만 말하고 실제로는 아무것도 안 도는 답변을 막는다(사장님 지시 2026-10-04, 핏 사고).

사고(2026-10-04 핏): 보고마다 "핏이 진행합니다"로 끝냈지만 그 시각 구PC·신PC에서 도는 작업이 없었다.
원인은 세 가지다. ① 약속 문장에 증거 칸이 없다. ② 세션은 대화 턴 사이에 스스로 움직이지 못해,
백그라운드 작업을 걸지 않은 약속은 곧 정지다. ③ 보고 양식의 "정하실 것 없음, 탐이 진행"이 약속을 기본값으로 만들었다.

규칙: 마지막 답변에 앞으로의 행동 약속(진행합니다·하겠습니다·시작합니다 등)이 있으면 둘 중 하나가 있어야 통과한다.
  (A) [지금 돌고 있는 것: <무엇, 로그나 작업 위치>] — 그리고 이번 턴에 실제로 실행을 걸었어야 한다
      (Bash run_in_background, Monitor, nohup·ssh로 시작, 예약 도구) 또는 태그 안의 로컬 로그 경로가 최근 15분 안에 갱신됐어야 한다.
  (B) [실행 대기: <이유와 풀리는 시각·조건>] — 아무것도 안 돌고 있음을 솔직히 밝히는 표지.
입력: stdin JSON(Claude Code Stop 훅 규격). 출력: 위반이면 exit 2 + stderr 지침, stop_hook_active면 통과.
"""
import json
import os
import re
import sys
import time

# 앞으로의 행동 약속. "~했습니다"(과거)·"~하지 않겠습니다"(부정)는 잡지 않는다.
PROMISE = re.compile(
    r"(?<![가-힣])(진행(합니다|하겠습니다)|착수(합니다|하겠습니다)|시작(합니다|하겠습니다)|"
    r"(구현|실행|만들|돌리|확인|점검|적용|고치|올리|넣|정리|처리|재개|재시험|시험)(하)?겠습니다|"
    r"(바로|곧|이어서|지금)\s*(하겠|합니다|진행|시작))"
)
NEGATED = re.compile(r"(하지|않|못)\s*[^.\n]{0,6}(겠습니다)")
TAG_RUN = re.compile(r"\[지금 돌고 있는 것:\s*([^\]]+)\]")
TAG_WAIT = re.compile(r"\[실행 대기:\s*[^\]]{4,}\]")
LAUNCH_HINT = re.compile(r"nohup|setsid|\bat\s+now|schtasks|Start-Process|run_in_background|crontab|CronCreate|ScheduleWakeup")


def load_turn(path):
    """마지막 '진짜' 사용자 발화 이후의 어시스턴트 텍스트와 도구 호출을 모은다."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    start = 0
    for i, ev in enumerate(events):
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        joined = "\n".join(parts)
        if joined and "SYSTEM NOTIFICATION" not in joined and not joined.lstrip().startswith("<system-reminder>"):
            start = i
    texts, tools = [], []
    for ev in events[start + 1:]:
        if ev.get("type") != "assistant":
            continue
        for p in ev.get("message", {}).get("content", []) or []:
            if not isinstance(p, dict):
                continue
            if p.get("type") == "text":
                texts.append(p.get("text", ""))
            elif p.get("type") == "tool_use":
                tools.append((p.get("name", ""), p.get("input", {}) or {}))
    return (texts[-1] if texts else ""), tools


def launched(tools):
    for name, inp in tools:
        if name in ("Monitor", "CronCreate", "ScheduleWakeup", "mcp__scheduled-tasks__create_scheduled_task"):
            return True
        if name in ("Bash", "PowerShell"):
            cmd = str(inp.get("command", ""))
            if inp.get("run_in_background") or LAUNCH_HINT.search(cmd):
                return True
    return False


def tool_blob(tools):
    out = []
    for name, inp in tools:
        out.append(name)
        out.extend(str(v) for v in inp.values())
    return " ".join(out)


def topic_matches(tag_text, tools):
    """태그에 적은 낱말(경로·스크립트·로그 이름)이 이번 턴 도구 호출에 실제로 나와야 한다(무관한 태그 방지, 2026-10-04)."""
    blob = tool_blob(tools)
    toks = [t for t in re.split(r"[\s,:;|/\\()\[\]]+", tag_text) if len(t) >= 4]
    return any(t in blob for t in toks)


def fresh_local_log(tag_text):
    for m in re.finditer(r"[A-Za-z]:[\\/][^\s,|\]]+", tag_text):
        p = m.group(0).rstrip(").,")
        try:
            if time.time() - os.path.getmtime(p) < 900:
                return True
        except OSError:
            continue
    return False


def check(text, tools):
    if not PROMISE.search(text):
        return None
    # "~하지 않겠습니다"만 있는 답변은 약속이 아니다
    stripped = NEGATED.sub("", text)
    if not PROMISE.search(stripped):
        return None
    if TAG_WAIT.search(text):
        return None
    m = TAG_RUN.search(text)
    if m:
        if fresh_local_log(m.group(1)):
            return None
        if launched(tools):
            return None if topic_matches(m.group(1), tools) else "run-tag-topic-mismatch"
        return "run-tag-without-evidence"
    return "no-tag"


if __name__ == "__main__":
    for _s in (sys.stdin, sys.stderr):  # Windows 기본 인코딩(cp949)에서 한글 입출력이 깨지지 않게
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
        if data.get("stop_hook_active"):
            sys.exit(0)
        text, tools = ("", [])
        if data.get("_text") is not None:
            text, tools = data["_text"], data.get("_tools", [])
        elif data.get("transcript_path"):
            text, tools = load_turn(data["transcript_path"])
        verdict = check(text, tools) if text else None
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)  # 검사기 오류로 답변을 막지 않는다
    if not verdict:
        sys.exit(0)
    if verdict == "run-tag-topic-mismatch":
        print("[지금 돌고 있는 것] 태그의 내용이 이번 턴에 실제로 건 실행(명령·경로)과 맞지 않습니다. 약속한 바로 그 작업을 걸고, "
              "태그에는 그 명령에 나오는 스크립트·로그 이름을 적으세요. 무관한 크론·PR 대기로 채우지 마세요.", file=sys.stderr)
    elif verdict == "run-tag-without-evidence":
        print("[지금 돌고 있는 것] 표지가 있지만 이번 턴에 실행을 건 흔적(백그라운드 Bash, Monitor, nohup, 예약 도구)이나 "
              "최근 15분 안에 갱신된 로컬 로그가 없습니다. 실제로 실행을 걸거나, 아무것도 안 돌면 [실행 대기: 이유와 풀리는 조건]으로 바꾸세요.",
              file=sys.stderr)
    else:
        print("답변에 '진행합니다·하겠습니다·시작합니다' 같은 앞으로의 행동 약속이 있지만 증거 표지가 없습니다(사장님 지시 2026-10-04). "
              "세션은 대화 턴 사이에 스스로 움직이지 못합니다. 지금 그 자리에서 실행을 걸고(run_in_background, Monitor, nohup) "
              "[지금 돌고 있는 것: 무엇, 로그 위치] 한 줄을 달거나, 아무것도 안 돌고 있다면 [실행 대기: 이유와 풀리는 시각·조건]을 다세요. "
              "약속만 하고 끝내지 마세요.", file=sys.stderr)
    sys.exit(2)
