# -*- coding: utf-8 -*-
"""하이~ 브리핑(N156, 2026-10-05 탐, 사장님 관찰 "하이·바이 때 컨텍스트 5~10%가 DB형 검색으로 채워진다"): 세션 시작 의식이 읽는 자료를 운영 상태 DB 질의 한 번으로 줄인다.
출력: ① 내 최신 인수인계 블록 원문(CLAUDE.md 규칙: 요약 금지) ② 내 열린 건 중 사람 확인 필요·진행·확인필요 목록(번호·제목만) ③ 감시 상태판의 문제 줄(🔴·🟡)만 ④ DB 기준 시각(DB가 최대 1시간 뒤처질 수 있음을 알리기 위해).
읽지 않는 것: 업무대장 전체(탐 약 146KB), 상태판 전체, 진행상황.md. 필요한 건은 `opsdb.py select tasks --where "no=eq.N151"`로 그 행만 읽는다.
사용: python scripts/ops/session_brief.py 탐 [--full-list]"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

STATUS = Path(r'C:\work\_ops\STATUS.md')
SOURCES = [Path(r'C:\work\hansunghee7.github.io\docs\진행상황.md'), Path(r'C:\work\shorts-lab\pilot-shorts2\KPI_과제.md')]  # 인수인계 정본


def ensure_fresh():
    """인수인계 정본(md)이 DB 마지막 동기화보다 새로우면 바로 한 번 동기화한다(바이 직후 새 세션이 하이를 하면 시간당 자동 동기화를 기다리지 않게)."""
    import subprocess
    from datetime import timezone
    last = opsdb.select('tasks', 'imported_at', order='id.desc', limit=1)
    if last:
        at = datetime.fromisoformat(last[0]['imported_at']).astimezone(timezone.utc).timestamp()
        if all(s.stat().st_mtime <= at for s in SOURCES if s.exists()):
            return False
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'import_ops_tables.py')], capture_output=True, timeout=240)
    return True


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    who = sys.argv[1] if len(sys.argv) > 1 else '탐'
    synced = ensure_fresh()
    full = '--full-list' in sys.argv
    h = opsdb.select('tasks', 'title,raw', where={'owner': f'eq.{who}', 'section': 'eq.handoff', 'no': 'eq.1'}, limit=1)
    print(f'===== {who} 최신 인수인계(원문)' + (' (md가 DB보다 새로워 방금 동기화함)' if synced else '') + ' =====')
    if h:
        print('## [' + who + '] ' + h[0]['raw'].get('head', '') + '\n' + h[0]['raw'].get('body', ''))
    else:
        print('(DB에 인수인계 블록 없음: 진행상황.md를 직접 확인하세요)')
    rows = opsdb.select('tasks', 'no,title,status,raw', where={'owner': f'eq.{who}', 'section': 'eq.open'}, order='id.asc', limit=300)
    def human(r):
        body = (r.get('raw') or {}).get('body', '')
        return r['status'] == '사장님' or bool(re.search(r'다음\(사장님\)|정하실 것[^\n]{0,6}[:：]\s*[^없\n]', body))
    H = [r for r in rows if human(r)]
    P = [r for r in rows if r['status'] == '진행' and r not in H]
    C = [r for r in rows if r['status'] == '확인필요' and r not in H]
    W = [r for r in rows if r['status'] == '대기' and r not in H]
    def line(r, n=58):
        return f"- {r['no'] or '-'} [{r['status']}] {r['title'][:n]}"
    print(f'\n===== {who} 열린 건 {len(rows)}개 (진행 {len(P)}, 확인필요 {len(C)}, 대기 {len(W)}, 사람 확인 필요 {len(H)}) =====')
    print('-- 사람 확인 필요'); [print(line(r)) for r in H]
    print('-- 진행'); [print(line(r)) for r in P]
    print('-- 확인필요'); [print(line(r)) for r in C]
    print('-- 대기' + ('' if full else f' (처음 8개만, 전체는 --full-list)')); [print(line(r)) for r in (W if full else W[:8])]
    print('\n===== 감시 상태판 문제 줄 =====')
    try:
        bad = [l.strip() for l in STATUS.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip().startswith(('🔴', '🟡', '| 🔴', '| 🟡'))]
        print('\n'.join(b[:150] for b in bad[:10]) if bad else '문제 없음')
    except OSError:
        print('(상태판을 못 읽음)')
    last = opsdb.select('tasks', 'imported_at', order='id.desc', limit=1)
    print(f"\nDB 기준 시각(마지막 동기화): {last[0]['imported_at'] if last else '알 수 없음'}  | 현재 {datetime.now():%H:%M}  (md가 정본, DB는 최대 1시간 뒤처질 수 있음)")


if __name__ == '__main__':
    main()
