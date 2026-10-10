# -*- coding: utf-8 -*-
"""수집 파이프 대장 밀도 동기화(2026-10-11): 감시 대장이 이미 아는 '마지막 성공'을 data_pipelines 에 옮긴다.
근거: 감시가 쓰는 상태 기록 C:/work/_ops/state.json(상태판 STATUS.md 와 같은 내용의 기계용 사본, jobs.toml 항목 id 로 색인).
방법: `pipeline_db.py stale` 로 성공 기록 없는 파이프와 감시 id 를 읽고, 감시 상태가 ok/fail 이면 `pipeline_db.py add-run` 을 호출한다(DB 직접 쓰기 없음, 키 값은 이 코드에 없다).
근거를 못 찾은 파이프는 건드리지 않고 목록만 낸다.
사용: python scripts/ops/pipeline_sync.py [--dry] [--state 경로]"""
import argparse
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
    """'성공 기록 없음' 때문에 stale 인 줄만 (slug, 감시 id)로 돌려준다(다른 이유의 stale 은 건드리지 않음)."""
    out = []
    for ln in text.splitlines():
        if ln.startswith('신선도'):
            continue
        r = parse_stale_line(ln)
        if r and r[2]:
            out.append(r[:2])
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
        at = f"{checked[:4]}-{m.group(1).replace(' ', 'T')}:00{checked[-6:] if re.search(r'[+-]\d\d:\d\d$', checked) else ''}"
    when = ('감시가 기록한 마지막 실행 ' + m.group(1)) if m else '감시 점검 ' + checked[:16].replace('T', ' ')
    return st == 'ok', f"pipeline_sync: 감시 {entry.get('id')} {st}, {when} (상태판 근거)", at


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
    todo, none = [], []
    for slug, watch in rows:
        ev = evidence(state[watch]) if watch and watch in state else None
        if ev:
            todo.append((slug, ev))
        else:
            none.append(f"{slug} (감시 {watch or '-'})")
    print(f"stale {len(rows)}개 중 근거 있음 {len(todo)}, 근거 없음 {len(none)}")
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
