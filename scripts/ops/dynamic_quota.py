# -*- coding: utf-8 -*-
"""다이나믹 한도(N163, 2026-10-05 탐, 사장님 지시 "일일 측정을 해서 일사용량을 못 채웠으면 뒤에 한도가 늘어나는 다이나믹 한도로"):
① GCP 크레딧 일 상한은 고정값이 아니라 (남은 잔액 × 안전율) ÷ 만료까지 남은 일수로 매일 다시 계산한다. 오늘 덜 쓰면 내일 상한이 자동으로 올라간다.
② 덱스·비티·타미의 하루 목표 호출 수는 기본값 + 이월분이다. 못 채운 만큼(부족분)이 이월분이 되어 다음 날 목표가 올라가고(천장 있음), 채우면 이월분이 줄어든다.
상태 파일: C:/work/_ops/dynamic_quota.json (일별 기록 records, 이월분 carry). 크레딧 설정: C:/work/_ops/vertex_budget.json (잔액·기준일·만료일·안전율, 결제 화면과 대조한 뒤 고친다).
사용: python scripts/ops/dynamic_quota.py status | measure     (measure = 어제까지 완료된 날의 기록을 남기고 오늘 목표를 계산, 하루 1회 감시 등록, 여러 번 돌려도 같은 결과)"""
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

OPS = Path(r'C:\work\_ops')
STATE = OPS / 'dynamic_quota.json'
BUDGET = OPS / 'vertex_budget.json'
BASE = {'덱스': 25, '비티': 10, '타미': 5}      # 하루 기본 목표 호출 수(램프업 시작값, 덱스는 한도 신호가 주 1~2회 나올 때까지 올린다)
CEIL = {'덱스': 60, '비티': 40, '타미': 20}     # 천장(무한 이월 방지)
ALIAS = {'덱스': ['덱스'], '비티': ['비티', '비티-sonnet', '비티-라우터', '비티-vertex'], '타미': ['타미']}
CARRY_DECAY = 0.5                               # 지난 이월분은 매일 절반만 남긴다
DEFAULT_BUDGET = {'balance': 326145, 'as_of': '2026-10-03', 'expiry': '2026-12-23', 'safety': 0.85, 'max_day': 15000,
                  'observe_until': '2026-10-12', 'floor_remaining': 100000}  # 관찰 기간(사장님 10/5 "7일은 그냥 써보죠"): 이 날까지 일 상한 없이 쓰되 남은 잔액이 floor 아래로 내려가면 평시 계산으로 복귀


def load_state():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'records': {}, 'carry': {a: 0 for a in BASE}}


def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding='utf-8')


def budget():
    try:
        return {**DEFAULT_BUDGET, **json.loads(BUDGET.read_text(encoding='utf-8'))}
    except (OSError, ValueError):
        return dict(DEFAULT_BUDGET)


def vertex_spent(start, before=None):
    """vertex_usage.csv에서 start 이상(before 미만) 추정 비용 합."""
    f = OPS / 'vertex_usage.csv'
    if not f.exists():
        return 0.0
    tot = 0.0
    for r in csv.DictReader(f.open(encoding='utf-8')):
        d = r['time'][:10]
        if d >= start and (before is None or d < before):
            tot += float(r['est_krw'] or 0)
    return tot


def remaining(today=None):
    """남은 크레딧 추정(원) = 기준 잔액 − 기준일부터 어제까지 API 실사용(오늘 분 제외)."""
    b = budget()
    today = today or date.today()
    try:
        import gcp_usage
        spent = gcp_usage.spent_since(b['as_of'], before=today.isoformat())
    except Exception:  # noqa: BLE001
        spent = vertex_spent(b['as_of'], before=today.isoformat())
    return round(b['balance'] - spent, 1)


