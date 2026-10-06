#!/usr/bin/env python3
"""마야 KPI 글별 수치(인스타, 컴포지오 경유 maya_collect.py가 만든 maya_metrics.json)를 운영 상태 DB에 적재한다(대장 N152 후속·N156, 2026-10-06 탐).

사장님 지시 2026-10-06: SNS·콘텐츠 수치 분석은 핏·마야가, DB로 체계적으로 관리하는 것은 탐 몫.
- channels: 인스타 계정별 한 줄(ig-<계정>), content_items: 글 한 줄(ig-<미디어id>), metrics_snapshots: 오늘 한 번만(멱등) 좋아요·댓글·조회.
- 도달·저장·공유는 표에 열이 없어 JSON 원본(C:/work/_ops/n152/maya_metrics.json)에 둔다.
사용: python scripts/ops/maya_metrics_to_db.py [--dry]. 종료 코드 1 = 입력 없음, 2 = DB 오류.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import opsdb  # noqa: E402

SRC = Path('C:/work/_ops/n152/maya_metrics.json')


def main():
    dry = '--dry' in sys.argv
    if not SRC.exists():
        print('입력 파일 없음', SRC)
        return 1
    data = json.loads(SRC.read_text(encoding='utf-8'))
    rows = data.get('instagram') or []
    if not rows:
        print('인스타 행 0건')
        return 1
    now = datetime.now(timezone.utc)
    today = now.strftime('%Y-%m-%d')
    accts = sorted({r['account'] for r in rows if r.get('account')})
    channels = [{'id': f'ig-{a}', 'platform': 'instagram', 'label': f'인스타 {a}', 'active': True, 'source': 'composio-ig'} for a in accts]
    items = []
    for r in rows:
        kind = 'short' if r.get('type') == 'VIDEO' else 'post'  # 표의 kind 제약: longform/short/post
        items.append({'id': f"ig-{r['id']}", 'channel_id': f"ig-{r['account']}", 'kind': kind,
                      'title': (r.get('caption') or f"인스타 {r.get('date')} {r.get('type')}")[:80], 'status': 'published',
                      'scheduled_at': None, 'published_at': f"{r.get('date')}T00:00:00+00:00" if r.get('date') else None,
                      'external_id': r['id'], 'source': 'composio-ig'})
    done = {x['content_id'] for x in opsdb.select('metrics_snapshots', 'content_id', where={'source': 'eq.composio-ig', 'captured_at': f'gte.{today}T00:00:00+00:00'}, limit=5000)}
    snaps = [{'content_id': f"ig-{r['id']}", 'views': r.get('views'), 'likes': r.get('like_count'), 'comments': r.get('comments_count'), 'source': 'composio-ig'}
             for r in rows if f"ig-{r['id']}" not in done]
    print(f'계정 {accts} | 글 {len(items)} | 새 스냅샷 {len(snaps)} (오늘 이미 {len(rows) - len(snaps)})')
    if dry:
        return 0
    try:
        opsdb.upsert('channels', channels, 'id')
        opsdb.upsert('content_items', items, 'id')
        opsdb.insert('metrics_snapshots', snaps)
    except RuntimeError as e:
        print('DB 오류', str(e)[:200])
        return 2
    print('적재 완료 | metrics_snapshots 행 수', opsdb.count('metrics_snapshots'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
