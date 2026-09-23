#!/usr/bin/env python3
"""PreToolUse 훅: 사장님께 가는 보고물(아티팩트 발행, 파일 전달, 사장님 앞 우편)은 새김 조회 뒤에만 나간다.

왜: 사장님 지시(2026-09-20) "저에게 보고는 무조건 MCP 쓰게". 도그푸딩(고객과 같은 방식으로 써서 고객보다 먼저 문제를
찾는 것)이 규칙 문장에만 맡겨져 있어 탐도 오늘 사장님이 읽는 문서를 새김 조회 없이 만들었다. 기억에 맡기지 않고
기계가 확인한다. 판정은 의미 해석이 아니라 "이 세션에 새김 조회(tool_use) 기록이 있는가"뿐이다.
범위: 기계가 감지할 수 있는 곳만 막는다. 채팅 답변은 감지할 수 없어 규칙 문장과 주간 감사로 다룬다.
통과 장치(새김이 끊겼을 때 보고 자체가 막히면 안 된다):
  - 이 세션에서 가장 최근의 새김 호출이 오류로 끝났으면 통과
  - 파일 .claude/saegim-outage 가 있으면 통과(접속 불가를 사장님께 밝히고 UX_GUIDE.md를 직접 읽은 뒤 만든다).
    삭제가 아니라 "잠금"이라 이 파일 자체는 막지 않되, 만들어질 때마다 PostToolUse 훅
    (saegim-outage-notify.py)이 지투에게 자동으로 우편을 보내 사후 감독한다(사장님 확정, 2026-09-23 --
    동기 승인은 지투 세션이 꺼져 있을 때 일을 무한정 멈출 위험이 있어, "즉시 통보"로 취지를 구현)
  - 환경변수 SAEGIM_GATE=off 이면 통과
입력: stdin JSON(tool_name, tool_input, transcript_path). 막을 때 exit 2 + stderr(Claude가 읽고 조회 후 다시 시도).
"""
import json
import os
import re
import sys

LOOKUP_TOOLS = ("mcp__saegim__lookup", "mcp__saegim__get_section", "mcp__saegim__list_sections")
BOSS_MAIL = re.compile(r"mailbox\.py\s+send\s+사장님")

BLOCK_MSG = (
    "사장님께 드리는 보고·아티팩트·알림은 새김 조회가 먼저입니다(사장님 지시 2026-09-20). "
    "mcp__saegim__lookup(doc=\"UX_GUIDE\", query=...)을 먼저 호출해 해당 절을 확인한 뒤 다시 시도하세요. "
    "반영했으면 cite도 남깁니다. 새김이 끊겨 있으면 접속 불가를 사장님께 밝히고 docs/UX_GUIDE.md를 직접 읽은 뒤 "
    ".claude/saegim-outage 파일을 만들면 통과합니다."
)

UX_GUIDE_BLOCK_MSG = (
    "docs/UX_GUIDE.md를 로컬 파일로 직접 읽기 전에 새김 MCP 조회가 먼저입니다(사장님 지시 2026-09-23, "
    "UX가이드 지름길 잠금 -- \"불편해야지 개선합니다\"). mcp__saegim__lookup(doc=\"UX_GUIDE\", query=...) 또는 "
    "list_sections/get_section을 먼저 호출하세요. 새김이 끊겨 있을 때만 .claude/saegim-outage 파일을 만들면 "
    "통과됩니다 -- 이건 가벼운 우회가 아니라 사장님과 지투에게 즉시 통보되는 예외입니다. 만들 때 왜 필요한지를 "
    "적어두고, 복구되면 직접 지우세요."
)

UX_GUIDE_PATH_RE = re.compile(r"(^|[/\\])docs[/\\]ux_guide\.md$", re.IGNORECASE)


def is_boss_facing(tool, tinput):
    if tool == "SendUserFile":
        return True
    if tool == "Artifact":
        action = tinput.get("action") or "publish"
        # 발행만 대상. 조회·목록·삭제·열기·고정과 자산 업로드는 보고물이 아니다.
        return action == "publish" and not tinput.get("asset")
    if tool == "Bash":
        return bool(BOSS_MAIL.search(tinput.get("command", "") or ""))
    return False


def is_ux_guide_shortcut(tool, tinput):
    if tool != "Read":
        return False
    path = (tinput.get("file_path") or "").replace("\\", "/")
    return bool(UX_GUIDE_PATH_RE.search(path))


def scan(transcript_path):
    """(조회 기록이 있는가, 가장 최근 새김 호출이 오류였는가)."""
    seen, last_err, ids = False, False, {}
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                # 결과 줄에는 도구 이름이 없으므로 tool_result 줄도 읽는다
                if "mcp__saegim__" not in line and "tool_result" not in line:
                    continue
                try:
                    msg = (json.loads(line).get("message") or {}).get("content")
                except Exception:
                    continue
                if not isinstance(msg, list):
                    continue
                for b in msg:
                    if b.get("type") == "tool_use" and str(b.get("name", "")).startswith("mcp__saegim__"):
                        ids[b.get("id")] = b.get("name")
                        if b.get("name") in LOOKUP_TOOLS:
                            seen = True
                    elif b.get("type") == "tool_result" and b.get("tool_use_id") in ids:
                        last_err = bool(b.get("is_error"))
    except OSError:
        return True, False  # 기록을 못 읽으면 막지 않는다(fail-open)
    return seen, last_err


def decide(event, project_dir):
    tool = event.get("tool_name", "")
    tinput = event.get("tool_input") or {}
    if is_boss_facing(tool, tinput):
        msg = BLOCK_MSG
    elif is_ux_guide_shortcut(tool, tinput):
        msg = UX_GUIDE_BLOCK_MSG
    else:
        return 0, ""
    if os.environ.get("SAEGIM_GATE") == "off":
        return 0, ""
    if project_dir and os.path.exists(os.path.join(project_dir, ".claude", "saegim-outage")):
        return 0, ""
    seen, last_err = scan(event.get("transcript_path", ""))
    if seen or last_err:
        return 0, ""
    return 2, msg


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    code, msg = decide(event, os.environ.get("CLAUDE_PROJECT_DIR", ""))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
