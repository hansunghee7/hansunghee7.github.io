# -*- coding: utf-8 -*-
"""주제관리·롱폼주제 구글시트(공개 CSV)를 운영 상태 DB의 channels·content_items·metrics_snapshots로 가져온다(N156 파일럿, 2026-10-05 탐).
시트는 읽기만 한다(공개 링크 export). 같은 주제는 id가 같아 다시 실행해도 content_items는 갱신되고, 조회수는 실행 시각의 새 스냅샷으로 쌓인다(성과 곡선용).
1단계 범위: 유튜브 기준 콘텐츠 한 줄 + 조회수·팔로워 증가수. 플랫폼별 예약일(인스타·틱톡 등)은 2단계 표(channel_posts)에서 다룬다.
사용: python scripts/ops/import_topic_sheet_to_opsdb.py [--dry]"""
import csv
import hashlib
import io
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

SHEET_ID = '1hCeiPWW7661GbeePyqGeubeqacfnHm1G364VFIGcM-I'
TABS = {'short': 1307976893, 'longform': 113572078}
KST = timezone(timedelta(hours=9))
STATUS = {'발행': 'published', '발행예약': 'scheduled', '영상제작완료': 'ready', '제작중': 'producing', '후보': 'idea', '': 'idea'}
CHANNELS = [
    {'id': 'yt-shorts', 'platform': 'youtube', 'label': '유튜브 쇼츠', 'source': 'sheet-import'},
    {'id': 'yt-main', 'platform': 'youtube', 'label': '유튜브 롱폼', 'source': 'sheet-import'},
]


def fetch(gid):
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}'
    with urllib.request.urlopen(url, timeout=30) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode('utf-8'))))


def day(s):
    m = re.match(r'\s*(\d{4})\.(\d{1,2})\.(\d{1,2})', s or '')
    return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=KST).isoformat() if m else None


def num(s):
    s = re.sub(r'[,\s]', '', s or '')
    return int(s) if re.fullmatch(r'-?\d+', s) else None


def rows_for(kind):
    items, snaps, seen = [], [], set()
    title_col = '주제' if kind == 'short' else '롱폼 주제'
    for r in fetch(TABS[kind]):
        title = (r.get(title_col) or '').strip()
        status = (r.get('상태') or '').strip()
        if not title or (kind == 'longform' and not status):
            continue  # 빈 줄, 롱폼 탭의 빈 설계 칸은 제외
        eid = (r.get('에피소드ID') or '').strip()
        cid = eid or ('sh-' if kind == 'short' else 'lf-') + hashlib.sha1(title.encode('utf-8')).hexdigest()[:8]
        if cid in seen:
            cid = cid + '-' + hashlib.sha1(title.encode('utf-8')).hexdigest()[:4]
        seen.add(cid)
        st = STATUS.get(status, 'idea')
        when = day(r.get('유튜브 예약발행일')) or day(r.get('발행예정일'))
        items.append({'id': cid, 'channel_id': 'yt-shorts' if kind == 'short' else 'yt-main', 'kind': kind if kind == 'longform' else 'short',
                      'title': title, 'status': st, 'scheduled_at': when if st in ('scheduled', 'ready', 'producing') else None,
                      'published_at': when if st == 'published' else None, 'source': 'sheet-import'})
        v, f = num(r.get('조회수')), num(r.get('팔로워 증가수'))
        if v is not None:
            snaps.append({'content_id': cid, 'views': v, 'followers_delta': f, 'source': 'sheet-import'})
    return items, snaps


def main():
    dry = '--dry' in sys.argv
    items, snaps = [], []
    for k in ('short', 'longform'):
        i, s = rows_for(k)
        items += i
        snaps += s
    print(f'가져올 것: 콘텐츠 {len(items)}개(쇼츠 {sum(1 for x in items if x["kind"]=="short")}·롱폼 {sum(1 for x in items if x["kind"]=="longform")}), 조회수 스냅샷 {len(snaps)}개')
    if dry:
        return
    now = datetime.now(KST).isoformat()
    for s in snaps:
        s['captured_at'] = now
    print('채널', opsdb.upsert('channels', CHANNELS, 'id'))
    print('콘텐츠', opsdb.upsert('content_items', items, 'id'))
    print('스냅샷', opsdb.insert('metrics_snapshots', snaps))
    print('확인 표 행 수:', {t: opsdb.count(t) for t in ('channels', 'content_items', 'metrics_snapshots')})


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
