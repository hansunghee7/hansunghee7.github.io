#!/usr/bin/env python3
"""Stop 훅(2026-10-05 탐, 사장님: "사장이 프로세스표에 저장하라는 거 꼭 저장하고"): 사장님이 이번 대화에서 "프로세스표에 저장/정리/기록/등록" 또는 "까먹지 말라"고 지시했는데
이번 턴에 실제로 DB 공정 카드를 쓰지 않았으면(proc.py add·amend·import-md, worklog.py add) 한 번 되돌려 보내 저장하게 한다.
왜: 사장님이 같은 지시를 세 번 해도 저장이 안 되고 넘어가 에이전트들이 나중에 다른 말을 하게 됨(10/5). 저장을 에이전트의 의지에 맡기지 않고 종료 관문에 둔다(CLAUDE.md id:4e7b).
통과: 이번 턴 도구 호출에 위 저장 명령이 있거나, 답변에 [저장 불필요: 이유]가 있거나, stop_hook_active. 기록: C:/work/_ops/save_gate_log.jsonl"""
import json
import re
import sys
import time

TRIGGER = re.compile(r'(프로세스표|프로세스\s*맵|공정|단계\s*카드)[^\n]{0,40}(저장|정리|기록|등록|그려|만들|넣어|적어)|(저장|기록|정리해)\s*(해\s*두|해두|하세요|해주세요|해 주세요)|까먹지|절대 까먹|꼭 저장|프로세스표에 정리|(정리|저장|기록)\s*해\s*두')
SAVE_CMD = re.compile(r'proc\.py\s+(add|amend|import-md|retire)|worklog\.py\s+add')
LOG = r'C:\work\_ops\save_gate_log.jsonl'


def parse(path):
    events = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    start, boss = 0, ''
    for i, ev in enumerate(events):
        if ev.get('type') != 'user':
            continue
        c = ev.get('message', {}).get('content', [])
        parts = [c] if isinstance(c, str) else [p.get('text', '') for p in c if isinstance(p, dict) and p.get('type') == 'text']
        joined = '\n'.join(parts).strip()
        if joined and 'SYSTEM NOTIFICATION' not in joined and not joined.startswith(('<system-reminder>', '<cross-session', '<task-notification', '[Subagent', 'Stop hook feedback')):
            start, boss = i, joined
    texts, cmds = [], []
    for ev in events[start + 1:]:
        if ev.get('type') != 'assistant':
            continue
        for p in ev.get('message', {}).get('content', []) or []:
            if not isinstance(p, dict):
                continue
            if p.get('type') == 'text':
                texts.append(p.get('text', ''))
            elif p.get('type') == 'tool_use':
                inp = p.get('input', {}) or {}
                cmds.append(str(inp.get('command', '')) + ' ' + str(inp.get('file_path', '')))
    return boss, '\n'.join(texts[-2:]), cmds


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8'))
    except Exception:
        return 0
    if data.get('stop_hook_active'):
        return 0
    try:
        boss, last, cmds = parse(data.get('transcript_path', ''))
    except Exception:
        return 0
    if not boss or not TRIGGER.search(boss):
        return 0
    if '[저장 불필요:' in last or any(SAVE_CMD.search(c) for c in cmds):
        return 0
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': time.strftime('%F %T'), 'boss': boss[:120]}, ensure_ascii=False) + '\n')
    except Exception:
        pass
    sys.stderr.write('[저장 관문] 사장님이 방금 저장/정리를 지시했는데(' + boss[:60].replace('\n', ' ') + '…) 이번 턴에 공정 카드를 쓴 흔적이 없습니다. '
                     '끝내기 전에 `python scripts/ops/proc.py add <공정> "제목" --do "할 일" --boss "사장님 말(날짜)"` 또는 `proc.py amend`로 DB에 저장하고(원문은 `boss_said.py find 키워드`로 확인), '
                     '저장 대상이 아니면 답변에 [저장 불필요: 이유]를 적으세요.')
    return 2


if __name__ == '__main__':
    sys.exit(main())
