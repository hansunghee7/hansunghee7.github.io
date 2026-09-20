#!/usr/bin/env python3
"""UserPromptSubmit 훅: 정확히 일치하는 개시어("하이~", "바이~")가 오면 해당 스킬을 열라고 한 줄 주입한다.

왜: 아침·저녁 의식 절차를 CLAUDE.md에서 스킬로 옮기면(2026-09-20 구조 최적화) 세션이 스킬을 안 열고
진행할 위험이 생긴다(마야 시험 A 10/14 → 14/14 → 12/14, 2026-09-08 아침 의식 사고). 규칙 문장에만 맡기지 않고
결정적으로 상기시킨다.
범위를 좁게 둔 이유: 의미 해석이 필요한 요청(글 써줘, ffmpeg 렌더 등)은 키워드 표로 열거할 수 없고,
지시서 8-D가 의미 해석 규칙은 훅으로 만들지 말라고 했다. 그래서 개시어 두 개만 다룬다.
입력: stdin JSON(Claude Code UserPromptSubmit 규격, prompt 포함). 출력: stdout 한두 줄(컨텍스트로 주입). 항상 exit 0.
"""
import json
import re
import sys

# "하이~ ..." / "바이~" (물결 필수, 뒤에 무엇이 와도 됨) 또는 짧은 "하이 탐" / "바이" 단독 메시지
TILDE = re.compile(r"^\s*(하이|바이)\s*[~～〜]")
SHORT = re.compile(r"^\s*(하이|바이)(\s+\S{1,6})?\s*$")

MESSAGES = {
    "하이": "📌 개시어 '하이~' 감지: `.claude/skills/session-start/SKILL.md`를 먼저 열고 그 절차를 따른다. 새 세션으로 시작하고, 자기 인수인계 블록은 요약하지 말고 원문 그대로 출력한다.",
    "바이": "📌 개시어 '바이~' 감지: `.claude/skills/session-end/SKILL.md`를 먼저 열고 그 절차를 따른다. 산출물 회수와 push까지 끝내고, 새 파일을 읽는 조사는 하지 않는다.",
}


def nudge(prompt):
    m = TILDE.match(prompt) or SHORT.match(prompt)
    return MESSAGES[m.group(1)] if m else ""


def main():
    try:
        # Windows 콘솔 기본 인코딩(cp949)으로 읽으면 한글 개시어가 깨지므로 바이트로 받아 UTF-8로 푼다
        prompt = json.loads(sys.stdin.buffer.read().decode("utf-8")).get("prompt", "")
    except Exception:
        return 0
    out = nudge(prompt)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
