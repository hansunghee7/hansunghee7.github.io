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
try:
    import opsdb  # noqa: E402
except Exception:  # 클라우드엔 운영 DB 설정이 없다
    opsdb = None

STATUS = Path(r'C:\work\_ops\STATUS.md')
SOURCES = [Path(r'C:\work\hansunghee7.github.io\docs\진행상황.md'), Path(r'C:\work\shorts-lab\pilot-shorts2\KPI_과제.md')]  # 인수인계 정본


ORCH_LINES = [
    "===== 오케스트레이션 2.0 기본값 (사장님 지시 2026-10-11, 모든 에이전트) =====",
    "- 직접 손일(반복 Bash·수집·측정)보다 위임이 기본: 서브에이전트·덱스·비티·헤르메스·백그라운드 스크립트로 맡기고 요약·판정만 받는다.",
    "- 정본: docs/오케스트레이터_일하는_방식.md. 위임 관문 훅이 위임 없는 100회/15만 자 구간마다 확인을 보낸다(기본 warn).",
    "- 소넷 서브에이전트는 예외 관문(무상 2회 실패·100줄 이내 복잡 코드)만. 클로드 API는 래퍼 레이어로(정본 '여섯째 갈래').",
]


def print_orch():
    print()
    print(chr(10).join(ORCH_LINES))


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


def open_orders():
    """클라우드 관제탑이 올린 로컬 지시서(tasks/todo/*.md)를 보인다. 끝난 지시서는 tasks/done/으로 옮긴다(git mv)."""
    root = Path(__file__).resolve().parents[2]
    files = sorted(f for f in (root / 'tasks' / 'todo').glob('*.md') if f.name.lower() != 'readme.md')
    print(f'\n===== 열린 지시서 {len(files)}개 (tasks/todo, 클라우드가 올림: 끝나면 tasks/done으로 git mv) =====')
    for f in files:
        first = f.read_text(encoding='utf-8').splitlines()[:1]
        print(f"- {f.name}: {first[0].lstrip('# ') if first else ''}")


def cloud_main(who):
    """클라우드 세션용(운영 DB·C:/work 경로가 없을 때): 저장소 안 파일만으로 인수인계 원문과 업무대장 진행 건을 보인다.
    정본은 docs/진행상황.md(핏은 shorts-lab KPI_과제.md라 add_repo 뒤 직접), 업무대장은 docs/<이름>_업무대장.md."""
    sys.stdout.reconfigure(encoding='utf-8')
    root = Path(__file__).resolve().parents[2]
    prog = (root / 'docs' / '진행상황.md').read_text(encoding='utf-8')
    m = re.search(r'^## \[' + re.escape(who) + r'\].*?(?=^---\s*$|^## \[)', prog, re.S | re.M)
    print(f'===== {who} 최신 인수인계(원문, 클라우드 모드: 저장소 docs/진행상황.md) =====')
    print(m.group(0).rstrip() if m else '(진행상황.md에 해당 블록 없음)')
    ledger = root / 'docs' / f'{who}_업무대장.md'
    print(f'\n===== {who} 업무대장 제목 줄(진행·확인필요·사장님 상태만) =====')
    if ledger.exists():
        for l in ledger.read_text(encoding='utf-8').splitlines():
            if l.startswith('#') and re.search(r'진행|확인필요|사장님', l):
                print('-', l[:140])
    open_orders()
    print_orch()
    print('\n(운영 DB·감시 상태판은 로컬 전용이라 생략. 기억 스냅샷: 비공개 저장소 simplifier-cxo-db reports/tam_memory/MEMORY.md)')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    who = sys.argv[1] if len(sys.argv) > 1 else '탐'
    if opsdb is None or not STATUS.exists() or '--cloud' in sys.argv:
        return cloud_main(who)
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
    if who == '탐':  # 사장님이 지시한 목표 장부(.claude/hooks/drive-gate.py가 같은 파일을 봄): 묻지 말고 다음 단계를 실행한다
        try:
            import json
            gs = [g for g in json.load(open(r'C:\work\_ops\tam_drive.json', encoding='utf-8')).get('goals', []) if g.get('active')]
            print('\n===== 사장님 지시 목표(활성, 이미 승인됨: 시작 여부를 묻지 말고 다음 단계를 실행) =====')
            for g in gs:
                print(f"- {g['id']} {g['title']} ({g.get('since', '')})\n    다음: {g.get('next', '')[:230]}\n    완료 기준: {g.get('done_when', '')}")
        except Exception:
            print('\n(목표 장부 C:/work/_ops/tam_drive.json 을 못 읽음)')
    open_orders()
    print_orch()
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
