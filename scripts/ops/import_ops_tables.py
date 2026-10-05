# -*- coding: utf-8 -*-
"""전수조사 이관 1단계(N156, 2026-10-05 탐): 로그 CSV 3개와 업무대장·SNS·성과·계정 md 표를 운영 상태 DB로 복사한다.
원본은 읽기만 한다(md·csv는 그대로). 다시 실행하면 각 표를 비우고 다시 채운다(복사본이라 안전). 모든 행의 원본 전체를 raw(jsonb)에도 저장해 정보 손실이 없게 한다.
표 정의: cxo-db reports/n155/schema_v1_phaseA.sql. 사용: python scripts/ops/import_ops_tables.py [--dry]"""
import csv
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

KST = timezone(timedelta(hours=9))
REPO = Path(r'C:\work\hansunghee7.github.io')
SHORTS = Path(r'C:\work\shorts-lab\pilot-shorts2')
OPS = Path(r'C:\work\_ops')
SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')
PERSONAS = {'탐': 'docs/탐_업무대장.md', '핏': 'docs/핏_업무대장.md', '노트': 'docs/노트_업무대장.md', '마야': 'docs/마야_업무대장.md', '지투': 'docs/지투_업무대장.md', '클라우드탐': 'docs/클라우드탐_업무대장.md'}


def ts(s):
    try:
        return datetime.strptime((s or '').strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST).isoformat()
    except ValueError:
        return None


def num(s, cast=float):
    s = re.sub(r'[,\s%원]', '', s or '')
    try:
        return cast(s) if s else None
    except ValueError:
        return None


def md_tables(path):
    """파일의 모든 마크다운 표를 (헤더, 행 dict 목록)으로 돌려준다."""
    try:
        lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    out, i = [], 0
    cells = lambda l: [c.strip() for c in l.strip().strip('|').split('|')]
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith('|') and SEP.match(lines[i + 1]):
            hdr = cells(lines[i])
            j, rows = i + 2, []
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                c = cells(lines[j])
                c += [''] * (len(hdr) - len(c))
                rows.append(dict(zip(hdr, c[:len(hdr)])))
                j += 1
            out.append((hdr, rows))
            i = j
        else:
            i += 1
    return out


def read_csv(path):
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        return list(csv.DictReader(f))


def pick(d, *names):
    for n in names:
        if n in d and d[n] != '':
            return d[n]
    return None


def parse_tam_ledger(path):
    """탐 업무대장은 표가 아니라 `### [상태] N번: 제목` 제목 아래 불릿으로 쓴다. 제목 한 줄이 한 건이고, 본문 전체는 raw.body에 그대로 보존한다."""
    try:
        lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    blocks, cur = [], None
    for ln in lines:
        m = re.match(r'^###\s*\[([^\]]+)\]\s*(.*)$', ln)
        if m:
            cur = {'status': m[1].strip(), 'head': m[2].strip(), 'body': []}
            blocks.append(cur)
        elif ln.startswith('#') and not ln.startswith('###'):
            cur = None
        elif cur is not None:
            cur['body'].append(ln)
    out = []
    for b in blocks:
        n = re.match(r'^(N\d+)\s*[:：]\s*(.*)$', b['head'])
        no, title = (n[1], n[2]) if n else (None, b['head'])
        body = '\n'.join(b['body']).strip()

        def bullet(prefix):
            for ln in b['body']:
                if ln.lstrip('- ').startswith(prefix):
                    return ln.lstrip('- ').strip()[:1500]
            return None
        closed = b['status'].startswith('완료')
        out.append({'owner': '탐', 'section': 'closed' if closed else 'open', 'no': no, 'title': title[:300], 'status': b['status'], 'source_date': None,
                    'next_action': bullet('다음'), 'evidence': bullet('[완료'), 'result': bullet('결론'), 'cost': None, 'decider': None,
                    'raw': {'head': b['head'], 'body': body}, 'source': PERSONAS['탐']})
    return out


