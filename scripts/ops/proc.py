# -*- coding: utf-8 -*-
"""공정 단계 카드: 에이전트가 자기 공정을 DB에서 쉽게 쓰고·읽고·고치고, 작업을 단계별로 진행하며 빠진 단계를 확인한다
(G5, 2026-10-05 탐. 사장님: "토큰 부담 없이 사장이 얘기한 것과 본인이 정리한 것을 입출력이 빠른 표에 쉽게 쓰고 읽고 수정해서 공정을 체계적으로 관리하고,
프로세스 단위로 진행하면서 누락·환각·망각을 최소화"). 기술 구현은 탐 책임, 에이전트는 아래 명령만 쓰면 된다.

저장: 운영 DB tasks 표. section='step'(단계 카드, 에이전트가 직접 씀) · section='run'(작업 1건의 단계별 체크리스트) · section='process'(옛 문서에서 시간당 복사한 읽기 전용 절).
step·run 행은 시간당 거울 갱신이 지우지 않는다. 추가는 자유, 고치기는 이력을 raw.history에 남김, 삭제 명령은 없다(retire로 숨김).

쓰기·고치기
  proc.py add 핏 "자막 만들기" --do "build_srt.py <편폴더> 10 로 만든다" --boss "자막은 한 번에 10글자 이내(사장님 10/3)" [--tool "build_srt.py"] [--who 핏]
  proc.py amend 핏 3 [--title ..] [--do ..] [--boss ..] [--tool ..] [--who 핏]     (3 = 단계 번호)
  proc.py retire 핏 3 --why "이유"                                                (목록에서 숨김, 이력 보존)
읽기
  proc.py steps 핏                 그 공정의 단계 카드 전체(사장님 말 포함, 짧게)
  proc.py show 자막 [--who 핏]     키워드로 찾기(단계 카드 + 옛 문서 절)
  proc.py list [--who 핏]
작업 1건을 단계별로 진행(누락·망각 방지)
  proc.py run start 핏 "lf05 롱폼 조립" [--who 핏]        체크리스트를 만들고 각 단계의 사장님 말을 함께 보여 줌 → 작업 번호(run id)
  proc.py run done <run id> <단계번호> --evidence "파일·로그 경로" [--who 핏]     증거 없이는 완료 처리 안 됨(환각 방지)
  proc.py run skip <run id> <단계번호> --why "건너뛴 이유"                    (이유 필수, 기록됨)
  proc.py run status <run id>      완료·건너뜀·남은 단계(빠진 것 한눈에)"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

WHO = {'탐', '핏', '마야', '지투', '노트', '비티', '덱스', '타미', '클라우드탐'}
SECRET = re.compile(r'(sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|sb_secret_|sbp_[0-9a-f]{20,}|ghp_|github_pat_|-----BEGIN)', re.I)
COLS = ('owner', 'section', 'no', 'title', 'status', 'source_date', 'next_action', 'evidence', 'result', 'cost', 'decider', 'raw', 'source')


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def clean(*texts):
    for t in texts:
        if t and SECRET.search(t):
            sys.exit('비밀값 모양이 들어 있어 거부했습니다(값은 기록에 쓰지 않습니다)')


def row(**kw):
    r = {c: None for c in COLS}
    r.update(kw)
    return r


def steps_of(proc):
    rs = opsdb.select('tasks', 'id,owner,no,title,next_action,status,raw', where={'section': 'eq.step', 'owner': f'eq.{proc}'}, order='id.asc', limit=500)
    rs = [r for r in rs if r['status'] != '숨김']
    return sorted(rs, key=lambda r: int(r['no']))


def fmt_step(r, brief=False):
    raw = r['raw']
    s = f"[{r['no']}] {r['title']}"
    if r.get('next_action'):
        s += f"\n    할 일: {r['next_action'][:250]}"
    if raw.get('boss'):
        s += f"\n    ★ 사장님: {raw['boss'][:300]}"
    if raw.get('tool') and not brief:
        s += f"\n    도구: {raw['tool']}"
    return s


def cmd_add(a):
    clean(a.title, a.do, a.boss, a.tool)
    if a.who and a.who not in WHO:
        sys.exit(f'who는 {sorted(WHO)} 중 하나')
    cur = steps_of(a.proc)
    allrows = opsdb.select('tasks', 'no', where={'section': 'eq.step', 'owner': f'eq.{a.proc}'}, limit=1000)
    seq = max([int(r['no']) for r in allrows] + [0]) + 1
    opsdb.insert('tasks', [row(owner=a.proc, section='step', no=str(seq), title=a.title[:200], status='사용', next_action=(a.do or '')[:600], source='proc.py',
                              raw={'boss': a.boss or '', 'tool': a.tool or '', 'by': a.who or '', 'at': now(), 'history': []})])
    print(f'단계 추가: [{a.proc} #{seq}] {a.title}  (현재 {len(cur) + 1}단계)')


def get_step(proc, no):
    rs = opsdb.select('tasks', '*', where={'section': 'eq.step', 'owner': f'eq.{proc}', 'no': f'eq.{no}'}, limit=1)
    if not rs:
        sys.exit(f'{proc} 단계 {no}가 없습니다: proc.py steps {proc}')
    return rs[0]


def cmd_amend(a):
    clean(a.title, a.do, a.boss, a.tool)
    r = get_step(a.proc, a.no)
    old = {'title': r['title'], 'do': r['next_action'], 'boss': r['raw'].get('boss'), 'tool': r['raw'].get('tool'), 'at': now(), 'by': a.who or ''}
    raw = dict(r['raw'])
    raw['history'] = (raw.get('history') or [])[-9:] + [old]
    if a.title:
        r['title'] = a.title[:200]
    if a.do is not None:
        r['next_action'] = a.do[:600]
    if a.boss is not None:
        raw['boss'] = a.boss
    if a.tool is not None:
        raw['tool'] = a.tool
    r['raw'] = raw
    opsdb.patch('tasks', {'id': f"eq.{r['id']}"}, {'title': r['title'], 'next_action': r['next_action'], 'raw': raw})
    print(f'고침: [{a.proc} #{a.no}] 이전 내용은 이력에 보존됨(최근 10개)')


def cmd_retire(a):
    r = get_step(a.proc, a.no)
    raw = dict(r['raw'])
    raw['retired'] = {'why': a.why, 'at': now()}
    opsdb.patch('tasks', {'id': f"eq.{r['id']}"}, {'status': '숨김', 'raw': raw})
    print(f'숨김: [{a.proc} #{a.no}] {r["title"]}')


def cmd_steps(a):
    rs = steps_of(a.proc)
    if not rs:
        print(f'"{a.proc}" 단계 카드가 아직 없습니다. 옛 문서 절은 `proc.py show <키워드> --who {a.proc}` 로 찾고, `proc.py add {a.proc} "제목" --do ".." --boss ".."` 로 카드를 만드세요.')
        return
    print(f'== {a.proc} 공정 {len(rs)}단계')
    for r in rs:
        print(fmt_step(r))


def find_legacy(kw, who=None):
    where = {'section': 'eq.process', 'or': f'(title.ilike.*{kw}*,raw->>body.ilike.*{kw}*)'}
    rs = opsdb.select('tasks', 'owner,no,title,source,raw', where=where, limit=40)
    return [r for r in rs if not who or r['owner'].startswith(who)]


def cmd_show(a):
    shown = 0
    cards = opsdb.select('tasks', 'owner,no,title,next_action,status,raw', where={'section': 'eq.step', 'or': f'(title.ilike.*{a.kw}*,next_action.ilike.*{a.kw}*,raw->>boss.ilike.*{a.kw}*)'}, limit=40)
    for r in cards:
        if r['status'] == '숨김' or (a.who and not r['owner'].startswith(a.who)):
            continue
        print(f"== 단계 카드 [{r['owner']}] " + fmt_step(r))
        shown += 1
    legacy = find_legacy(a.kw, a.who)
    for r in legacy[:max(0, 4 - shown)]:
        raw = r['raw']
        print(f"\n== 옛 문서 [{r['owner']}#{r['no']}] {r['title'][:70]} ({r['source']}, {raw.get('bytes', 0)}B)")
        for b in raw.get('boss_lines', [])[:6]:
            print('  ★ ' + b)
        lines = [l for l in raw.get('body', '').split('\n') if a.kw in l][:5] or raw.get('body', '').split('\n')[:5]
        print('  ' + '\n  '.join(l[:220] for l in lines))
    if not shown and not legacy:
        print(f'"{a.kw}"가 든 단계가 없습니다. proc.py list 로 목록을 보세요.')


def cmd_list(a):
    rs = opsdb.select('tasks', 'owner,section,no,title,status,raw', where={'section': 'in.(step,process)'}, order='owner.asc,id.asc', limit=800)
    for r in rs:
        if (a.who and not r['owner'].startswith(a.who)) or r['status'] == '숨김':
            continue
        tag = '카드' if r['section'] == 'step' else '옛문서'
        print(f"[{r['owner']}#{r['no']}·{tag}] {r['title'][:60]}")


def cmd_run(a):
    if a.sub == 'start':
        rs = steps_of(a.proc)
        if not rs:
            sys.exit(f'{a.proc} 단계 카드가 없습니다: proc.py add {a.proc} ... 로 먼저 만드세요')
        runs = opsdb.select('tasks', 'no', where={'section': 'eq.run'}, limit=5000)
        rid = max([int(r['no'].split('-')[0]) for r in runs if r['no'] and r['no'].split('-')[0].isdigit()] + [0]) + 1
        opsdb.insert('tasks', [row(owner=a.proc, section='run', no=f'{rid}-{r["no"]}', title=r['title'], status='대기', next_action=r['next_action'],
                                  source='proc.py', raw={'run': rid, 'name': a.name, 'step': int(r['no']), 'boss': r['raw'].get('boss', ''), 'by': a.who or '', 'at': now()})
                                  for r in rs])
        print(f'작업 시작: run {rid} "{a.name}" ({a.proc} {len(rs)}단계). 완료 처리: proc.py run done {rid} <단계번호> --evidence "경로"\n')
        for r in rs:
            print(fmt_step(r, brief=True))
        return
    rid = str(a.rid)
    rows = opsdb.select('tasks', '*', where={'section': 'eq.run', 'no': f'like.{rid}-*'}, order='id.asc', limit=500)
    if not rows:
        sys.exit(f'run {rid}를 찾지 못했습니다')
    rows = sorted(rows, key=lambda r: r['raw']['step'])
    if a.sub == 'status':
        n = rows[0]['raw'].get('name')
        done = [r for r in rows if r['status'] == '완료']
        skip = [r for r in rows if r['status'] == '건너뜀']
        todo = [r for r in rows if r['status'] == '대기']
        print(f'run {rid} "{n}" ({rows[0]["owner"]}): 완료 {len(done)} / 건너뜀 {len(skip)} / 남음 {len(todo)} (전체 {len(rows)})')
        for r in rows:
            mark = {'완료': 'OK', '건너뜀': '건너뜀', '대기': '남음'}[r['status']]
            extra = f"  증거: {r['evidence']}" if r['status'] == '완료' else (f"  이유: {r['result']}" if r['status'] == '건너뜀' else '')
            print(f"  [{mark}] {r['raw']['step']}. {r['title'][:50]}{extra}")
        return
    r = next((x for x in rows if x['raw']['step'] == a.step), None)
    if not r:
        sys.exit(f'단계 {a.step}가 이 작업에 없습니다')
    if a.sub == 'done':
        clean(a.evidence)
        if not a.evidence or len(a.evidence.strip()) < 3:
            sys.exit('증거(파일·로그 경로나 확인한 값)가 필요합니다: --evidence "..." (했다는 말만으로는 완료 처리 안 됨)')
        r['status'], r['evidence'] = '완료', a.evidence[:400]
    else:
        clean(a.why)
        if not a.why or len(a.why.strip()) < 3:
            sys.exit('건너뛴 이유가 필요합니다: --why "..."')
        r['status'], r['result'] = '건너뜀', a.why[:400]
    r['raw'] = {**r['raw'], 'closed_at': now(), 'closed_by': a.who or ''}
    opsdb.patch('tasks', {'id': f"eq.{r['id']}"}, {'status': r['status'], 'evidence': r['evidence'], 'result': r['result'], 'raw': r['raw']})
    left = [x for x in rows if x['status'] == '대기' and x['raw']['step'] != a.step]
    print(f"단계 {a.step} {r['status']} 처리. 남은 단계 {len(left)}개" + (": " + ", ".join(f"{x['raw']['step']}.{x['title'][:20]}" for x in left[:6]) if left else " — 모두 끝났습니다"))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add'); p.add_argument('proc'); p.add_argument('title'); p.add_argument('--do'); p.add_argument('--boss'); p.add_argument('--tool'); p.add_argument('--who')
    p = sub.add_parser('amend'); p.add_argument('proc'); p.add_argument('no', type=int); p.add_argument('--title'); p.add_argument('--do'); p.add_argument('--boss'); p.add_argument('--tool'); p.add_argument('--who')
    p = sub.add_parser('retire'); p.add_argument('proc'); p.add_argument('no', type=int); p.add_argument('--why', required=True)
    p = sub.add_parser('steps'); p.add_argument('proc')
    p = sub.add_parser('show'); p.add_argument('kw'); p.add_argument('--who')
    p = sub.add_parser('list'); p.add_argument('--who')
    p = sub.add_parser('run'); rs = p.add_subparsers(dest='sub', required=True)
    q = rs.add_parser('start'); q.add_argument('proc'); q.add_argument('name'); q.add_argument('--who')
    q = rs.add_parser('done'); q.add_argument('rid'); q.add_argument('step', type=int); q.add_argument('--evidence'); q.add_argument('--who')
    q = rs.add_parser('skip'); q.add_argument('rid'); q.add_argument('step', type=int); q.add_argument('--why'); q.add_argument('--who')
    q = rs.add_parser('status'); q.add_argument('rid')
    a = ap.parse_args()
    {'add': cmd_add, 'amend': cmd_amend, 'retire': cmd_retire, 'steps': cmd_steps, 'show': cmd_show, 'list': cmd_list, 'run': cmd_run}[a.cmd](a)


if __name__ == '__main__':
    main()
