#!/usr/bin/env python3
"""PermissionDenied 훅: 자동 모드가 도구 호출을 거부하면 이유를 기록하고 사장님 텔레그램(탐 방)에 한 줄로 알린다. 2026-10-03 탐 (대장 N126).

왜: N116 1단계의 확장 편집이 "dangerous"로 세 번 막혔는데 거부 이유(분류기가 맞춘 규칙 이름)를 몰라 해법(allow 규칙 등)을 고를 수 없었다.
입력: 클로드 코드가 표준입력으로 주는 JSON(tool_name, tool_input, reason, cwd ...). 출력: 없음(거부를 뒤집지 않는다, retry도 안 함).
기록: C:/work/_ops/denied_log.jsonl (시각, 도구, 이유, 대상 파일 또는 명령 앞 80자). 편집 내용·명령 전체는 기록하지 않는다(비밀 값 방지).
알림: tg_boss.py text 로 같은 이유를 5분에 1번까지만(폭주 방지). 실패해도 일은 막지 않는다.
설정(사장님이 ~/.claude/settings.json에 1회): hooks.PermissionDenied 에 이 스크립트를 command로 등록. 규칙 정본 docs/탐_업무대장.md N126.
"""
import json, os, subprocess, sys, time

LOG = os.environ.get("DENIED_LOG", "C:/work/_ops/denied_log.jsonl")
STAMP = os.environ.get("DENIED_STAMP", "C:/work/_ops/denied_notify.stamp")
TG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_boss.py")


def target(ti):
    if not isinstance(ti, dict):
        return ""
    if ti.get("file_path"):
        return str(ti["file_path"])[:160]
    if ti.get("command"):
        return str(ti["command"]).replace("\n", " ")[:80]
    return ""


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    row = {"t": time.strftime("%F %T"), "tool": d.get("tool_name"), "reason": str(d.get("reason") or "")[:300],
           "target": target(d.get("tool_input")), "cwd": d.get("cwd"), "mode": d.get("permission_mode")}
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    try:
        last = float(open(STAMP).read().strip()) if os.path.exists(STAMP) else 0
        if time.time() - last >= 300 and not os.environ.get("DENIED_NO_TG"):
            open(STAMP, "w").write(str(time.time()))
            msg = f"🛑 자동 모드가 막았어요\n도구: {row['tool']}\n이유: {row['reason']}\n대상: {row['target']}"
            subprocess.run([sys.executable, TG, "text", msg, "--persona", "탐"], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