def parse_handoffs(path, keep=3, owner_override=None, source=None):
    """진행상황.md의 인수인계 블록(`## [페르소나] 상태: ...`)을 페르소나별 최신 keep개만 읽는다(파일 안에서 위쪽이 최신). 본문 전체를 raw.body에 보존한다."""
    try:
        lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    blocks, cur = [], None
    for ln in lines:
        m = re.match(r'^##\s*\[([^\]]+)\]\s*(.*)$', ln)
        if m:
            cur = {'owner': m[1].strip(), 'head': m[2].strip(), 'body': []}
            blocks.append(cur)
        elif ln.startswith('## '):
            cur = None
        elif cur is not None:
            cur['body'].append(ln)
    seen, out = {}, []
    for b in blocks:
        if owner_override:
            b['owner'] = owner_override  # 예: 핏은 '[핏(로컬)]' 블록을 '핏'으로 통일
        seen[b['owner']] = seen.get(b['owner'], 0) + 1
        if seen[b['owner']] > keep:
            continue
        out.append({'owner': b['owner'], 'section': 'handoff', 'no': str(seen[b['owner']]), 'title': b['head'][:300], 'status': b['head'][:40], 'source_date': None, 'next_action': None, 'evidence': None,
                    'result': None, 'cost': None, 'decider': None, 'raw': {'head': b['head'], 'body': chr(10).join(b['body']).strip()}, 'source': source or 'docs/진행상황.md'})
    return out


PROCESS_DOCS = {'탐': REPO / 'docs/탐_프로세스표.md', '핏': REPO / 'docs/핏_프로세스표.md', '마야': REPO / 'docs/마야_프로세스표.md', '지투': REPO / 'docs/지투_프로세스표.md',
                '노트': REPO / 'docs/노트_프로세스표.md', '클라우드탐': REPO / 'docs/클라우드탐_프로세스표.md',
                '핏/보이스': SHORTS / '보이스메이킹_프로세스표.md', '핏/파이프라인': SHORTS / 'GENERATION_PIPELINES.md'}
BOSS_LINE = re.compile(r'사장님[^\n]{0,20}(지시|결정|확정|정정|승인|합의|요청)|\b20\d\d-\d\d-\d\d\b[^\n]{0,12}사장님')


def parse_process_docs():
    """공정 문서(프로세스표·파이프라인)를 절 단위(최대 6천 자, 넘으면 ### 로 더 쪼갬)로 잘라 tasks 표 section='process' 행으로 만든다(G2, 사장님 10/5:
    에이전트가 일하는 단계에서 그 단계의 사장님 지시만 읽게 하려는 목적, 문서 전체를 읽는 토큰을 줄인다). 읽기는 scripts/ops/proc.py."""
    rows = []
    for owner, path in PROCESS_DOCS.items():
        try:
            text = Path(path).read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
        except OSError:
            continue
        parts = re.split(r'(?m)^(?=## )', text)
        units = []
        for pt in parts:
            if len(pt) > 6000 and '\n### ' in pt:
                head = pt.split('\n', 1)[0]
                for sub in re.split(r'(?m)^(?=### )', pt):
                    if sub.strip():
                        units.append((head if sub.startswith('## ') else head + ' / ' + sub.split('\n', 1)[0], sub))
            elif pt.strip():
                units.append((pt.split('\n', 1)[0], pt))
        for i, (title, body) in enumerate(units, 1):
            boss = [l.strip()[:300] for l in body.split('\n') if BOSS_LINE.search(l)][:12]
            rows.append({'owner': owner, 'section': 'process', 'no': str(i), 'title': title.lstrip('# ').strip()[:200], 'status': '', 'source_date': None,
                         'next_action': None, 'evidence': None, 'result': None, 'cost': None, 'decider': None,  # 다른 행과 열 이름을 맞춘다(한 번에 넣을 때 필요)
                         'raw': {'body': body[:12000], 'boss_lines': boss, 'bytes': len(body.encode('utf-8'))}, 'source': Path(path).name})
    return rows


