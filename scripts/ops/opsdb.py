# -*- coding: utf-8 -*-
"""운영 상태 DB 도서관(N156, 2026-10-05 탐): 에이전트들이 같은 방식으로 표를 넣고 빼는 공통 코드.
원칙: 키 값은 이 코드에 없다. 값은 카빗 패스 금고가 `C:/work/_ops/ops-data/.env`(OPS_DATA_SECRET_KEY)에 넣어 주고, 이 코드는 읽어서 쓰기만 한다(값을 출력하지 않는다).
접속 주소(비밀 아님)는 `C:/work/_ops/ops-data/config.env`의 OPS_DATA_URL. 표 정의는 비공개 저장소 cxo-db `reports/n155/schema_v0.sql`.

사용(모듈): from opsdb import select, upsert, delete, count, to_md
사용(CLI):  python scripts/ops/opsdb.py select content_items --where status=eq.published --cols id,title,status --limit 5 [--fmt md|csv|json]
            python scripts/ops/opsdb.py count metrics_snapshots
필터 문법은 PostgREST 그대로(eq., neq., gte., lte., in.(a,b), like.*글자*). 필요한 열과 행만 읽어 토큰을 줄이는 것이 목적이다."""
import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path('C:/work/_ops/ops-data')


def _env(path):
    out = {}
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def _conf():
    cfg = {**_env(DATA / 'config.env'), **_env(DATA / '.env')}
    if not cfg.get('OPS_DATA_SECRET_KEY') or not cfg.get('OPS_DATA_URL'):
        raise SystemExit('운영 DB 설정이 없습니다(config.env의 OPS_DATA_URL, .env의 OPS_DATA_SECRET_KEY). 키는 카빗 패스 envput으로 받습니다.')
    return cfg['OPS_DATA_URL'].rstrip('/') + '/rest/v1', cfg['OPS_DATA_SECRET_KEY']


def _access_log(method, path):
    """DB 사용 기록(값 없음): 시각·방식·표. 에이전트가 DB를 얼마나 쓰는지(도입 효과) 재는 용도, 실패해도 호출을 막지 않는다."""
    try:
        import os
        import time
        with open(r'C:\work\_ops\opsdb_access.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': time.strftime('%F %T'), 'm': method, 'table': path.split('?')[0].lstrip('/')[:40], 'who': os.environ.get('OPSDB_WHO', ''), 'cmd': os.path.basename(sys.argv[0])[:30]}, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _call(method, path, body=None, prefer=None, extra=None):
    _access_log(method, path)
    base, key = _conf()
    headers = {'apikey': key, 'Content-Type': 'application/json', 'User-Agent': 'carvit-opsdb'}
    if prefer:
        headers['Prefer'] = prefer
    if extra:
        headers.update(extra)
    req = urllib.request.Request(base + path, data=json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8')
            return r.status, (json.loads(raw) if raw else None), dict(r.headers)
    except urllib.error.HTTPError as e:
        msg = e.read().decode('utf-8', 'replace')[:300].replace(key, '[키]')
        raise RuntimeError(f'DB 오류 HTTP {e.code}: {msg}') from None


def select(table, cols='*', where=None, order=None, limit=None):
    """where: {'status': 'eq.published'} 또는 'status=eq.published&id=like.*x*' 같은 문자열."""
    q = [f'select={urllib.parse.quote(cols, safe=",*()")}']
    if isinstance(where, dict):
        q += [f'{k}={urllib.parse.quote(str(v), safe=".,*()")}' for k, v in where.items()]
    elif where:  # 문자열 조건은 & 로 나눈 각 조각의 값 부분을 인코딩한다(공백·한글이 든 값이 주소를 깨지 않게)
        for part in str(where).split('&'):
            k, _, v = part.partition('=')
            q.append(f'{k}={urllib.parse.quote(v, safe=".,*()")}')
    if order:
        q.append(f'order={order}')
    if limit:
        q.append(f'limit={int(limit)}')
    return _call('GET', f'/{table}?' + '&'.join(q))[1] or []


def upsert(table, rows, on_conflict=None):
    """있으면 고치고 없으면 넣는다. rows는 dict 목록(열 이름이 같아야 한다)."""
    if not rows:
        return 0
    q = f'?on_conflict={on_conflict}' if on_conflict else ''
    _call('POST', f'/{table}{q}', rows, prefer='resolution=merge-duplicates,return=minimal')
    return len(rows)


def insert(table, rows):
    if not rows:
        return 0
    _call('POST', f'/{table}', rows, prefer='return=minimal')
    return len(rows)


def patch(table, where, values):
    """조건에 맞는 행의 일부 열만 고친다(id 같은 자동 번호 열은 값으로 넣을 수 없어 upsert 대신 이것을 쓴다). where는 필수."""
    if not where:
        raise ValueError('patch에는 조건이 필요합니다')
    q = '&'.join(f'{k}={urllib.parse.quote(str(v), safe=".,*()")}' for k, v in where.items())
    _call('PATCH', f'/{table}?{q}', values, prefer='return=minimal')


def delete(table, where):
    """where는 필수(조건 없는 전체 삭제는 막는다)."""
    if not where:
        raise ValueError('delete에는 조건이 필요합니다')
    q = '&'.join(f'{k}={urllib.parse.quote(str(v), safe=".,*()")}' for k, v in where.items()) if isinstance(where, dict) else where
    _call('DELETE', f'/{table}?{q}', prefer='return=minimal')


def count(table, where=None):
    q = ''
    if isinstance(where, dict):
        q = '&' + '&'.join(f'{k}={urllib.parse.quote(str(v), safe=".,*()")}' for k, v in where.items())
    elif where:
        q = '&' + '&'.join(f'{k}={urllib.parse.quote(v, safe=".,*()")}' for k, _, v in (p.partition('=') for p in str(where).split('&')))
    st, _, h = _call('GET', f'/{table}?select=id{q}&limit=1', prefer='count=exact', extra={'Range-Unit': 'items', 'Range': '0-0'})
    rng = h.get('Content-Range', '*/0')
    return int(rng.split('/')[-1]) if rng.split('/')[-1].isdigit() else 0


def to_md(rows, cols=None):
    """사람·에이전트가 읽는 간결한 표(파이프·구분선 없이 탭 구분 CSV에 가깝게, 토큰을 줄인다)."""
    if not rows:
        return '(없음)'
    cols = cols or list(rows[0].keys())
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(cols)
    for r in rows:
        w.writerow(['' if r.get(c) is None else r.get(c) for c in cols])
    return buf.getvalue().rstrip('\n')


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='운영 상태 DB 읽기·세기')
    ap.add_argument('op', choices=['select', 'count'])
    ap.add_argument('table')
    ap.add_argument('--where', default='')
    ap.add_argument('--cols', default='*')
    ap.add_argument('--order', default='')
    ap.add_argument('--limit', default='')
    ap.add_argument('--fmt', default='csv', choices=['csv', 'json', 'md'])
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    if a.op == 'count':
        print(count(a.table, a.where or None))
        return
    rows = select(a.table, a.cols, a.where or None, a.order or None, a.limit or None)
    print(json.dumps(rows, ensure_ascii=False) if a.fmt == 'json' else to_md(rows))


if __name__ == '__main__':
    main(sys.argv[1:])
