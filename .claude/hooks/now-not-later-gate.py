#!/usr/bin/env python3
"""Stop 훅: "나중에·내일·18:00 이후에 만들겠다"로 미루는 답변을 막는다(사장님 지시 2026-10-10, 핏 사고).

사고(2026-10-10 핏): 신PC 크레딧 읽기 도구가 없다고 하면서 "10/10 18:00 이후에 만들겠습니다"로 미뤘다.
구PC 도구를 포팅하면 바로 만들 수 있었고 실제로 5분 안에 만들어 실측까지 됐다. 미루면 13시간, 또 안 되면 24시간이 반복된다.
규칙: 앞으로의 개발·시험·실측을 먼 시각으로 미루는 문장이 있으면 둘 중 하나가 있어야 통과한다.
  (A) 이번 턴에 실제 실행(Bash·PowerShell·Write·Edit 등 도구 호출)이 있었고 그 결과를 본문에 적었다.
  (B) [지금 못 하는 이유: <사장님 자격증명·시각 고정 리셋·돈 승인 등 진짜 제약 한 줄>] 태그.
기준은 하나다: 지금 1분 뒤에 돌려 볼 수 있는가. 있으면 지금 한다.
"""
import json, re, sys

DEFER = re.compile(
    r"(내일|모레|오늘\s*밤|\d{1,2}/\d{1,2}|\d{1,2}:\d{2}|\d{1,2}시|나중|다음\s*(세션|에)|이후(에|로)?)[^.\n]{0,40}"
    r"(만들|구현|작성|개발|포팅|구축|시험|실측|등록|연결|고치|적용)[^.\n]{0,8}(겠습니다|예정|할 것|하겠|합니다|하도록)"
)
OKTAG = re.compile(r"\[지금 못 하는 이유:\s*[^\]]{6,}\]")
DOERS = {"Bash", "PowerShell", "Write", "Edit", "Agent", "Workflow"}


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0
    if d.get("stop_hook_active"):
        return 0
    path = d.get("transcript_path")
    if not path:
        return 0
    events = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    except OSError:
        return 0
    start = 0
    for i, ev in enumerate(events):
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        j = "\n".join(parts)
        if j and "SYSTEM NOTIFICATION" not in j and not j.lstrip().startswith("<system-reminder>"):
            start = i
    texts, did = [], False
    for ev in events[start + 1:]:
        if ev.get("type") != "assistant":
            continue
        for p in ev.get("message", {}).get("content", []) or []:
            if isinstance(p, dict) and p.get("type") == "text":
                texts.append(p.get("text", ""))
            elif isinstance(p, dict) and p.get("type") == "tool_use" and p.get("name") in DOERS:
                did = True
    last = texts[-1] if texts else ""
    m = DEFER.search(last)
    if not m or OKTAG.search(last):
        return 0
    sys.stderr.write(
        "미루는 말이 있습니다: '%s'. 사장님 지시(2026-10-10): 만들고 시험하는 일은 나중이 아니라 지금 1분 뒤로 돌려 실측한다. "
        "지금 만들어 실행하고 결과를 적거나, 정말 못 하면 [지금 못 하는 이유: 자격증명·시각 고정 리셋·돈 승인 등 한 줄]을 다세요. "
        "(이번 턴 실행 흔적: %s)\n" % (m.group(0)[:60], "있음" if did else "없음"))
    return 2


if __name__ == "__main__":
    sys.exit(main())