def plan():
    P = {}
    P['agent_calls'] = [{'called_at': ts(r['time']), 'who': r['who'], 'sec': num(r['sec']), 'rc': num(r['rc'], int), 'out_bytes': num(r['out_bytes'], int), 'limit_hit': r.get('limit_hit'), 'source': 'agent_calls.csv'} for r in read_csv(OPS / 'agent_calls.csv')]
    P['gpu_gate_log'] = [{'logged_at': ts(r['time']), 'who': r['who'], 'need_gb': num(r['need_gb']), 'free_gb': num(r['free_gb']), 'result': r['result'], 'note': r['note'], 'source': 'gpu_gate_log.csv'} for r in read_csv(OPS / 'gpu_gate_log.csv')]
    P['vertex_usage'] = [{'used_at': ts(r['time']), 'who': r['who'], 'model': r['model'], 'search': num(r['search'], int), 'in_tok': num(r['in_tok'], int), 'out_tok': num(r['out_tok'], int),
                          'search_q': num(r['search_q'], int), 'est_krw': num(r['est_krw']), 'sec': num(r['sec']), 'rc': num(r['rc'], int), 'source': 'vertex_usage.csv'} for r in read_csv(OPS / 'vertex_usage.csv')]
    tasks = []
    for owner, rel in PERSONAS.items():
        for hdr, rows in md_tables(REPO / rel):
            if len(hdr) < 3 or hdr[0] != '#' or hdr[1] != '안건':
                continue
            sec = 'closed' if '닫은 날' in hdr else ('open' if ('다음 행동' in hdr or '상태' in hdr) else 'history')
            for r in rows:
                tasks.append({'owner': owner, 'section': sec, 'no': r.get('#'), 'title': r.get('안건'), 'status': r.get('상태') or ('닫힘' if sec == 'closed' else None),
                              'source_date': pick(r, '출처·날짜', '날짜·근거', '닫은 날', '날짜'), 'next_action': r.get('다음 행동'), 'evidence': pick(r, '완료 증거', '증거'),
                              'result': r.get('결과'), 'cost': r.get('비용'), 'decider': r.get('결정자'), 'raw': r, 'source': rel})
    tasks += parse_tam_ledger(REPO / PERSONAS['탐'])
    tasks += parse_handoffs(REPO / 'docs/진행상황.md')
    tasks += parse_process_docs()
    tasks += parse_handoffs(SHORTS / 'KPI_과제.md', owner_override='핏', source='shorts-lab pilot-shorts2/KPI_과제.md')  # 핏의 인수인계 정본
    P['tasks'] = tasks
    P['sns_posts'] = [{'post_date': r.get('날짜'), 'title': r.get('글(원문)'), 'channel': r.get('채널'), 'method': r.get('방식'), 'status': r.get('상태'), 'scheduled': r.get('예약/발행 시각'), 'note': r.get('참고'), 'raw': r, 'source': 'docs/SNS_등록대장.md'}
                      for hdr, rows in md_tables(REPO / 'docs/SNS_등록대장.md') if hdr[:2] == ['날짜', '글(원문)'] for r in rows]
    P['kpi_daily'] = [{'day': r.get('날짜'), 'yt_subs': r.get('유튜브 구독(증감)'), 'ig_followers': r.get('인스타 새 팔로워'), 'naver_followers': r.get('네이버 팔로워'), 'yt_daily_views': r.get('유튜브 하루 조회'), 'raw': r, 'source': 'KPI_팔로워.md'}
                      for hdr, rows in md_tables(SHORTS / 'KPI_팔로워.md') if hdr[:2] == ['날짜', '유튜브 구독(증감)'] for r in rows]
    P['video_perf'] = [{'published': r.get('발행'), 'category': r.get('카테고리'), 'title': r.get('제목'), 'elapsed_days': r.get('경과일'), 'views': r.get('조회'), 'per_day': r.get('하루 평균'), 'watch_pct': r.get('시청 비율(%)'),
                        'subs_gain': r.get('구독+'), 'shares': r.get('공유'), 'raw': r, 'source': '카테고리_성과표.md'}
                       for hdr, rows in md_tables(SHORTS / '카테고리_성과표.md') if hdr[:3] == ['발행', '카테고리', '제목'] for r in rows]
    P['accounts'] = [{'kind': r.get('구분'), 'display_name': r.get('이름(표시)'), 'email_partial': r.get('이메일(일부)'), 'flow_slot': r.get('Flow 슬롯'), 'balance': r.get('잔액'), 'measured': r.get('측정'), 'daily_refill': r.get('매일 채워지나'), 'raw': r, 'source': 'shorts-lab 계정_현황표.md'}
                     for hdr, rows in md_tables(Path(r'C:\work\shorts-lab\계정_현황표.md')) if hdr[:2] == ['구분', '이름(표시)'] for r in rows]
    return P


