# -*- coding: utf-8 -*-
"""전체 md의 표를 전수조사한다(N156 도서관 전수조사, 2026-10-05 탐). 모델을 쓰지 않는 스크립트라 토큰이 들지 않는다.
각 md에서 마크다운 표(머리줄 + 구분줄 + 행들)를 찾아 파일·줄·머리글·행 수·최근 수정일을 목록으로 만든다. CSV 파일도 행 수를 센다.
출력: C:/work/_ops/n156_inventory/tables.json 과 tables.csv(행 수 내림차순), 요약은 화면에 20줄.
사용: python scripts/ops/md_table_inventory.py"""
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOTS = [r'C:\work\hansunghee7.github.io', r'C:\work\shorts-lab', r'C:\work\solar-bible', r'C:\work\simplifier-cxo-db', r'C:\work\saegim-pass-dev', r'C:\work\_ops']
SKIP = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'omniroute-iso', 'bench_c_root', 'dex_wd', 'dex_iso', '.claude', 'backup', 'backup_1003', 'backup_1004', '_site', 'log_assets'}
OUT = Path(r'C:\work\_ops\n156_inventory')
SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')


def cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def scan_md(p):
    try:
        lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    out, i = [], 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith('|') and SEP.match(lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                j += 1
            hdr = cells(lines[i])
            out.append({'file': str(p), 'line': i + 1, 'kind': 'md-table', 'headers': hdr, 'cols': len(hdr), 'rows': j - i - 2})
            i = j
        else:
            i += 1
    return out


def scan_csv(p):
    try:
        with p.open(encoding='utf-8', errors='replace', newline='') as f:
            rows = list(csv.reader(f))
    except OSError:
        return []
    if not rows:
        return []
    return [{'file': str(p), 'line': 1, 'kind': 'csv', 'headers': rows[0], 'cols': len(rows[0]), 'rows': len(rows) - 1}]


def walk(root):
    for p in Path(root).rglob('*'):
        if any(part in SKIP for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in ('.md', '.csv') and p.stat().st_size < 3_000_000:
            yield p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    found, nfiles = [], 0
    for root in ROOTS:
        if not Path(root).exists():
            continue
        for p in walk(root):
            nfiles += 1
            items = scan_md(p) if p.suffix.lower() == '.md' else scan_csv(p)
            mt = datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d')
            for it in items:
                it['mtime'] = mt
                found.append(it)
    found.sort(key=lambda x: -x['rows'])
    (OUT / 'tables.json').write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding='utf-8')
    with (OUT / 'tables.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rows', 'cols', 'kind', 'mtime', 'file', 'line', 'headers'])
        for it in found:
            w.writerow([it['rows'], it['cols'], it['kind'], it['mtime'], it['file'], it['line'], ' | '.join(it['headers'])[:160]])
    big = [x for x in found if x['rows'] >= 10]
    print(f'파일 {nfiles}개 훑음, 표 {len(found)}개 발견(행 10개 이상 {len(big)}개). 목록: {OUT}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
