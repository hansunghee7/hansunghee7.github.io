# -*- coding: utf-8 -*-
"""유튜브 조회수 자동 수집(N156 후속, 2026-10-05 탐, 사장님 지시): 채널의 공개 목록에서 영상별 조회수를 읽어 운영 상태 DB의 metrics_snapshots에 쌓는다.
키가 필요 없다(yt-dlp가 공개 목록만 읽음, 하루 1회라 사람이 채널을 보는 빈도 이하). 공식 데이터 API로 바꾸려면 키 승인 뒤 fetch()만 교체한다.
채널 주소는 공개 저장소에 두지 않는다: C:/work/_ops/ops-data/yt_channels.json ({"채널행id": {"channel_id": "UC...", "tabs": ["shorts"]}}).
맞추는 법: 이미 영상 id(external_id)가 있으면 그대로 쓰고, 없는 것은 발행 완료 항목을 발행일 순서로 새 영상(오래된 순)과 짝지어 id를 채운다(유튜브 제목이 편집돼 제목 일치는 쓰지 않음). 시트에 없는 새 영상은 `yt-영상id` 항목으로 만든다.
사용: python scripts/ops/youtube_views.py [--dry]    종료 코드 1 = 목록을 못 읽음/DB 오류, 0 = 정상(맞춘 건수 0이어도 0)"""
import difflib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

CONF = Path(r'C:\work\_ops\ops-data\yt_channels.json')


def norm(t):
    return re.sub(r'[\s\W_]+', '', str(t or '')).lower()


def fetch(channel_id, tab):
    r = subprocess.run([sys.executable, '-m', 'yt_dlp', '--flat-playlist', '--dump-json', '--playlist-end', '200', f'https://www.youtube.com/channel/{channel_id}/{tab}'],
                       capture_output=True, text=True, encoding='utf-8', timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode != 0:
        raise RuntimeError(f'yt-dlp 실패 rc={r.returncode}')
    return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]


def main():
    dry = '--dry' in sys.argv
    conf = json.loads(CONF.read_text(encoding='utf-8'))
    items = opsdb.select('content_items', 'id,channel_id,kind,title,status,scheduled_at,published_at,external_id,source', limit=2000)
    known = {it['external_id']: it for it in items if it.get('external_id')}
    snaps, linked, created, total, failed = [], 0, 0, 0, 0
    for ch, c in conf.items():
        for tab in c.get('tabs', []):
            try:
                vids = list(reversed(fetch(c['channel_id'], tab)))  # 오래된 것부터
            except RuntimeError as e:  # 롱폼 탭이 아직 없는 채널 등: 이 탭만 건너뛴다
                print(f'건너뜀 {ch}/{tab}: {e}')
                failed += 1
                continue
            total += len(vids)
            fresh = [v for v in vids if v['id'] not in known]
            # 아직 영상 id가 없는 발행 완료 항목을 발행일 순서로 새 영상과 짝짓는다(유튜브 제목은 편집돼 달라서 제목 일치 대신 발행 순서를 쓴다)
            waiting = sorted([it for it in items if it['channel_id'] == ch and it['status'] == 'published' and not it.get('external_id')], key=lambda x: x['published_at'] or '')
            for v, it in zip(fresh, waiting):
                known[v['id']] = it
                linked += 1
                sim = difflib.SequenceMatcher(None, norm(re.sub(r'#.*', '', v.get('title') or '')), norm(it['title'])).ratio()
                print(f'  연결(순서) {it["published_at"][:10]} 유사도 {sim:.2f} {v.get("title","")[:20]} → {it["title"][:20]}')
                if not dry:
                    opsdb.upsert('content_items', [{**{k: it[k] for k in ('id', 'channel_id', 'kind', 'title', 'status', 'scheduled_at', 'published_at', 'source')}, 'external_id': v['id']}], 'id')  # 일부 열만 보내면 새 행 검사에서 막히므로 전체 열을 보낸다
            for v in fresh[len(waiting):]:  # 시트에 아직 없는 새 영상: 영상 id로 새 항목을 만든다
                it = {'id': 'yt-' + v['id'], 'channel_id': ch, 'title': (v.get('title') or '')[:200], 'external_id': v['id']}
                known[v['id']] = it
                created += 1
                if not dry:
                    opsdb.upsert('content_items', [{**it, 'kind': 'short' if tab == 'shorts' else 'longform', 'status': 'published', 'source': 'yt-dlp'}], 'id')
            for v in vids:
                if v.get('view_count') is not None and v['id'] in known:
                    snaps.append({'content_id': known[v['id']]['id'], 'views': int(v['view_count']), 'source': 'yt-dlp'})
    if failed and not total:
        raise RuntimeError('모든 탭을 못 읽음')
    print(f'채널 목록 영상 {total}개 → 새로 연결 {linked}, 새 항목 {created}, 조회수 기록 대상 {len(snaps)}개')
    if not dry:
        # 같은 날(UTC) 이미 쌓은 영상은 건너뛴다(재실행·이중 실행 때 중복 방지, 덱스·비티 리뷰 10/5 채택)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        done = {r['content_id'] for r in opsdb.select('metrics_snapshots', 'content_id', where={'source': 'eq.yt-dlp', 'captured_at': f'gte.{today}T00:00:00+00:00'}, limit=5000)}
        fresh_snaps = [x for x in snaps if x['content_id'] not in done]
        opsdb.insert('metrics_snapshots', fresh_snaps)
        print(f'조회수 기록 {len(fresh_snaps)} (오늘 이미 있음 {len(snaps) - len(fresh_snaps)}) | metrics_snapshots 행 수', opsdb.count('metrics_snapshots'))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print('실패:', type(e).__name__, str(e)[:200])
        sys.exit(1)
