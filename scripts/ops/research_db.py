# -*- coding: utf-8 -*-
"""리서치 체계 DB 도구(2026-10-11, 사장님 지시: 제미나이리서치·슈퍼리서치 등을 모듈형 공정표로 DB에 두고 빠르게 상태·적용 방법 확인).
표 정의: tools/db/research_schema.sql(운영 상태 DB simplifier-ops-data, 실행은 별도 승인). 접속은 opsdb.py(키 값은 이 코드에 없고 출력하지 않는다).
DB가 정본이다. 문서(docs/리서치_체계.md)는 이 도구 사용법만 가리킨다.

읽기
  research_db.py status                      모듈별 상태·최근 실행·열린 이슈 한 장
  research_db.py howto <slug>                적용 방법 전체(상태, 실행 명령, 방법, 한계, 공정 카드, 열린 이슈)
  research_db.py tree <slug>                 체계의 구성 모듈을 단계 순서로, 대체 경로·관문까지 들여쓰기
  research_db.py issues [slug] [--all]       열린·관찰 이슈(--all은 해결 포함)
쓰기(값 길이 제한, 비밀값 모양 거부)
  research_db.py add-run <slug> --who 탐 --question "..." --route "..." --ok yes --cost 0 --path <결과 파일>
  research_db.py add-issue <slug> --symptom "..." --cause "..." --fix "..." --status 열림
  research_db.py set-status <slug> <작동|부분|막힘|계획|폐기> --note "..." [--verified]
  research_db.py link-check <run_id> <url> <http> <확인|부분|미확인|불일치> [--note ".."]
  research_db.py seed <폴더>                 seed_modules.json, seed_links.json, seed_issues.json 을 upsert(있는 파일만)"""
import argparse
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

STATUSES = ('작동', '부분', '막힘', '계획', '폐기')
KINDS = ('체계', '모듈', '도구', '규칙', '경로')
ROLES = ('step', 'fallback', 'gate')
ISSUE_STATUSES = ('열림', '해결', '관찰')
VERDICTS = ('확인', '부분', '미확인', '불일치')
NO_TABLE = '표 미생성: research_schema.sql 실행 필요'

MODULE_COLS = ('slug', 'name', 'kind', 'summary', 'owner', 'status', 'status_note', 'engine', 'entry', 'how_to', 'limits',
               'process_ref', 'docs', 'evidence', 'last_verified')
LINK_COLS = ('parent', 'child', 'seq', 'role', 'required', 'note')
ISSUE_COLS = ('slug', 'found_at', 'symptom', 'cause', 'fix', 'status', 'evidence')

# 비밀값 모양(키 접두어). 걸리면 쓰기를 거부한다.
SECRET = re.compile(
    r'(sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|sb_secret_|sb_publishable_|sbp_[0-9a-f]{20,}|ghp_|gho_|github_pat_|xox[abp]-|AKIA[0-9A-Z]{12,}'
    r'|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|-----BEGIN|Bearer\s+[A-Za-z0-9._-]{20,}|[?&](api_?key|key|token|secret|access_token)=)', re.I)
MAXLEN = {'slug': 60, 'name': 100, 'url': 500, 'path': 400, 'default': 1500}


def die(msg):
    raise SystemExit(msg)


def gate(field, value):
    """길이 제한과 비밀값 모양 거부. 통과하면 값을 그대로 돌려준다."""
    if value is None or not isinstance(value, str):
        return value
    lim = MAXLEN.get(field, MAXLEN['default'])
    if len(value) > lim:
        die(f'{field} 값이 너무 깁니다({len(value)}자, 한도 {lim}자). 줄여서 다시 넣으세요.')
    if SECRET.search(value):
        die(f'{field} 값에 비밀값 모양이 있어 거부했습니다(값은 기록에 쓰지 않습니다).')
    return value


def gate_row(row):
    return {k: gate(k, v) for k, v in row.items()}


def _is_no_table(msg):
    return any(s in msg for s in ('PGRST205', 'PGRST200', '42P01', 'does not exist', 'Could not find the table', 'schema cache'))


