# -*- coding: utf-8 -*-
"""전체 md 문서를 운영 상태 DB의 docs 표(목록·요약·제목·본문)에 적재한다(N156 검색 1단계, 2026-10-05 탐, 사장님 허용: 로컬 저장소들의 md를 내 비공개 Supabase 프로젝트 simplifier-ops-data의 docs 표에 적재).
원본은 읽기만 한다. 검색은 opsdb로 하고, 임베딩은 embed_docs.py(로컬 bge-m3)로 만든다. 표 정의: cxo-db reports/n155/schema_v2_phaseB.sql.
주의: 같은 경로를 다시 적재하면 summary가 원래대로 돌아간다(색인 보강으로 붙인 [태그]가 지워진다). 보강 칸은 phaseC.sql로 summary와 분리할 예정이다.
제외: 진행상황 아카이브 폴더, site-packages·dist-packages(파이썬 패키지 문서), 3MB 초과 파일, 숨김·백업·가상환경 폴더. 비공개 저장소 문서도 이 비공개 DB에만 들어가며 외부 모델로 보내지 않는다.
사용: python scripts/ops/import_docs_to_opsdb.py [--dry]"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

ROOTS = {'hansunghee7.github.io': r'C:\work\hansunghee7.github.io', 'shorts-lab': r'C:\work\shorts-lab', 'solar-bible': r'C:\work\solar-bible',
         'simplifier-cxo-db': r'C:\work\simplifier-cxo-db', 'saegim-pass-dev': r'C:\work\saegim-pass-dev', '_ops': r'C:\work\_ops'}
SKIP = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'omniroute-iso', 'bench_c_root', 'dex_wd', 'dex_iso', '.claude', 'backup', 'backup_1003', 'backup_1004', '_site', 'log_assets', '진행상황_아카이브',
        'site-packages', 'dist-packages'}  # 파이썬 패키지 문서 노이즈(10/7 실측 52개·약 950KB, N174)


PUBLIC_REPOS = {'hansunghee7.github.io'}  # 공개 저장소(GitHub public). 나머지는 비공개. doc_sections.visibility 값의 기준(N174)


def visibility_of(repo):
    return 'public' if repo in PUBLIC_REPOS else 'private'


def is_skipped(parts, size):
    return any(x in SKIP for x in parts) or size > 3_000_000


def doc_row(repo, root, p):
    try:
        txt = p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    txt = txt.replace('\x00', '')
    heads = [l.strip() for l in txt.splitlines() if l.lstrip().startswith('#')]
    title = next((h.lstrip('#').strip() for h in heads), p.stem)
    st = p.stat()
    return {'path': f'{repo}/' + str(p.relative_to(root)).replace('\\', '/'), 'repo': repo, 'title': title[:200], 'summary': re.sub(r'\s+', ' ', txt)[:600],
            'headings': '\n'.join(heads)[:6000], 'body': txt[:400000], 'bytes': st.st_size, 'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d'), 'source': 'md-import'}


def collect():
    rows = []
    for repo, root in ROOTS.items():
        r = Path(root)
        if not r.exists():
            continue
        for p in r.rglob('*.md'):
            if is_skipped(p.parts, p.stat().st_size):
                continue
            d = doc_row(repo, r, p)
            if d:
                rows.append(d)
    return rows


def main():
    rows = collect()
    print(f'문서 {len(rows)}개, 본문 합계 {sum(len(r["body"].encode("utf-8")) for r in rows) // 1024}KB')
    if '--dry' in sys.argv:
        return
    n = 0
    for i in range(0, len(rows), 40):
        n += opsdb.upsert('docs', rows[i:i + 40], 'path')
    print('적재', n, '| DB 행 수', opsdb.count('docs'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
