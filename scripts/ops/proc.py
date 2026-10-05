# -*- coding: utf-8 -*-
"""공정 단계 카드 조회(G2, 2026-10-05 탐, 사장님 "프로세스표에 단계마다 사장님이 말한 걸 적게 한 이유는 에이전트가 까먹어서"):
일하는 단계에 해당하는 절만 DB에서 꺼내 보여 준다. 문서 전체(핏 공정 문서 약 86KB)를 읽지 않고 그 단계 절(보통 1~3KB)과 그 안의 사장님 지시 줄만 본다.
출처: 운영 DB tasks 표의 section='process' 행(공정 문서를 절 단위로 시간당 거울 복사, import_ops_tables.py parse_process_docs).
사용:
  python scripts/ops/proc.py show 자막                 키워드가 절 제목·본문에 든 단계를 찾아 사장님 지시 줄과 본문 앞부분을 보여 줌
  python scripts/ops/proc.py show 대본 --who 핏        핏 공정에서만
  python scripts/ops/proc.py list [--who 핏]            절 목록(번호·제목·크기·사장님 지시 줄 수)
  python scripts/ops/proc.py boss 자막                 사장님 지시 줄만(가장 짧게)
  --full 을 붙이면 본문 전체(최대 6천 자)"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402


def find(kw, who=None):
    where = {'section': 'eq.process', 'or': f'(title.ilike.*{kw}*,raw->>body.ilike.*{kw}*)'}
    rows = opsdb.select('tasks', 'owner,no,title,source,raw', where=where, limit=40)
    if who:
        rows = [r for r in rows if r['owner'].startswith(who)]
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['show', 'list', 'boss'])
    ap.add_argument('kw', nargs='?')
    ap.add_argument('--who')
    ap.add_argument('--full', action='store_true')
    a = ap.parse_args()
    if a.cmd == 'list':
        where = {'section': 'eq.process'}
        rs = opsdb.select('tasks', 'owner,no,title,raw', where=where, order='owner.asc,id.asc', limit=500)
        for r in rs:
            if a.who and not r['owner'].startswith(a.who):
                continue
            print(f"[{r['owner']}#{r['no']}] {r['title'][:60]}  ({r['raw'].get('bytes', 0)}B, 사장님 지시 {len(r['raw'].get('boss_lines', []))}줄)")
        return
    if not a.kw:
        sys.exit('키워드가 필요합니다')
    rs = find(a.kw, a.who)
    if not rs:
        print(f'"{a.kw}"가 든 공정 단계가 없습니다. python scripts/ops/proc.py list 로 목록을 보세요.')
        return
    shown = 0
    for r in rs:
        raw = r['raw']
        boss = raw.get('boss_lines', [])
        print(f"\n== [{r['owner']}#{r['no']}] {r['title'][:80]}  ({r['source']}, {raw.get('bytes', 0)}B)")
        for b in boss[:8]:
            print('  ★ ' + b)
        if a.cmd == 'show':
            body = raw.get('body', '')
            if not a.full:
                lines = [l for l in body.split('\n') if a.kw in l][:6] or body.split('\n')[:6]
                print('  ' + '\n  '.join(l[:220] for l in lines))
            else:
                print(body[:6000])
        shown += 1
        if shown >= 4:
            print(f'\n(그 밖의 {len(rs) - shown}개 단계는 --who 로 좁히거나 list 로 보세요)') if len(rs) > shown else None
            break


if __name__ == '__main__':
    main()