def call(fn, *a, **kw):
    """opsdb 호출. 표가 없으면 안내 한 줄로 끝낸다."""
    try:
        return fn(*a, **kw)
    except RuntimeError as e:
        if _is_no_table(str(e)):
            die(NO_TABLE)
        die(str(e))


def sel(table, cols='*', where=None, order=None, limit=None):
    return call(opsdb.select, table, cols, where, order, limit) or []


# ---------- 출력 도우미 ----------
def wid(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in str(s))


def pad(s, n):
    s = str(s)
    return s + ' ' * max(0, n - wid(s))


def short_time(t):
    if not t:
        return '-'
    return str(t).replace('T', ' ')[:16]


def run_label(r):
    if not r.get('last_run_at'):
        return '실행 기록 없음'
    ok = r.get('last_run_ok')
    return f"{short_time(r['last_run_at'])} {'성공' if ok else ('실패' if ok is False else '결과미상')}"


# ---------- 읽기 명령 ----------
def cmd_status(a):
    rows = sel('v_research_status', order='slug.asc')
    if not rows:
        print('(등록된 모듈 없음. seed 로 넣으세요)')
        return
    print(f'리서치 체계 현황 {len(rows)}개 모듈')
    w1 = max(wid(r['slug']) for r in rows)
    w2 = max(wid(r['name']) for r in rows)
    for r in rows:
        iss = r.get('open_issues') or 0
        print(f"{pad(r['slug'], w1)}  {pad(r['name'], w2)}  [{r['status']}]  최근 {run_label(r)}  열린 이슈 {iss}건")
    cnt = {}
    for r in rows:
        cnt[r['status']] = cnt.get(r['status'], 0) + 1
    print('합계: ' + ', '.join(f'{k} {v}' for k, v in cnt.items()))


def open_issues(slug):
    rows = sel('research_issues', 'id,found_at,symptom,cause,fix,status', where={'slug': f'eq.{slug}', 'status': 'in.(열림,관찰)'}, order='id.asc')
    return rows


def cmd_howto(a):
    rows = sel('v_research_howto', where={'slug': f'eq.{a.slug}'})
    if not rows:
        die(f'모듈 없음: {a.slug} (status 로 목록 확인)')
    m = rows[0]
    print(f"{m['name']} ({m['slug']})  상태: {m['status']}")
    print(f"실행 명령: {m.get('entry') or '-'}")
    print(f"방법: {m.get('how_to') or '-'}")
    print(f"한계: {m.get('limits') or '-'}")
    print(f"관련 공정 카드: {m.get('process_ref') or '-'}")
    iss = open_issues(a.slug)
    if iss:
        print(f'열린 이슈 {len(iss)}건')
        for i in iss:
            print(f"  #{i['id']} [{i['status']}] {i['symptom']}" + (f" -> {i['fix']}" if i.get('fix') else ''))
    else:
        print('열린 이슈 없음')


def cmd_tree(a):
    mods = {m['slug']: m for m in sel('research_modules', 'slug,name,status,kind')}
    if a.slug not in mods:
        die(f'모듈 없음: {a.slug}')
    links = sel('research_links', '*', order='seq.asc')
    by_parent = {}
    for l in links:
        by_parent.setdefault(l['parent'], []).append(l)
    order = {'step': 0, 'gate': 1, 'fallback': 2}
    for k in by_parent:
        by_parent[k].sort(key=lambda l: (l.get('seq') if l.get('seq') is not None else 999, order.get(l['role'], 9)))
    root = mods[a.slug]
    print(f"{root['name']} ({root['slug']}) [{root['status']}]")
    seen = {a.slug}

    def walk(slug, depth):
        for l in by_parent.get(slug, []):
            c = mods.get(l['child'], {'name': '(미등록)', 'status': '?'})
            tag = {'step': f"{l['seq']}단계" if l.get('seq') is not None else '단계', 'fallback': '대체', 'gate': '관문'}.get(l['role'], l['role'])
            req = '' if l.get('required', True) else ' (선택)'
            note = f" - {l['note']}" if l.get('note') else ''
            loop = ' (순환, 생략)' if l['child'] in seen else ''
            print(f"{'  ' * depth}{tag}: {c['name']} ({l['child']}) [{c['status']}]{req}{note}{loop}")
            if l['child'] not in seen and depth < 6:
                seen.add(l['child'])
                walk(l['child'], depth + 1)
                seen.discard(l['child'])

    if not by_parent.get(a.slug):
        print('  (구성 모듈 없음)')
    walk(a.slug, 1)


