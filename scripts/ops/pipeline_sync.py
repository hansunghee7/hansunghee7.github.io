# -*- coding: utf-8 -*-
"""수집 파이프 대장 밀도 동기화(2026-10-11): 감시 대장이 이미 아는 '마지막 성공'을 data_pipelines 에 옮긴다.
근거: 감시가 쓰는 상태 기록 C:/work/_ops/state.json(상태판 STATUS.md 와 같은 내용의 기계용 사본, jobs.toml 항목 id 로 색인).
방법(10/18 eager): 기준을 넘긴 파이프뿐 아니라 대장 last_success 가 감시의 실제 최신 성공보다 낡은 파이프도 옮긴다(freshness 기준값은 그대로).
`pipeline_db.py stale` 로 신선도를 넘긴 파이프와 감시 id 를 읽고(성공 기록이 오래된 것은 감시가 ok일 때만), 감시 상태가 ok/fail 이면 `pipeline_db.py add-run` 을 호출한다(DB 직접 쓰기 없음, 키 값은 이 코드에 없다).
근거를 못 찾은 파이프는 건드리지 않고 목록만 낸다.
사용: python scripts/ops/pipeline_sync.py [--dry] [--state 경로]"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_TOOL = str(HERE / 'pipeline_db.py')
STATE = os.environ.get('OPS_STATE_DIR', r'C:\work\_ops') + r'\state.json'
NOWIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
LAST_RE = re.compile(r'마지막\s*(?:실행|성공|갱신)?\s*(\d{2}-\d{2} \d{2}:\d{2})')
TZ_RE = re.compile(r'[+-]\d\d:\d\d$')  # f-string 식 안에 역슬래시를 못 쓰는 3.11 대응으로 밖에서 컴파일


def parse_stale_line(line):
    """'slug  이름  [상태]  ..  감시 X' -> (slug, 감시 id 또는 None, 성공기록없음 여부)"""
    line = line.strip()
    if not line or '감시' not in line:
        return None
    m = re.search(r'감시 (.+)$', line)
    watch = m.group(1).strip() if m else None
    if watch in (None, '-', ''):
        watch = None
    return line.split()[0], watch, '성공 기록 없음' in line


def parse_stale(text):
    """stale 줄을 (slug, 감시 id, 성공기록없음 여부)로 돌려준다.
    10/15 수정(타미 당직 판정): 예전엔 '성공 기록 없음'만 옮겨 적어, 한 번 성공한 뒤 기록이 멈춘 파이프 24개가 10/11부터 정체로 보였다.
    이제 오래된 성공도 대상에 넣되, 그런 줄은 감시가 ok일 때만 성공을 적는다(main)."""
    out = []
    for ln in text.splitlines():
        if ln.startswith('신선도'):
            continue
        r = parse_stale_line(ln)
        if r:
            out.append(r)
    return out


def evidence(entry):
    """감시 상태 항목 -> (ok bool, 메모) 또는 None(ok/fail 이 아니면 근거 아님)"""
    st = entry.get('status')
    if st not in ('ok', 'fail'):
        return None
    checked = str(entry.get('checked', ''))
    m = LAST_RE.search(entry.get('detail', '') or '')
    at = checked
    if m and checked[:4].isdigit():  # 'MM-DD HH:MM'에 점검 시각의 연도·시간대를 붙인다
        tz = checked[-6:] if TZ_RE.search(checked) else ''
        at = f"{checked[:4]}-{m.group(1).replace(' ', 'T')}:00{tz}"
    when = ('감시가 기록한 마지막 실행 ' + m.group(1)) if m else '감시 점검 ' + checked[:16].replace('T', ' ')
    return st == 'ok', f"pipeline_sync: 감시 {entry.get('id')} {st}, {when} (상태판 근거)", at


GH_REPOS = {'site': 'hansunghee7/hansunghee7.github.io', 'data': 'hansunghee7/carvit-insight-data'}


def gh_evidence(watch):
    """감시 대장(jobs.toml)에 없는 'gh:<site|data>:<워크플로 이름>' 파이프는 GitHub 실행 기록에서 마지막 성공을 직접 읽는다.
    10/16 타미 당직 판정: GA4·Clarity·서치콘솔 등 워크플로는 매일 성공하는데 감시 대장에 없어 근거 없음으로 4일 넘게 정체로 보였다."""
    m = re.match(r'gh:([a-z]+):(.+)$', watch or '')
    if not m or m.group(1) not in GH_REPOS:
        return None
    try:
        r = subprocess.run(['gh', 'run', 'list', '-R', GH_REPOS[m.group(1)], '--workflow', m.group(2), '--status', 'success', '-L', '1', '--json', 'updatedAt'],
                           capture_output=True, text=True, encoding='utf-8', creationflags=NOWIN, timeout=60)
        runs = json.loads(r.stdout or '[]') if r.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not runs:
        return None
    at = runs[0]['updatedAt']
    return True, f"pipeline_sync: GitHub 실행 기록 {m.group(2)} 성공 {at[:16].replace('T', ' ')} UTC", at


# 대장에 감시 id 가 비어 있는 파이프의 기본 근거(10/21: index-coverage 는 워크플로가 매일 성공하는데 감시 id 가 없어 last_success 가 10/05에 멈춘 채 경보)
DEFAULT_WATCH = {'index-coverage': 'gh:site:Fetch Index Coverage'}


def pick_evidence(watch, state, gh=None):
    """GitHub 워크플로(gh:)는 실제 실행 기록을 먼저 보고, 못 읽으면 감시 상태 파일로 내려간다.
    10/16 타미 당직 판정: 상태 파일이 02:38에 멈춰 06:40 사이트 점검 성공을 못 옮겨 9시간 정체로 보였다."""
    gh = gh or gh_evidence
    ev = gh(watch) if (watch or '').startswith('gh:') else None
    if not ev and watch and watch in state:
        ev = evidence(state[watch])
    return ev


def parse_last_success(text):
    """`pipeline_db.py last-success` 출력 -> {slug: (last_success datetime 또는 None, 감시 id 또는 None)}"""
    out = {}
    for ln in text.splitlines():
        parts = ln.split('\t')
        if len(parts) != 3:
            continue
        slug, ls, watch = parts
        out[slug] = (to_dt(ls) if ls != '-' else None, None if watch in ('-', '') else watch)
    return out


def to_dt(s):
    """ISO 문자열 -> 시간대 있는 datetime(시간대 없으면 로컬로 본다). 못 읽으면 None."""
    try:
        t = datetime.datetime.fromisoformat(str(s).strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return t.astimezone() if t.tzinfo is None else t


def ledger_is_behind(last_success, at):
    """대장 last_success 가 근거 시각보다 낡았으면 True(근거 시각을 못 읽으면 False). add-run 이 멱등 키가 없어,
    옮긴 뒤엔 ran_at=근거 시각이 되어 이 값이 거짓이 되는 것이 순차 재실행 중복을 막는 보호다(동시 실행은 못 막음)."""
    t = to_dt(at)
    if t is None:
        return False
    return last_success is None or last_success < t


def real_run_time(ev):
    """근거 시각이 '실제 마지막 실행/성공 시각'인지(감시 점검 시각이면 점검마다 새 값이라 eager 대상에서 뺀다: 점검 때마다 행이 쌓이는 것을 막는다)."""
    return '감시 점검' not in ev[1]


def plan(stale_rows, ledger, state, gh=None):
    """(todo, none) 계산. 기준을 넘긴 줄(stale_rows)과 '대장이 현실보다 낡은' 파이프(ledger 전체)를 합친다.
    성공 근거는 대장이 낡았을 때만 옮긴다. 실패 근거는 기준을 넘긴 파이프에서만 옮긴다(기존 동작)."""
    todo, none, seen = [], [], set()
    for slug, watch, no_record in stale_rows:
        seen.add(slug)
        watch = watch or DEFAULT_WATCH.get(slug)
        ev = pick_evidence(watch, state, gh)
        last = ledger.get(slug, (None, None))[0]
        if ev and ev[0] and not ledger_is_behind(last, ev[2]):
            none.append(f"{slug} (감시 {watch or '-'}, 대장이 이미 최신)")
        elif ev and (no_record or ev[0]):
            todo.append((slug, ev))
        else:
            none.append(f"{slug} (감시 {watch or '-'})")
    for slug, (last, watch) in sorted(ledger.items()):
        watch = watch or DEFAULT_WATCH.get(slug)
        if slug in seen or not watch:
            continue
        ev = pick_evidence(watch, state, gh)
        if ev and ev[0] and real_run_time(ev) and ledger_is_behind(last, ev[2]):
            todo.append((slug, ev))
    return todo, none


def run_tool(*args):
    r = subprocess.run([sys.executable, '-X', 'utf8', DB_TOOL, *args], capture_output=True, text=True, encoding='utf-8',
                       creationflags=NOWIN, timeout=60)
    return r.returncode, (r.stdout + r.stderr).strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry', action='store_true', help='기록하지 않고 계획만 출력')
    ap.add_argument('--state', default=STATE)
    a = ap.parse_args(argv)
    try:
        with open(a.state, encoding='utf-8') as f:
            state = json.load(f)
        if not isinstance(state, dict):
            raise ValueError('최상위가 객체가 아님')
    except (OSError, ValueError) as e:
        print(f'상태 파일 오류: {a.state} ({e})')
        sys.exit(2)
    code, out = run_tool('stale')
    if code:
        sys.exit('stale 조회 실패: ' + out[:200])
    rows = parse_stale(out)
    code, lout = run_tool('last-success')
    if code:
        sys.exit('last-success 조회 실패: ' + lout[:200])
    todo, none = plan(rows, parse_last_success(lout), state)
    print(f"stale {len(rows)}개 중 옮길 것 {len(todo)}, 근거 없음 {len(none)}")
    for slug, (ok, note, at) in todo:
        flag = 'yes' if ok else 'no'
        if a.dry:
            print(f'[dry] add-run {slug} --ok {flag} --at {at} --note "{note}"')
            continue
        c, o = run_tool('add-run', slug, '--ok', flag, '--at', at, '--note', note)
        print(f"{slug}: {o.splitlines()[-1] if o else c}")
    print('근거 없음: ' + (', '.join(none) or '없음'))


if __name__ == '__main__':
    main()
