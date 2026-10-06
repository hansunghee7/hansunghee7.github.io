#!/usr/bin/env python3
"""크롬 확장이 모은 계정별 팔로워 일별 시계열(assets/data/sns-insight.json)을 운영 DB account_snapshots로 이관한다(대장 N103, 2026-10-06 탐).
표가 없으면 종료 코드 3(표 신설 대기). 멱등: (channel_id, day, source)가 고유라 다시 돌려도 중복이 쌓이지 않는다.
계정 이름이 확장 데이터에 없어 채널 id는 ext-<플랫폼>이고 label에 '계정 미확인'을 적는다. 사용: python scripts/ops/followers_to_db.py [--dry]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import opsdb  # noqa: E402

SRC = Path(__file__).resolve().parents[2] / 'assets' / 'data' / 'sns-insight.json'


def main():
    dry = '--dry' in sys.argv
    data = json.loads(SRC.read_text(encoding='utf-8'))
    channels, rows = [], []
    for plat, series in data.items():
        if not isinstance(series, list) or not series:
            continue
        cid = f'ext-{plat}'
        channels.append({'id': cid, 'platform': plat, 'label': f'{plat} (크롬 확장, 계정 미확인)', 'active': True, 'source': 'chrome-ext'})
        for p in series:
            rows.append({'channel_id': cid, 'day': p['date'], 'followers': p.get('count'), 'source': 'chrome-ext'})
    print(f'채널 {len(channels)} | 팔로워 점 {len(rows)}')
    if dry:
        return 0
    try:
        opsdb.count('account_snapshots')
    except RuntimeError as e:
        if 'PGRST205' in str(e):
            print('account_snapshots 표가 아직 없음')
            return 3
        raise
    opsdb.upsert('channels', channels, 'id')
    opsdb.upsert('account_snapshots', rows, 'channel_id,day,source')
    print('이관 완료 | account_snapshots 행 수', opsdb.count('account_snapshots'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