LOGS = ('agent_calls', 'gpu_gate_log', 'vertex_usage')
LOG_TIME = {'agent_calls': 'called_at', 'gpu_gate_log': 'logged_at', 'vertex_usage': 'used_at'}
LOG_EXTRA = {'agent_calls': 'sec', 'gpu_gate_log': 'result', 'vertex_usage': 'in_tok'}


def log_key(t, r):
    """로그 한 줄의 비교 키: 시각(UTC 초)·누가·표별 한 칸. DB는 UTC, CSV는 KST로 와서 같은 시각으로 맞춘다."""
    at = r.get(LOG_TIME[t])
    try:
        at = datetime.fromisoformat(at).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if at else ''
    except ValueError:
        at = str(at)
    ex = r.get(LOG_EXTRA[t])
    return (at, r.get('who'), float(ex) if isinstance(ex, (int, float)) else ex)  # 계속 이어 붙는 로그(쓰는 스크립트는 건드리지 않고, DB에 없는 뒷부분만 이어 붙인다)


def insert_all(t, rows):
    for i in range(0, len(rows), 200):
        opsdb.insert(t, rows[i:i + 200])


def last_id(t):
    r = opsdb.select(t, 'id', order='id.desc', limit=1)
    return r[0]['id'] if r else 0


def main():
    P = plan()
    for t, rows in P.items():
        print(f'{t}: {len(rows)}행')
    if '--dry' in sys.argv:
        return
    for t, rows in P.items():
        if t in LOGS and '--full' not in sys.argv:
            # 로그는 지우지 않고 DB에 없는 줄만 채운다. 관문 같은 도구가 DB에 직접 쓰기 시작해도 중복이 생기지 않게 시각·누가·결과 키로 비교한다
            tcol = LOG_TIME[t]
            have = {log_key(t, r) for r in opsdb.select(t, tcol + ',who,' + LOG_EXTRA[t], limit=100000)}
            insert_all(t, [r for r in rows if log_key(t, r) not in have])
            continue
        # 표 전체 교체: 새 행을 먼저 넣고 옛 행을 지운다(비는 순간이 없다)
        old = last_id(t)
        insert_all(t, rows)
        if old:
            # 에이전트가 직접 쓴 작업 기록(section=worklog, worklog.py)은 문서에서 오는 행이 아니므로 지우지 않는다(10/5, 대장 N156 G2)
            opsdb.delete(t, {'id': f'lte.{old}', 'section': 'not.in.(worklog,step,run)'} if t == 'tasks' else {'id': f'lte.{old}'})
    counts = {t: (opsdb.count(t, {'section': 'not.in.(worklog,step,run)'}) if t == 'tasks' else opsdb.count(t)) for t in P}
    # 로그 표는 도구가 DB에 직접 쓴 기록이 더 있을 수 있어 DB ≥ 원본이면 정상, 나머지 표는 같아야 정상
    bad = [t for t, rows in P.items() if (counts[t] < len(rows) if t in LOGS else counts[t] != len(rows))]
    print('확인(DB 행 수):', counts)
    print('불일치:', bad or '없음')
    if bad:
        sys.exit(1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