def vertex_day_cap(today=None):
    """오늘의 GCP 일 상한(원) = (잔액 − 기준일부터 어제까지 쓴 추정 비용) × 안전율 ÷ 만료까지 남은 일수. 덜 쓰면 자동으로 오른다."""
    b = budget()
    today = today or date.today()
    try:  # 실제 사용량(Cloud Monitoring 토큰 × 공개 단가). API가 막히면 우리 호출 기록으로 대체
        import gcp_usage
        spent = gcp_usage.spent_since(b['as_of'], before=today.isoformat())
    except Exception:  # noqa: BLE001
        spent = vertex_spent(b['as_of'], before=today.isoformat())
    days_left = max(1, (date.fromisoformat(b['expiry']) - today).days)
    if b.get('observe_until') and today.isoformat() <= b['observe_until'] and (b['balance'] - spent) > b['floor_remaining']:
        return round(b['balance'] - spent - b['floor_remaining'], 1)  # 관찰 기간: 사실상 상한 없음(바닥선까지 허용)
    cap = (b['balance'] - spent) * b['safety'] / days_left
    return round(min(max(cap, 0.0), b['max_day']), 1)


def used_on(agent, day):
    f = OPS / 'agent_calls.csv'
    if not f.exists():
        return 0
    names = ALIAS[agent]
    return sum(1 for r in csv.DictReader(f.open(encoding='utf-8')) if r['who'] in names and r['time'].startswith(day))


def target_for(agent, carry):
    return int(min(CEIL[agent], BASE[agent] + round(carry)))


def measure(today=None):
    """어제까지 비어 있는 날의 기록을 채우고(그날 목표 대비 사용), 이월분을 갱신한 뒤 오늘 목표를 돌려준다."""
    today = today or date.today()
    s = load_state()
    s.setdefault('carry', {a: 0 for a in BASE})
    recs = s.setdefault('records', {})
    days = sorted(recs)
    start = date.fromisoformat(days[-1]) + timedelta(days=1) if days else today  # 제도 시작일(오늘) 이전은 소급 채점하지 않는다
    d = start
    while d < today:
        key = d.isoformat()
        rec = {}
        for a in BASE:
            carry = s['carry'].get(a, 0)
            tgt = target_for(a, carry)
            used = used_on(a, key)
            deficit = max(0, tgt - used)
            s['carry'][a] = round(CARRY_DECAY * carry + deficit, 1) if deficit else round(CARRY_DECAY * carry, 1)
            rec[a] = {'target': tgt, 'used': used, 'carry_after': s['carry'][a]}
        recs[key] = rec
        d += timedelta(days=1)
    try:  # 일별 실제 지출(API)을 상태에 남겨 관찰 기간 끝에 곡선을 본다
        import gcp_usage
        s['gcp_daily'] = {d: {'krw': v['krw'], 'in': v['input'], 'out': v['output']} for d, v in sorted(gcp_usage.daily_usage().items()) if d >= budget()['as_of']}
    except Exception:  # noqa: BLE001
        pass
    s['today'] = {'date': today.isoformat(), 'targets': {a: target_for(a, s['carry'].get(a, 0)) for a in BASE}, 'vertex_day_cap': vertex_day_cap(today)}
    save_state(s)
    return s


def status():
    s = measure()
    t = s['today']
    print(f"[다이나믹 한도 {t['date']}] GCP 일 상한 ₩{t['vertex_day_cap']:,} (잔액·남은 일수로 매일 재계산)")
    for a in BASE:
        used = used_on(a, t['date'])
        print(f"  {a}: 오늘 목표 {t['targets'][a]}회(기본 {BASE[a]}+이월 {s['carry'].get(a, 0)}, 천장 {CEIL[a]}) / 오늘 사용 {used}회")
    for k in sorted(s['records'])[-5:]:
        print('  기록', k, {a: f"{v['used']}/{v['target']}" for a, v in s['records'][k].items()})


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'measure':
        s = measure()
        print('오늘 목표', s['today']['targets'], '| GCP 일 상한', s['today']['vertex_day_cap'], '| 이월', s['carry'])
    else:
        status()
