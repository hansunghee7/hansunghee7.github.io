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


def main():
    P = plan()
    for t, rows in P.items():
        print(f'{t}: {len(rows)}행')
    if '--dry' in sys.argv:
        return
    for t, rows in P.items():
        opsdb.delete(t, {'id': 'gt.0'})
        for i in range(0, len(rows), 200):
            opsdb.insert(t, rows[i:i + 200])
    print('확인(DB 행 수):', {t: opsdb.count(t) for t in P})
    bad = [t for t, rows in P.items() if opsdb.count(t) != len(rows)]
    print('불일치:', bad or '없음')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