def cmd_issues(a):
    where = {}
    if a.slug:
        where['slug'] = f'eq.{a.slug}'
    if not a.all:
        where['status'] = 'in.(열림,관찰)'
    rows = sel('research_issues', 'id,slug,found_at,symptom,cause,fix,status', where=where or None, order='id.asc')
    if not rows:
        print('이슈 없음')
        return
    print(f'이슈 {len(rows)}건')
    for i in rows:
        print(f"#{i['id']} [{i['status']}] {i['slug']} ({i.get('found_at') or '-'}): {i['symptom']}")
        if i.get('cause'):
            print(f"    원인: {i['cause']}")
        if i.get('fix'):
            print(f"    조치: {i['fix']}")


# ---------- 쓰기 명령 ----------
def need_module(slug):
    gate('slug', slug)
    if not sel('research_modules', 'slug', where={'slug': f'eq.{slug}'}):
        die(f'모듈 없음: {slug} (status 로 목록 확인)')


def parse_bool(s):
    v = str(s).strip().lower()
    if v in ('yes', 'y', 'true', '1', '성공', 'ok'):
        return True
    if v in ('no', 'n', 'false', '0', '실패'):
        return False
    die(f'--ok 는 yes/no 중 하나: {s}')


def cmd_add_run(a):
    row = gate_row({'slug': a.slug, 'who': a.who, 'question': a.question, 'route': a.route, 'result_path': a.path, 'notes': a.notes})
    row['ok'] = parse_bool(a.ok) if a.ok is not None else None
    row['cost_krw'] = a.cost
    row = {k: v for k, v in row.items() if v is not None}
    need_module(a.slug)
    _, body, _h = call(opsdb._call, 'POST', '/research_runs', [row], 'return=representation')
    rid = body[0]['id'] if body else '?'
    print(f'실행 기록 추가: run_id={rid} ({a.slug})')


def cmd_add_issue(a):
    if a.status not in ISSUE_STATUSES:
        die(f'--status 는 {ISSUE_STATUSES} 중 하나')
    row = gate_row({'slug': a.slug, 'found_at': a.found_at or datetime.date.today().isoformat(), 'symptom': a.symptom, 'cause': a.cause, 'fix': a.fix,
                    'status': a.status, 'evidence': a.evidence})
    row = {k: v for k, v in row.items() if v is not None}
    need_module(a.slug)
    call(opsdb.upsert, 'research_issues', [row], 'slug,symptom')
    print(f'이슈 기록: {a.slug} [{a.status}] {a.symptom[:60]}')


