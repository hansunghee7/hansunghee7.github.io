"""글 x 채널 최근 7일 성과 표(읽기 전용, 파일 쓰기 없음).

metrics_snapshots 는 누적 수치의 시점별 스냅샷이다. 글마다 7일 창 안의
최신 스냅샷을 '현재 누적'으로, 창 안 최초 스냅샷과의 차이를 '7일 증가'로 쓴다
(스냅샷이 1개뿐이면 증가는 0으로 두고 누적만 보인다).
"""
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WINDOW_DAYS = 7
NO_DATA = '최근 7일 적재 없음'


def _n(v):
    return v if isinstance(v, (int, float)) else 0


def aggregate(snapshots, items):
    """snapshots: metrics_snapshots 행 목록, items: content_items 행 목록.
    반환: [{'title','channel','views','views_delta','reactions','reactions_delta'}] (노출 누적 내림차순)."""
    meta = {i['id']: i for i in items}
    by = {}
    for s in snapshots:
        by.setdefault(s['content_id'], []).append(s)
    rows = []
    for cid, snaps in by.items():
        snaps.sort(key=lambda x: x['captured_at'])
        first, last = snaps[0], snaps[-1]

        def react(x):
            return _n(x.get('likes')) + _n(x.get('comments'))

        m = meta.get(cid, {})
        rows.append({
            'title': m.get('title') or cid,
            'channel': m.get('channel_id') or '(미분류)',
            'views': _n(last.get('views')),
            'views_delta': _n(last.get('views')) - _n(first.get('views')),
            'reactions': react(last),
            'reactions_delta': react(last) - react(first),
        })
    rows.sort(key=lambda r: (-r['views'], r['title']))
    return rows


def channel_totals(rows):
    t = {}
    for r in rows:
        c = t.setdefault(r['channel'], {'views': 0, 'views_delta': 0, 'reactions': 0, 'posts': 0})
        c['views'] += r['views']
        c['views_delta'] += r['views_delta']
        c['reactions'] += r['reactions']
        c['posts'] += 1
    return t


def _cell(s):
    return str(s).replace('|', '/').replace('\n', ' ')


def render(rows):
    if not rows:
        return NO_DATA
    out = ['| 글 | 채널 | 노출(누적) | 노출 7일 증가 | 반응(좋아요+댓글) |', '|---|---|---:|---:|---:|']
    for r in rows:
        out.append(f"| {_cell(r['title'])} | {r['channel']} | {r['views']} | {r['views_delta']} | {r['reactions']} |")
    out += ['', '| 채널 | 글 수 | 노출 합계 | 7일 증가 합계 | 반응 합계 |', '|---|---:|---:|---:|---:|']
    for ch, c in sorted(channel_totals(rows).items(), key=lambda kv: -kv[1]['views']):
        out.append(f"| {ch} | {c['posts']} | {c['views']} | {c['views_delta']} | {c['reactions']} |")
    return '\n'.join(out)


def main(now=None):
    from opsdb import select
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    snaps = select('metrics_snapshots', '*', {'captured_at': f'gte.{since}'}, 'captured_at.asc', 5000)
    if not snaps:
        print(NO_DATA)
        return 0
    items = select('content_items', 'id,channel_id,title', None, None, 5000)
    print(render(aggregate(snaps, items)))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
