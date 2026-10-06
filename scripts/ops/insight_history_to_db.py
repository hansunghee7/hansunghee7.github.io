#!/usr/bin/env python3
"""공식 API·구PC 크롤 수집 이력(비공개 저장소 carvit-insight-data)을 운영 상태 DB에 통합한다(대장 N103·N14, 2026-10-06 탐).

사장님 지시 2026-10-06: 크롬 확장·구PC 크롤·공식 API·컴포지오 수집 정보를 통합하고 과거 기록을 정리한다.
- 인스타 sinkihanapt 공식 Meta API 최신 글별 수치 → content_items(ig-<미디어id>, 컴포지오 적재분과 같은 id) + metrics_snapshots(source=meta-api)
- 네이버 클립 구PC 크롤 일별 이력 → channels(naver-clip) + content_items(nc-<제목 해시>) + metrics_snapshots(source=pc-crawl, 날짜별)
멱등: (content_id, source, 날짜)가 이미 있으면 건너뛴다. 사용: python scripts/ops/insight_history_to_db.py [--dry]
"""
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import opsdb  # noqa: E402

REPO = 'hansunghee7/carvit-insight-data'


def gh_json(path):
    r = subprocess.run(['gh', 'api', f'repos/{REPO}/contents/{path}'], capture_output=True, text=True, encoding='utf-8', timeout=60,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode:
        raise RuntimeError(f'gh api {path}: {r.stderr[:120]}')
    return json.loads(base64.b64decode(json.loads(r.stdout)['content']).decode('utf-8'))


def existing(source):
    rows = opsdb.select('metrics_snapshots', 'content_id,captured_at', where={'source': f'eq.{source}'}, limit=20000)
    return {(r['content_id'], r['captured_at'][:10]) for r in rows}


def main():
    dry = '--dry' in sys.argv
    channels, items, snaps = [], {}, []
    # 1) 인스타 공식 API
    ig = gh_json('data/instagram_insights.json')['latest']
    day = ig['collected_at'][:10]
    have = existing('meta-api')
    channels.append({'id': 'ig-sinkihanapt', 'platform': 'instagram', 'label': '인스타 sinkihanapt', 'active': True, 'source': 'meta-api'})
    for m in ig.get('media', []):
        cid = f"ig-{m['id']}"
        items[cid] = {'id': cid, 'channel_id': 'ig-sinkihanapt', 'kind': 'short', 'title': (m.get('caption') or cid).replace('\n', ' ')[:80], 'status': 'published',
                      'scheduled_at': None, 'published_at': (m.get('timestamp') or '')[:19] + '+00:00' if m.get('timestamp') else None, 'external_id': m['id'], 'source': 'meta-api'}
        if (cid, day) not in have:
            snaps.append({'content_id': cid, 'captured_at': ig['collected_at'], 'views': m.get('views'), 'likes': m.get('like_count', m.get('likes')),
                          'comments': m.get('comments_count', m.get('comments')), 'source': 'meta-api'})
    # 2) 네이버 클립 크롤 이력
    channels.append({'id': 'naver-clip', 'platform': 'naverclip', 'label': '네이버 클립', 'active': True, 'source': 'pc-crawl'})
    have = existing('pc-crawl')
    for h in gh_json('data/naver_clip.json')['history']:
        for it in h['items']:
            cid = 'nc-' + hashlib.sha1(it['caption'][:30].encode('utf-8')).hexdigest()[:10]
            items.setdefault(cid, {'id': cid, 'channel_id': 'naver-clip', 'kind': 'short', 'title': it['caption'][:80], 'status': 'published',
                                   'scheduled_at': None, 'published_at': None, 'external_id': None, 'source': 'pc-crawl'})
            if (cid, h['date']) not in have:
                snaps.append({'content_id': cid, 'captured_at': h['date'] + 'T00:00:00+00:00', 'views': it.get('views'), 'likes': None, 'comments': None, 'source': 'pc-crawl'})
                have.add((cid, h['date']))
    print(f'채널 {len(channels)} | 글 {len(items)} | 새 스냅샷 {len(snaps)}')
    if dry:
        return 0
    opsdb.upsert('channels', channels, 'id')
    opsdb.upsert('content_items', list(items.values()), 'id')
    if snaps:
        opsdb.insert('metrics_snapshots', snaps)
    print('적재 완료 | metrics_snapshots 행 수', opsdb.count('metrics_snapshots'))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as e:
        print('오류', str(e)[:200])
        sys.exit(2)
