# -*- coding: utf-8 -*-
"""슈퍼색인관리 2단계 승격 큐(2026-10-15 탐): 최근에 업무 기록(worklog·closed·open)에 적힌 결정·규칙인데 대응하는 정본 공정 카드가 없는 행을 찾는다.
결정은 카드로 올라가야 1차 검색(recall.py)에 걸린다. 카드로 올릴지는 사람이나 탐이 보고 정한다(이 도구는 후보만 낸다, 읽기 전용).
사용: python scripts/ops/promote_queue.py [--days 7] [--limit 30]"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402
import recall  # noqa: E402

KEY = re.compile(r'결정|규칙|정책|기준|한도|상한|원칙|승인|확정|금지|변경|전환|도입|폐지')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    days = int(a[a.index('--days') + 1]) if '--days' in a else 7
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else 30
    since = time.strftime('%Y-%m-%d', time.localtime(time.time() - days * 86400))
    rows = []
    for sec in ('worklog', 'closed'):
        off = 0
        while True:
            rs = opsdb.select('tasks', 'id,owner,no,title,source_date', where={'section': f'eq.{sec}', 'source_date': f'gte.{since}', 'id': f'gt.{off}'}, order='id.asc', limit=1000)
            if not rs:
                break
            rows += [dict(r, sec=sec) for r in rs]
            off = rs[-1]['id']
    cands = [r for r in rows if KEY.search(r.get('title') or '')]
    miss = []
    for r in cands:
        res = recall.query(r['title'], n_cards=1, n_boss=0, min_hits=4)
        if not res or not res['cards']:
            miss.append(r)
    print(f"최근 {days}일 업무 기록 {len(rows)}건 중 결정·규칙 문구 {len(cands)}건, 대응 카드 없음 {len(miss)}건")
    for r in miss[:limit]:
        print(f"- [{r['sec']}] {r['owner']}{('#' + r['no']) if r.get('no') else ''} {r['source_date']}: {r['title'][:110]}")


if __name__ == '__main__':
    main()
