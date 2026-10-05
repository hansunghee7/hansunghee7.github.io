#!/usr/bin/env python3
"""Stop 훅(2026-10-05 탐, 사장님 지시 "목표를 잃고 대기 타는 이유 분석과 재발방지"): 사장님이 이미 지시한 목표를 놓고
"시작해도 될까요?"·"[실행 대기: 사장님의 선택]"으로 턴을 끝내려 하면 한 번 되돌려 보내고 다음 단계를 실행하게 한다.

원인(탐 분석 10/5): ① 한 산출물(PR·문서)이 끝나면 보고로 닫는 턴 구조라 다음 일을 잇는 장치가 없다 ② 이미 승인된 방향을 다시 "정하실 것"으로 묻는 습관
③ 목표가 대화에만 있어 새 지시가 오면 밀려난다 ④ 정지 훅이 요구하는 [실행 대기] 표지를 무엇이든 정당화하는 출구로 썼다.
장치: 목표 장부 C:/work/_ops/tam_drive.json (사장님 지시 목표, 지시 날짜, 다음 단계, 키워드). 하이 브리핑(session_brief.py)이 매 세션 시작에 보여 준다.
규칙: 마지막 답변이 장부의 활성 목표 키워드를 말하면서 (a) 허락·시작 여부를 묻거나 (b) 사장님의 선택을 기다린다는 [실행 대기]를 달았고
      (c) [사람 개입 필요: …] 표지가 없으면 → exit 2로 되돌려 보낸다("묻지 말고 다음 단계를 지금 실행"). stop_hook_active면 통과(한 턴에 한 번만 되돌림).
예외: [사람 개입 필요: 자격증명|비가역|돈|제품 결정|방향 결정|규칙상 금지|외부 발신|계정 생성] 표지가 있으면 통과. 기록: C:/work/_ops/drive_gate_log.jsonl"""
import json
import re
import sys
import time

DRIVE = r"C:\work\_ops\tam_drive.json"
LOG = r"C:\work\_ops\drive_gate_log.jsonl"
ASK = re.compile(r"(시작|진행|착수|실행|전환|적용)(해도|할까요|하시겠|해도 될까요|해도 되겠|하면 될까요)|정하실 것:[^\n]*[?？]")
WAIT_SELF = re.compile(r"\[실행 대기:\s*사장님의[^\]]{0,40}(선택|시작|답|결정|승인|응답|여부)[^\]]*\]")
HUMAN = re.compile(r"\[사람 개입 필요:")


def last_assistant_text(path):
    texts, start = [], 0
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    for i, ev in enumerate(events):
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        joined = "\n".join(parts)
        if joined and "SYSTEM NOTIFICATION" not in joined and not joined.lstrip().startswith("<system-reminder>"):
            start = i
    for ev in events[start + 1:]:
        if ev.get("type") == "assistant":
            for p in ev.get("message", {}).get("content", []) or []:
                if isinstance(p, dict) and p.get("type") == "text":
                    texts.append(p.get("text", ""))
    return "\n".join(texts[-2:])  # 마지막 보고 부분만


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0
    try:
        goals = [g for g in json.load(open(DRIVE, encoding="utf-8")).get("goals", []) if g.get("active")]
        text = last_assistant_text(data.get("transcript_path", ""))
    except Exception:
        return 0
    if not goals or not text or HUMAN.search(text):
        return 0
    if not (ASK.search(text) or WAIT_SELF.search(text)):
        return 0
    hit = [g for g in goals if any(k in text for k in g.get("keywords", []))]
    if not hit:
        return 0
    g = hit[0]
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%F %T"), "goal": g["id"], "ask": bool(ASK.search(text))}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    sys.stderr.write(
        f"[목표 관문] 목표 {g['id']}({g['title']})는 사장님이 이미 지시했습니다({g.get('since', '')}: \"{g.get('boss_quote', '')[:60]}\"). "
        f"시작 여부를 다시 묻거나 사장님의 선택을 기다리는 표지로 끝내지 말고, 지금 다음 단계를 실행하세요: {g.get('next', '')} "
        "정말 사람만 할 수 있는 일(자격증명·비가역·돈·제품 결정·규칙상 금지)이면 답변에 [사람 개입 필요: 사유]를 달고 그 한 가지만 구체적으로 요청하세요."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
