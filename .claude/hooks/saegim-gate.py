#!/usr/bin/env python3
"""PreToolUse 훅: 사장님께 가는 보고물(아티팩트 발행, 파일 전달, 사장님 앞 우편)은 새김 조회 뒤에만 나간다.

왜: 사장님 지시(2026-09-20) "저에게 보고는 무조건 MCP 쓰게". 도그푸딩(고객과 같은 방식으로 써서 고객보다 먼저 문제를
찾는 것)이 규칙 문장에만 맡겨져 있어 탐도 오늘 사장님이 읽는 문서를 새김 조회 없이 만들었다. 기억에 맡기지 않고
기계가 확인한다. 판정은 의미 해석이 아니라 "이 세션에 새김 조회(tool_use) 기록이 있는가"뿐이다.
범위: 기계가 감지할 수 있는 곳만 막는다. 채팅 답변은 감지할 수 없어 규칙 문장과 주간 감사로 다룬다.
통과 장치(새김이 끊겼을 때 보고 자체가 막히면 안 된다):
  - 이 세션에서 가장 최근의 새김 호출이 오류로 끝났으면 통과
  - 파일 .claude/saegim-outage 가 있으면 통과(접속 불가를 사장님께 밝힌 뒤 만든다).
    삭제가 아니라 "잠금"이라 이 파일 자체는 막지 않되, 만들어질 때마다 PostToolUse 훅
    (saegim-outage-notify.py)이 지투에게 자동으로 우편을 보내 사후 감독한다(사장님 확정, 2026-09-23 --
    동기 승인은 지투 세션이 꺼져 있을 때 일을 무한정 멈출 위험이 있어, "즉시 통보"로 취지를 구현)
  - 환경변수 SAEGIM_GATE=off 이면 통과
UX가이드 원문 읽기(2026-09-24 사장님 지시 "UX가이드 열람은 대표 승인, 그 외는 새김 MCP"): 원문은 비공개
새김 저장소 docs/guides/UX_GUIDE.md로 옮겼다. 원문 파일을 읽는 것(Read 도구, 또는 셸 명령에 경로가 들어간 것)은
새김 조회 여부·장애 여부와 상관없이 막고, 사장님이 대화에서 승인한 뒤 세션이 만드는 .claude/uxguide-approved
파일이 있을 때만 통과한다(승인 자체는 기계가 확인할 수 없어 세션의 정직성에 맡기고, 다 읽으면 지운다).
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
    "반영했으면 cite도 남깁니다. 새김이 끊겨 있으면 접속 불가를 사장님께 밝힌 뒤 "
    ".claude/saegim-outage 파일을 만들면 통과합니다(UX가이드 원문 열람은 별도로 대표 승인이 필요)."
)

UX_GUIDE_BLOCK_MSG = (
    "UX가이드 원문 열람은 대표 승인이 필요합니다(사장님 지시 2026-09-24). 평소에는 새김 MCP로 보세요: "
    "mcp__saegim__lookup(doc=\"UX_GUIDE\", query=...) 또는 list_sections/get_section. "
    "원문이 꼭 필요하면 사장님께 이유를 말씀드리고 채팅으로 승인을 받은 뒤 세션이 직접 .claude/uxguide-approved 파일을 만들고(사장님께 파일 생성을 요청하지 말 것), "
    "다 읽으면 지우세요(새김 장애 표시 .claude/saegim-outage로는 통과되지 않습니다)."
)

# 공개 저장소 안내문(docs/UX_GUIDE.md)과 비공개 원문(simplifier-saegim/docs/guides/UX_GUIDE.md) 모두
UX_GUIDE_PATH_RE = re.compile(r"(^|[/\\])ux_guide\.md$", re.IGNORECASE)
UX_GUIDE_CMD_RE = re.compile(r"guides[/\\]+ux_guide\.md", re.IGNORECASE)


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
    if tool == "Read":
        path = (tinput.get("file_path") or "").replace("\\", "/")
        return bool(UX_GUIDE_PATH_RE.search(path))
    if tool in ("Bash", "PowerShell"):
        return bool(UX_GUIDE_CMD_RE.search(tinput.get("command", "") or ""))
    return False


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
    if is_ux_guide_shortcut(tool, tinput):
        if os.environ.get("SAEGIM_GATE") == "off":
            return 0, ""
        if project_dir and os.path.exists(os.path.join(project_dir, ".claude", "uxguide-approved")):
            return 0, ""
        return 2, UX_GUIDE_BLOCK_MSG
    if is_boss_facing(tool, tinput):
        msg = BLOCK_MSG
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
