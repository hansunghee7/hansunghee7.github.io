"""PreToolUse 훅(2026-09-26 지투, 사장님 지시): 지투가 탐·핏에게 보내는 가이드 알림은
"UX 가이드에 무엇이 업데이트됐는지"만 담는다. 사장님 전달사항·검수 결과·판정·배경은 붙이지 않는다.
이유: 탐·핏은 외부 고객과 같은 조건으로 새김을 쓰는 도그푸딩 사용자다. 배경을 알고 쓰면 가이드 빈칸이
안 드러난다. 메모리·문서에만 있던 규칙을 지투가 9/25·9/26에 네 번 어겨(급할 때 "빨리 전하려고" 덧붙임)
보내기 전에 막는 관문으로 옮겼다. 근거 CLAUDE.md id:4e7b.
2026-10-01 사장님 보정: "탐과는 어떠한 소통도 가능하다. MCP로 해야 할 일을 직접 수정 요청하는 것만 안 하면 된다."
그래서 이 훅은 두 갈래로 나뉜다. ① 본문에 "가이드"가 들어 있으면 가이드 알림으로 보고 업데이트 내용만 허용(아래 FORBIDDEN),
② 그 밖의 업무 소통(사이트맵·일정·과업 등)은 막지 않고, 화면을 직접 고쳐 달라는 요청(DIRECT_FIX)만 막는다.
대상: SendMessage 본문이 "[지투→탐" 또는 "[지투→핏"으로 시작, 또는 mailbox.py send 탐|핏 --from 지투.
"""
import json, re, sys

# 업무 협의(순서·일정·과업)에 흔한 말(결정·요청·부탁·문제)은 빼고, 배경·검수·판정에만 쓰는 말만 막는다(9/26 범위 조정).
FORBIDDEN = ["사장님", "대표", "검수", "위반", "어긋", "고쳐", "고치", "판정", "발견", "봐 주세요",
             "확인해", "기준으로", "사례", "깨진", "깨져", "잘립", "잘려", "지적"]
# 가이드 없이 화면을 직접 고쳐 달라는 말(MCP·가이드를 거쳐야 할 일). 업무 소통 일반은 막지 않는다.
DIRECT_FIX = re.compile(r"(고쳐|수정해|바꿔|변경해)\s*(주|달|줘)")
TEMPLATE = ("[지투→탐] UX 가이드 업데이트(2026-09-26.N): 1.29 상태 아이콘 - 뜻은 아이콘마다 올리면 표시, "
            "목록 머리는 짧은 제목 / 1.32 토스트 - 표시 시간·줄바꿈 규칙 추가")


def check(text):
    if "가이드" not in text:
        if DIRECT_FIX.search(text):
            return ("[탐·핏 소통 관문] 화면·UX를 직접 고쳐 달라는 요청은 보내지 않습니다. "
                    "가이드에 넣어 MCP로 전달합니다. 사이트맵·일정·과업 같은 업무 소통은 자유롭게 보낼 수 있습니다.")
        return None
    hits = [w for w in FORBIDDEN if w in text]
    if hits:
        return ("[가이드 알림 관문] 탐·핏에게는 UX 가이드에 무엇이 업데이트됐는지만 알립니다. "
                f"사장님 전달사항·검수·판정·배경은 붙이지 않습니다. 걸린 말: {', '.join(hits)}. "
                f"형식: {TEMPLATE}")
    return None


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    text = None
    if tool == "SendMessage":
        msg = str(ti.get("message", ""))
        if re.match(r"\s*\[지투\s*→\s*(탐|핏)", msg):
            text = msg
    elif tool in ("Bash", "PowerShell"):
        cmd = str(ti.get("command", ""))
        if re.search(r"mailbox\.py\"?'?\s+send\s+[\"']?(탐|핏)[\"']?\s", cmd) and re.search(r"--from\s+[\"']?지투", cmd):
            text = cmd
    if not text:
        return 0
    reason = check(text)
    if reason:
        sys.stderr.write(reason)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
