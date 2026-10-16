"""PreToolUse 훅(2026-10-16 탐, 사장님 지시 "배포할 때 사장 컨펌 받게 프로세스 바꾸시고 Claude.md에도 추가하세요").

이 PC의 모든 세션(사용자 설정에 연결)에서 수동 배포 명령을 멈추고, 그 세션 대화에 사장님이 직접 쓴 배포 승인이 있을 때만 통과시킨다.
대상: `gh workflow run`(배포 워크플로), 배포 워크플로 dispatches API, `gcloud run deploy`.
승인: 사장님이 그 세션 대화창에 직접 쓴 메시지 중 최근 3시간 안의 "배포 승인|배포 컨펌|배포 ok|배포 오케이|배포해".
승인 1번 = 배포 1번. 다른 세션 메시지·도구 결과·알림 속 문구는 승인으로 치지 않는다.
예약 배포(12시·18시)는 이 훅 대상이 아니다(GitHub 안에서 돈다). 기록: C:/work/_ops/deploy_gate_log.jsonl
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 명령 자리(줄 맨 앞, ; && || | 뒤)에서 시작하는 것만 잡는다. 커밋·PR 본문·스크립트 속 글자는 잡지 않는다.
DEPLOY = re.compile(
    r"(?:^|[;&|\n(]|\bthen|\bdo)[ \t]*(?:\w+=\S+[ \t]+)*(?:"
    r"gh\s+workflow\s+run\b[^\n;&|]*deploy"
    r"|gh\s+api\b[^\n;&|]*actions/workflows/[^\s/]*deploy[^\s/]*/dispatches"
    r"|gcloud\s+run\s+deploy\b)",
    re.I,
)
APPROVE = re.compile(r"배포\s*(승인|컨펌|ok|오케이|해)", re.I)
WINDOW = timedelta(hours=3)
LOG = r"C:\work\_ops\deploy_gate_log.jsonl"

MSG = ("[배포 관문] 수동 배포는 사장님 컨펌이 있어야 합니다(사장님 지시 10/16, CLAUDE.md '배포는 사장님 컨펌').\n"
       "사장님께 이 대화에서 한 줄로 여쭈세요: 무엇을(PR 번호·제목) / 왜 예약 배포(12시·18시)를 못 기다리는지 / 비용(수동 배포 1회 약 6분).\n"
       "사장님이 이 대화창에 '배포 승인'이라고 직접 쓰시면 3시간 안에 배포 1회가 통과합니다. 급하지 않으면 예약 배포에 싣습니다.")


def log(decision, why):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%F %T"), "decision": decision, "why": why[:160]}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def user_text(entry):
    """사람이 대화창에 직접 쓴 글만 돌려준다(도구 결과·다른 세션 메시지·알림 제외)."""
    att = entry.get("attachment") or {}
    if entry.get("type") == "attachment" and att.get("type") == "queued_command":  # 작업 중에 사람이 보낸 글
        return str(att.get("prompt", "")) if (att.get("origin") or {}).get("kind") == "human" else ""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return ""
    msg = entry.get("message") or {}
    c = msg.get("content")
    if isinstance(c, list):
        if any(isinstance(p, dict) and p.get("type") == "tool_result" for p in c):
            return ""
        c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
    c = str(c or "").strip()
    if c.startswith("<") or "cross-session-message" in c or "task-notification" in c:
        return ""
    return c


def deploy_calls(entry):
    if entry.get("type") != "assistant":
        return 0
    n = 0
    for p in (entry.get("message") or {}).get("content") or []:
        if isinstance(p, dict) and p.get("type") == "tool_use":
            if DEPLOY.search(str((p.get("input") or {}).get("command", ""))):
                n += 1
    return n


def ts(entry):
    try:
        return datetime.fromisoformat(str(entry.get("timestamp")).replace("Z", "+00:00"))
    except Exception:
        return None


def approved(entries, now):
    """마지막 승인 뒤 배포 호출이 1건(지금 것) 이하이고 승인이 3시간 안이면 True."""
    last = None
    for i, e in enumerate(entries):
        t = user_text(e)
        if t and APPROVE.search(t):
            last = i
    if last is None:
        return False
    t0 = ts(entries[last])
    if t0 is None or now - t0 > WINDOW:
        return False
    used = sum(deploy_calls(e) for e in entries[last + 1:])
    return used <= 1  # 지금 호출이 이미 기록에 있으면 1


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if not DEPLOY.search(cmd):
        return 0
    entries = []
    try:
        with open(data.get("transcript_path", ""), encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    if approved(entries, datetime.now(timezone.utc)):
        log("pass", cmd)
        return 0
    log("block", cmd)
    sys.stderr.write(MSG)
    return 2


if __name__ == "__main__":
    sys.exit(main())
