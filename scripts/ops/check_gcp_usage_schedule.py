#!/usr/bin/env python3
"""새김 사용량 워크플로(simplifier-cxo-db gcp-usage)의 **정기(schedule) 실행**이 36시간 안에 성공했는지 본다(대장 N164, 2026-10-06 탐).
사고: 10/6 09:20 첫 정기 실행이 2시간이 지나도 오지 않았다(수동 실행은 성공). GitHub 정기 실행은 누락될 수 있어 감시 대장에 올린다.
종료 코드 0 = 최근 36시간 안에 정기 실행 성공, 1 = 없음(수동 실행은 세지 않는다), 2 = gh 오류."""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

r = subprocess.run(['gh', 'run', 'list', '--repo', 'hansunghee7/simplifier-cxo-db', '--workflow', 'gcp-usage.yml', '--limit', '20',
                    '--json', 'event,conclusion,createdAt'], capture_output=True, text=True, encoding='utf-8', timeout=60,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
if r.returncode:
    print('gh 오류', r.stderr[:120])
    sys.exit(2)
cut = datetime.now(timezone.utc) - timedelta(hours=36)
ok = [x for x in json.loads(r.stdout) if x['event'] == 'schedule' and x['conclusion'] == 'success'
      and datetime.fromisoformat(x['createdAt'].replace('Z', '+00:00')) > cut]
print(f'최근 36시간 정기 실행 성공 {len(ok)}건')
sys.exit(0 if ok else 1)
