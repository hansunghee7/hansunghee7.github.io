#!/usr/bin/env python3
"""마야 글별 좋아요(링크드인·리멤버·로켓펀치·페이스북 개인, 화면 수집 assets/data/post_reactions.json)를 운영 상태 DB에 적재한다.
슈퍼프로세스 ③ 장부(2026-10-11): 인스타만 DB에 있고 나머지 채널은 JSON에만 있던 빈칸을 메운다. 손으로 쓰지 않고 증거 파일에서 적재한다.
- channels: <채널>-han 한 줄, content_items: <채널>-<글번호> 한 줄(kind=post), metrics_snapshots: (글, 채널, 수집일) 한 번만(멱등, source=screen-read).
- views 열에는 노출(impressions)을 넣는다. 없으면 비운다.
사용: python scripts/ops/maya_reactions_to_db.py [--dry]. 종료 코드 1 = 입력 없음, 2 = DB 오류.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import opsdb  # noqa: E402

SRC = Path(__file__).resolve().parents[2] / 'assets' / 'data' / 'post_reactions.json'
LABEL = {'linkedin': '링크드인', 'remember': '리멤버 커넥트', 'rocketpunch': '로켓펀치', 'facebook': '페이스북 개인'}


LI_LATEST = Path(r'C:/work/_ops/maya_linkedin_latest.json')  # 구PC 일일 자동 읽기 결과(N30)


def linkedin_daily(allrows):
    """일일 자동 읽기(maya_linkedin_latest.json) 16글을 행으로 바꾼다. 기존 글번호와 제목 앞 10자로 맞추고, 못 맞추면 제목 해시로 id를 만든다."""
    import hashlib
    if not LI_LATEST.exists():
        return []
    d = json.loads(LI_LATEST.read_text(encoding='utf-8'))
    known = {(x.get('title') or '')[:10]: x['post'] for x in allrows if x['channel'] == 'linkedin' and x.get('post')}
    day = d['collected'][:10]
    out = []
    for p in d['posts']:
        t = p['title']
        post = known.get(t[:10]) or 't' + hashlib.md5(t.encode('utf-8')).hexdigest()[:6]
        out.append({'date': day, 'channel': 'linkedin', 'post': post, 'title': t, 'likes': p.get('likes'),
                    'comments': None, 'impressions': p.get('impressions')})
    return out


def main():
    dry = '--dry' in sys.argv
    if not SRC.exists():
        print('입력 파일 없음', SRC)
        return 1
    allrows = json.loads(SRC.read_text(encoding='utf-8'))
    rows = [r for r in allrows if r.get('post')]  # 글번호 없는 행(계정 합계 등)은 글별 장부에서 뺀다
    print('글번호 없어 제외', len(allrows) - len(rows), '행')
    rows += linkedin_daily(allrows)
    chans = sorted({r['channel'] for r in rows})
    channels = [{'id': f'{c}-han', 'platform': c, 'label': f'{LABEL.get(c, c)} 한성희', 'active': True, 'source': 'screen-read'} for c in chans]
    items = {}
    for r in rows:
        cid = f"{r['channel']}-{r['post']}"
        items[cid] = {'id': cid, 'channel_id': f"{r['channel']}-han", 'kind': 'post', 'title': (r.get('title') or '')[:80],
                      'status': 'published', 'scheduled_at': None, 'published_at': None, 'external_id': str(r['post']), 'source': 'screen-read'}
    try:
        done = {(x['content_id'], x['captured_at'][:10]) for x in opsdb.select('metrics_snapshots', 'content_id,captured_at', where={'source': 'eq.screen-read'}, limit=5000)}
    except RuntimeError as e:
        print('DB 오류', str(e)[:200])
        return 2
    snaps = []
    for r in rows:
        cid = f"{r['channel']}-{r['post']}"
        if (cid, r['date']) in done:
            continue
        snaps.append({'content_id': cid, 'captured_at': f"{r['date']}T12:00:00+09:00", 'views': r.get('impressions'),
                      'likes': r.get('likes'), 'comments': r.get('comments'), 'source': 'screen-read'})
    print(f'채널 {chans} | 글 {len(items)} | 새 스냅샷 {len(snaps)} (이미 {len(rows) - len(snaps)})')
    if dry:
        return 0
    try:
        opsdb.upsert('channels', channels, 'id')
        opsdb.upsert('content_items', list(items.values()), 'id')
        if snaps:
            opsdb.insert('metrics_snapshots', snaps)
    except RuntimeError as e:
        print('DB 오류', str(e)[:200])
        return 2
    print('적재 완료 | metrics_snapshots 행 수', opsdb.count('metrics_snapshots'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
