# -*- coding: utf-8 -*-
"""사장님 말 원장(G5, 2026-10-05 탐, 사장님 "같은 얘기를 3번째 하는데 저장 안 하고 넘어가서 에이전트들이 나중에 딴소리하고 사장이 이상한 얘기하는 사람이 된다"):
사장님이 한 말을 에이전트의 기억이나 판단에 맡기지 않고, 모든 세션의 대화 기록(Claude Code가 자동 저장하는 transcript)에서 사장님의 실제 발화만 뽑아
원문 그대로 운영 DB(tasks 표 section='boss')에 쌓는다. 누가 저장할지 고민할 필요가 없고(자동), 날짜·세션이 붙어 "언제 몇 번 말했는지"가 숫자로 남는다.
안전: 키·토큰 모양은 [키 값 제외]로 바꿔 저장, 시스템 알림·다른 세션의 메시지·도구 결과는 제외, 읽기는 transcript 파일뿐.
사용:
  python scripts/ops/boss_said.py sync [--days 2]      새 발화를 DB에 추가(중복 제외, 시간당 자동)
  python scripts/ops/boss_said.py find 프로세스표 [--days 7] [--who 탐]   그 말이 든 사장님 발화를 날짜순으로(원문)
  python scripts/ops/boss_said.py count 프로세스표 [--days 7]            그 주제를 사장님이 몇 번 말했는지(날짜별)"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

PROJ = Path(os.path.expanduser('~')) / '.claude' / 'projects'
KST = timezone(timedelta(hours=9))
SECRET = re.compile(r'(sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|sb_secret_[\w-]+|sbp_[0-9a-f]{20,}|ghp_\w{20,}|github_pat_\w{20,}|xox[bp]-[\w-]+|-----BEGIN[\s\S]*?(?:-----END[^-]*-----|$)|eyJ[\w-]{20,}\.[\w-]{10,}\.[\w-]{10,})')
SKIP = ('<system-reminder', 'SYSTEM NOTIFICATION', '[Subagent hand-back]', '<cross-session-message', '<task-notification', '<command-name>', '<local-command', 'Stop hook feedback', 'Caveat:')
PERSONAS = ['클라우드탐', '탐', '핏', '마야', '지투', '노트', '비티', '덱스', '타미']


def texts_of(ev):
    c = ev.get('message', {}).get('content', [])
    if isinstance(c, str):
        return [c]
    return [p.get('text', '') for p in c if isinstance(p, dict) and p.get('type') == 'text']


def persona_of(first_texts):
    for t in first_texts[:4]:
        m = re.search(r'(클라우드탐|탐|핏|마야|지투|노트|비티|덱스|타미)', t[:120])
        if m:
            return m.group(1)
    return '미상'


def scan(days):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for f in glob.glob(str(PROJ / '*' / '*.jsonl')):
        try:
            if datetime.fromtimestamp(os.path.getmtime(f), timezone.utc) < since:
                continue
        except OSError:
            continue
        sid = Path(f).stem
        said, first = [], []
        try:
            with open(f, encoding='utf-8', errors='ignore') as fh:
                for line in fh:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get('type') != 'user' or ev.get('isMeta') or ev.get('isSidechain'):
                        continue
                    for t in texts_of(ev):
                        t = t.strip()
                        if not t or any(t.startswith(s) or s in t[:80] for s in SKIP):
                            continue
                        if len(first) < 6:
                            first.append(t)
                        ts = ev.get('timestamp', '')
                        try:
                            at = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        except ValueError:
                            continue
                        if at < since:
                            continue
                        said.append((at, t))
        except OSError:
            continue
        who = persona_of(first)
        for at, t in said:
            clean = SECRET.sub('[키 값 제외]', t)
            out.append({'at': at.astimezone(KST), 'who': who, 'sid': sid, 'text': clean[:6000]})
    return sorted(out, key=lambda x: x['at'])


def hashes():
    h, off = set(), 0
    while True:
        rs = opsdb.select('tasks', 'id,raw', where={'section': 'eq.boss', 'id': f'gt.{off}'}, order='id.asc', limit=1000)
        if not rs:
            return h
        for r in rs:
            h.add(r['raw'].get('hash'))
        off = rs[-1]['id']


def sync(days):
    rows = scan(days)
    have = hashes()
    new = []
    for r in rows:
        hsh = hashlib.sha1((r['sid'] + r['at'].isoformat() + r['text'][:200]).encode('utf-8')).hexdigest()[:16]
        if hsh in have:
            continue
        new.append({'owner': r['who'], 'section': 'boss', 'no': '', 'title': re.sub(r'\s+', ' ', r['text'])[:150], 'status': '기록', 'source_date': r['at'].strftime('%Y-%m-%d'),
                    'next_action': None, 'evidence': None, 'result': None, 'cost': None, 'decider': None, 'source': 'boss_said.py',
                    'raw': {'text': r['text'], 'at': r['at'].strftime('%Y-%m-%d %H:%M:%S'), 'session': r['sid'], 'hash': hsh}})
    for i in range(0, len(new), 100):
        opsdb.insert('tasks', new[i:i + 100])
    print(f'사장님 발화 {len(rows)}건 중 새로 {len(new)}건 추가 (DB boss 행 {opsdb.count("tasks", {"section": "eq.boss"})}건)')


def fetch(days, who=None):
    since = (datetime.now(KST) - timedelta(days=days)).strftime('%Y-%m-%d')
    where = {'section': 'eq.boss', 'source_date': f'gte.{since}'}
    if who:
        where['owner'] = f'eq.{who}'
    out, off = [], 0
    while True:
        rs = opsdb.select('tasks', 'id,owner,raw', where={**where, 'id': f'gt.{off}'}, order='id.asc', limit=1000)
        if not rs:
            return out
        out += rs
        off = rs[-1]['id']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sync'); p.add_argument('--days', type=int, default=2)
    p = sub.add_parser('find'); p.add_argument('kw'); p.add_argument('--days', type=int, default=7); p.add_argument('--who')
    p = sub.add_parser('count'); p.add_argument('kw'); p.add_argument('--days', type=int, default=7)
    a = ap.parse_args()
    if a.cmd == 'sync':
        return sync(a.days)
    rs = [r for r in fetch(a.days, getattr(a, 'who', None)) if a.kw in r['raw']['text']]
    rs.sort(key=lambda r: r['raw']['at'])
    if a.cmd == 'count':
        by = {}
        for r in rs:
            by.setdefault(r['raw']['at'][:10], []).append(r['raw']['at'][11:16])
        print(f'"{a.kw}"를 사장님이 말한 발화: 총 {len(rs)}건')
        for d, ts in sorted(by.items()):
            print(f'  {d}: {len(ts)}건 ({", ".join(ts[:8])})')
        return
    for r in rs:
        t = re.sub(r'\s+', ' ', r['raw']['text'])
        print(f"[{r['raw']['at']}·{r['owner']}] {t[:400]}")


if __name__ == '__main__':
    main()
