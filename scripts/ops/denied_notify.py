#!/usr/bin/env python3
"""PermissionDenied 훅: 자동 모드가 도구 호출을 거부하면 이유를 기록하고 사장님 텔레그램(탐 방)에 한 줄로 알린다. 2026-10-03 탐 (대장 N126).

왜: N116 1단계의 확장 편집이 "dangerous"로 세 번 막혔는데 거부 이유(분류기가 맞춘 규칙 이름)를 몰라 해법(allow 규칙 등)을 고를 수 없었다.
입력: 클로드 코드가 표준입력으로 주는 JSON(tool_name, tool_input, reason, cwd ...). 출력: 없음(거부를 뒤집지 않는다, retry도 안 함).
기록: C:/work/_ops/denied_log.jsonl (시각, 도구, 이유, 대상 파일 또는 명령 앞 80자). 편집 내용·명령 전체는 기록하지 않는다(비밀 값 방지).
알림: tg_boss.py text 로 같은 이유를 5분에 1번까지만(폭주 방지). 실패해도 일은 막지 않는다.
설정(사장님이 ~/.claude/settings.json에 1회): hooks.PermissionDenied 에 이 스크립트를 command로 등록. 규칙 정본 docs/탐_업무대장.md N126.
"""
import json, os, re, subprocess, sys, time

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


PASS_CLI = os.environ.get("DENIED_PASS_CLI", "C:/work/saegim-pass-dev/host/pass.py")
RULE_STAMPS = os.environ.get("DENIED_RULE_STAMPS", "C:/work/_ops/denied_rule_stamps.json")
RULE_TOOLS = {"Bash", "Write", "Edit", "NotebookEdit"}
RULE_THROTTLE = 1800  # 같은 (분류·도구·폴더) 요청은 30분에 한 번만 사장님께 보낸다(승인 피로 방지)


def repo_root(path):
    m = re.match(r"^([A-Za-z]:/work/[^/]+)", str(path or "").replace("\\", "/"))
    return m.group(1) if m else ""


def rule_request(d, row):
    """대장 N137 ⑤(사장님 승인 10/4 텔레그램 버튼 방식): 거부가 나면 사장님 텔레그램에 [허용]/[거절] 승인 요청을 보낸다.
    규칙 문장은 금고가 분류·도구·폴더로만 만들고, 사장님이 누를 때만 설정에 한 줄이 추가된다(에이전트는 자기 권한 설정을 못 고침).
    '검사 우회 시도' 분류는 요청하지 않는다(대화로만). 값·명령 내용은 보내지 않는다. 요청을 보냈으면 True."""
    tool = d.get("tool_name")
    if tool not in RULE_TOOLS or os.environ.get("DENIED_NO_RULE"):
        return False
    reason = str(row.get("reason") or "")
    m = re.search(r"\[([^\]]+)\]", reason)
    category = m.group(1) if m else ("Unsafe Action" if "dangerous" in reason else "")
    if not category or category == "Auto-Mode Bypass":
        return False
    ti = d.get("tool_input") or {}
    root = repo_root(ti.get("file_path") if tool != "Bash" else d.get("cwd"))
    if not root:
        return False
    key = f"{category}|{tool}|{root}"
    try:
        stamps = json.load(open(RULE_STAMPS, encoding="utf-8")) if os.path.exists(RULE_STAMPS) else {}
    except (OSError, ValueError):
        stamps = {}
    now = time.time()
    if now - float(stamps.get(key, 0)) < RULE_THROTTLE:
        return False
    stamps = {k: v for k, v in stamps.items() if now - float(v) < 86400}
    stamps[key] = now
    try:
        with open(RULE_STAMPS, "w", encoding="utf-8") as f:
            json.dump(stamps, f)
        subprocess.Popen([sys.executable, PASS_CLI, "claude_rule", "--category", category, "--tool", tool, "--target", root, "--from", "탐"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x00000008)
    except OSError:
        return False
    return True


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
        if rule_request(d, row):
            return 0  # 승인 요청 메시지가 알림을 겸한다
    except Exception:
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