def cmd_set_status(a):
    if a.status not in STATUSES:
        die(f'상태는 {STATUSES} 중 하나')
    vals = gate_row({'status': a.status, 'status_note': a.note})
    vals['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if a.verified:
        vals['last_verified'] = datetime.date.today().isoformat()
    need_module(a.slug)
    call(opsdb.patch, 'research_modules', {'slug': f'eq.{a.slug}'}, {k: v for k, v in vals.items() if v is not None})
    print(f'상태 변경: {a.slug} -> {a.status}' + (f' ({a.note})' if a.note else ''))


def cmd_link_check(a):
    if a.verdict not in VERDICTS:
        die(f'판정은 {VERDICTS} 중 하나')
    row = gate_row({'url': a.url, 'note': a.note})
    row.update({'run_id': int(a.run_id), 'http': int(a.http), 'verdict': a.verdict})
    row = {k: v for k, v in row.items() if v is not None}
    call(opsdb.insert, 'research_link_checks', [row])
    print(f'링크 점검 기록: run {a.run_id} {a.verdict} (HTTP {a.http})')


def load_json(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        die(f'{path.name} 을 읽지 못했습니다: {e}')
    if not isinstance(data, list):
        die(f'{path.name} 은 JSON 목록이어야 합니다')
    return data


def pick(rows, cols, label):
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            die(f'{label} {i + 1}번째 항목이 객체가 아닙니다')
        unknown = set(r) - set(cols)
        if unknown:
            die(f'{label} {i + 1}번째 항목에 알 수 없는 열: {sorted(unknown)}')
        out.append(gate_row({k: r[k] for k in cols if k in r}))
    return out


def cmd_seed(a):
    folder = Path(a.folder)
    done = []
    f = folder / 'seed_modules.json'
    mods = []
    if f.exists():
        mods = pick(load_json(f), MODULE_COLS, 'modules')
        for i, m in enumerate(mods):
            if not m.get('slug') or not m.get('name') or m.get('status') not in STATUSES:
                die(f'modules {i + 1}번째: slug·name·status(작동/부분/막힘/계획/폐기) 필수')
            if m.get('kind') and m['kind'] not in KINDS:
                die(f"modules {i + 1}번째: kind 는 {KINDS} 중 하나")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for m in mods:
            m['updated_at'] = now
        call(opsdb.upsert, 'research_modules', mods, 'slug')
        done.append(f'모듈 {len(mods)}')
    f = folder / 'seed_links.json'
    if f.exists():
        links = pick(load_json(f), LINK_COLS, 'links')
        for i, l in enumerate(links):
            if not l.get('parent') or not l.get('child') or l.get('role') not in ROLES:
                die(f'links {i + 1}번째: parent·child·role(step/fallback/gate) 필수')
        call(opsdb.upsert, 'research_links', links, 'parent,child,role')
        done.append(f'링크 {len(links)}')
    f = folder / 'seed_issues.json'
    if f.exists():
        iss = pick(load_json(f), ISSUE_COLS, 'issues')
        for i, r in enumerate(iss):
            if not r.get('slug') or not r.get('symptom') or r.get('status') not in ISSUE_STATUSES:
                die(f'issues {i + 1}번째: slug·symptom·status(열림/해결/관찰) 필수')
        call(opsdb.upsert, 'research_issues', iss, 'slug,symptom')
        done.append(f'이슈 {len(iss)}')
    print('시드 반영: ' + ', '.join(done) if done else f'시드 파일 없음({folder})')


def build_parser():
    ap = argparse.ArgumentParser(description='리서치 체계 DB 조회·기록', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    p = sub.add_parser('howto'); p.add_argument('slug')
    p = sub.add_parser('tree'); p.add_argument('slug')
    p = sub.add_parser('issues'); p.add_argument('slug', nargs='?'); p.add_argument('--all', action='store_true')
    p = sub.add_parser('add-run'); p.add_argument('slug')
    for k in ('who', 'question', 'route', 'path', 'ok', 'notes'):
        p.add_argument('--' + k)
    p.add_argument('--cost', type=float)
    p = sub.add_parser('add-issue'); p.add_argument('slug')
    for k in ('symptom', 'cause', 'fix', 'evidence', 'found-at'):
        p.add_argument('--' + k)
    p.add_argument('--status', default='열림')
    p = sub.add_parser('set-status'); p.add_argument('slug'); p.add_argument('status')
    p.add_argument('--note'); p.add_argument('--verified', action='store_true')
    p = sub.add_parser('link-check'); p.add_argument('run_id'); p.add_argument('url'); p.add_argument('http'); p.add_argument('verdict'); p.add_argument('--note')
    p = sub.add_parser('seed'); p.add_argument('folder')
    return ap


CMDS = {'status': cmd_status, 'howto': cmd_howto, 'tree': cmd_tree, 'issues': cmd_issues, 'add-run': cmd_add_run, 'add-issue': cmd_add_issue,
        'set-status': cmd_set_status, 'link-check': cmd_link_check, 'seed': cmd_seed}


def main(argv):
    a = build_parser().parse_args(argv)
    if a.cmd == 'add-issue' and not a.symptom:
        die('--symptom 필수')
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    CMDS[a.cmd](a)


if __name__ == '__main__':
    main(sys.argv[1:])
