# -*- coding: utf-8 -*-
"""에이전트 작업 기록을 운영 DB에 직접 남기고 읽는다(G2, 2026-10-05 탐, 사장님 "에이전트가 본인 기록을 DB에 못 쓰면 탐이 대신 넣어 주나?"):
탐이 대신 옮기지 않는다. 각자 한 줄 명령으로 자기 기록을 쓴다. 문서(업무대장 md)는 시간당 자동으로 DB에 복사되는 거울이고, 이 도구는 문서를 거치지 않는 직접 기록이다.
저장: tasks 표의 section='worklog' 행(스키마 변경 없음, 시간당 거울 갱신이 지우지 않도록 importer가 예외 처리). 누가 썼는지(owner)는 --who 필수.
안전: 허용된 이름만, 한 줄 300자, 비밀값 모양(키·토큰) 거부, 삭제 명령 없음(추가 전용), 값은 DB 키 대신 opsdb.py가 읽는 .env의 키를 쓰므로 에이전트가 키를 볼 일 없음.
사용:
  python scripts/ops/worklog.py add --who 핏 "대본 3편 Vertex 검증 호출을 4회에서 1회로 묶음" [--task N66] [--evidence 로그경로]
  python scripts/ops/worklog.py list [--who 핏] [--days 3]
  python scripts/ops/worklog.py today"""
import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

WHO = {'탐', '핏', '마야', '지투', '노트', '비티', '덱스', '타미', '사장님'}
SECRET = re.compile(r'(sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|sb_secret_|sbp_[0-9a-f]{20,}|ghp_|github_pat_|-----BEGIN)', re.I)


def add(a):
    if a.who not in WHO:
        sys.exit(f'who는 {sorted(WHO)} 중 하나여야 합니다')
    text = ' '.join(a.text).strip()
    if not text or len(text) > 300:
        sys.exit('기록은 1~300자 한 줄이어야 합니다')
    if SECRET.search(text) or SECRET.search(a.evidence or ''):
        sys.exit('비밀값 모양이 들어 있어 거부했습니다(값은 기록에 쓰지 않습니다)')
    now = datetime.now()
    row = {'owner': a.who, 'section': 'worklog', 'no': a.task or '', 'title': text, 'status': '기록', 'source_date': now.strftime('%Y-%m-%d'),
           'evidence': a.evidence, 'source': 'agent-log', 'raw': {'source': 'agent-log', 'at': now.strftime('%Y-%m-%d %H:%M:%S')}}
    opsdb.insert('tasks', [row])
    print(f'기록함: [{a.who}] {text[:60]}')


def rows(who=None, days=3):
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    where = {'section': 'eq.worklog', 'source_date': f'gte.{since}'}
    if who:
        where['owner'] = f'eq.{who}'
    return opsdb.select('tasks', 'owner,no,title,evidence,source_date,raw', where=where, order='id.desc', limit=200)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add')
    p.add_argument('--who', required=True)
    p.add_argument('--task')
    p.add_argument('--evidence')
    p.add_argument('text', nargs='+')
    p = sub.add_parser('list')
    p.add_argument('--who')
    p.add_argument('--days', type=int, default=3)
    sub.add_parser('today')
    a = ap.parse_args()
    if a.cmd == 'add':
        add(a)
        return
    rs = rows(getattr(a, 'who', None), 1 if a.cmd == 'today' else getattr(a, 'days', 3))
    for r in rs:
        print(f"{r['raw'].get('at', r['source_date'])}  [{r['owner']}] {r['no'] + ' ' if r['no'] else ''}{r['title']}" + (f"  (증거 {r['evidence']})" if r['evidence'] else ''))
    print(f'-- {len(rs)}건')


if __name__ == '__main__':
    main()
