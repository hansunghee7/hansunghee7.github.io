# -*- coding: utf-8 -*-
"""데이터 수집 파이프 대장 DB 도구(2026-10-11, 사장님 지시: API·스크래핑 등 수집 파이프 대장을 만들고, 이 대장의 프로세스로 각 데이터수집 대장이 관리되게 구조화).
표 정의: tools/db/pipeline_schema.sql(운영 상태 DB simplifier-ops-data, 실행은 별도 승인). 접속은 opsdb.py(키 값은 이 코드에 없고 출력하지 않는다).
구조: 데이터 대장(pipeline_ledgers) 1 : N 수집 파이프(data_pipelines) 1 : N 실행 기록(pipeline_runs). DB가 정본이고 문서(docs/대장_체계.md)는 사용법만 가리킨다.
인증은 auth_ref 에 참조 이름만 쓴다(키 값은 어떤 칸에도 넣지 않는다).

읽기
  pipeline_db.py status                      대장별로 묶은 파이프라인 한 장(stale·막힘 표시)
  pipeline_db.py stale                       신선도 기준을 넘긴 것만
  pipeline_db.py howto <slug>                수동 실행 방법, 막혔을 때 보는 곳, 한계, 약관 위험, 감시 id
  pipeline_db.py ledgers                     대장별 건강(파이프라인 수, stale 수, 막힘 수)
쓰기(값 길이 제한, 비밀값 모양 거부)
  pipeline_db.py add-run <slug> --ok yes --rows 120 --note "..."   실행 기록 + last_checked, 성공이면 last_success 갱신
  pipeline_db.py set-status <slug> <작동|부분|막힘|계획|폐기> --note "..."
  pipeline_db.py register <slug> --name .. --kind API --source .. --owner .. --schedule .. --engine .. --destination .. --watch-job .. --ledger ..
  pipeline_db.py seed <폴더>                 seed_ledgers.json 먼저, seed_pipelines.json 나중에 upsert(non_pipeline_jobs 필드는 건너뜀)"""
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
KINDS = ('API', '스크래핑', '파일', '구독', '웹훅', '이메일')
NO_TABLE = '표 미생성: pipeline_schema.sql 실행 필요'
SKIP_FIELD = 'non_pipeline_jobs'

LEDGER_COLS = ('slug', 'name', 'table_name', 'owner', 'update_process', 'freshness_hours', 'status', 'status_note')
PIPELINE_COLS = ('slug', 'name', 'kind', 'source', 'owner', 'schedule', 'engine', 'destination', 'auth_ref', 'freshness_hours', 'status', 'status_note',
                 'watch_job_id', 'ledger_slug', 'process_ref', 'how_to', 'limits', 'tos_risk', 'evidence', 'last_success', 'last_checked')

# 비밀값 모양(키 접두어). 걸리면 쓰기를 거부한다.
SECRET = re.compile(
    r'(sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|sb_secret_|sb_publishable_|sbp_[0-9a-f]{20,}|ghp_|gho_|github_pat_|xox[abp]-|AKIA[0-9A-Z]{12,}'
    r'|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|-----BEGIN|Bearer\s+[A-Za-z0-9._-]{20,}|[?&](api_?key|key|token|secret|access_token)=)', re.I)
MAXLEN = {'slug': 60, 'ledger_slug': 60, 'pipeline_slug': 60, 'name': 100, 'source': 500, 'default': 1500}


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


def num(v):
    if v is None:
        return '-'
    f = float(v)
    return str(int(f)) if f == int(f) else f'{f:g}'


def success_label(p):
    if p.get('last_success') is None:
        return '성공 기록 없음'
    h = p.get('hours_since_success')
    return f"마지막 성공 {short_time(p['last_success'])} ({num(h)}시간 전)" if h is not None else f"마지막 성공 {short_time(p['last_success'])}"


def mark(p):
    out = []
    if p.get('stale'):
        out.append('stale')
    if p.get('status') == '막힘':
        out.append('막힘')
    return ' <' + ', '.join(out) + '>' if out else ''


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------- 읽기 명령 ----------
def cmd_status(a):
    rows = sel('v_pipeline_status', order='ledger_slug.asc.nullsfirst,slug.asc')
    if not rows:
        print('(등록된 파이프라인 없음. seed 또는 register 로 넣으세요)')
        return
    ledgers = {l['slug']: l for l in sel('v_ledger_health')}
    groups = {}
    for r in rows:
        groups.setdefault(r.get('ledger_slug') or '', []).append(r)
    print(f'데이터 수집 파이프 현황 {len(rows)}개 파이프라인, 대장 {len([g for g in groups if g])}곳')
    for key, items in groups.items():
        if key:
            l = ledgers.get(key, {})
            print(f"\n[대장] {l.get('name') or key} ({key})  [{l.get('status', '?')}]")
        else:
            print('\n[대장 미지정]')
        w1 = max(wid(p['slug']) for p in items)
        w2 = max(wid(p['name']) for p in items)
        for p in items:
            print(f"  {pad(p['slug'], w1)}  {pad(p['name'], w2)}  {p.get('kind') or '-'}  [{p['status']}]  {success_label(p)}{mark(p)}")
    cnt = {}
    for r in rows:
        cnt[r['status']] = cnt.get(r['status'], 0) + 1
    stale = sum(1 for r in rows if r.get('stale'))
    print('\n합계: ' + ', '.join(f'{k} {v}' for k, v in cnt.items()) + f', stale {stale}')


def cmd_stale(a):
    rows = [r for r in sel('v_pipeline_status', order='slug.asc') if r.get('stale')]
    if not rows:
        print('신선도 기준을 넘긴 파이프라인 없음')
        return
    print(f'신선도 기준을 넘긴 파이프라인 {len(rows)}개')
    for r in rows:
        print(f"{r['slug']}  {r['name']}  [{r['status']}]  기준 {num(r.get('freshness_hours'))}시간  {success_label(r)}  대장 {r.get('ledger_slug') or '-'}  감시 {r.get('watch_job_id') or '-'}")


def cmd_howto(a):
    rows = sel('data_pipelines', where={'slug': f'eq.{a.slug}'})
    if not rows:
        die(f'파이프라인 없음: {a.slug} (status 로 목록 확인)')
    p = rows[0]
    print(f"{p['name']} ({p['slug']})  종류: {p.get('kind') or '-'}  상태: {p['status']}" + (f" ({p['status_note']})" if p.get('status_note') else ''))
    print(f"수집원: {p.get('source') or '-'}  엔진: {p.get('engine') or '-'}  일정: {p.get('schedule') or '-'}")
    print(f"저장 위치: {p.get('destination') or '-'}  대장: {p.get('ledger_slug') or '-'}  인증 참조: {p.get('auth_ref') or '-'}")
    print(f"수동 실행 방법: {p.get('how_to') or '-'}")
    print(f"막혔을 때 보는 곳: 감시 id {p.get('watch_job_id') or '-'}, 공정 {p.get('process_ref') or '-'}, 근거 {p.get('evidence') or '-'}")
    print(f"한계: {p.get('limits') or '-'}")
    print(f"약관 위험: {p.get('tos_risk') or '-'}")
    print(f"마지막 성공: {short_time(p.get('last_success'))}  마지막 점검: {short_time(p.get('last_checked'))}")


def cmd_ledgers(a):
    rows = sel('v_ledger_health', order='slug.asc')
    if not rows:
        print('(등록된 대장 없음. seed 로 넣으세요)')
        return
    print(f'데이터 대장 {len(rows)}곳')
    w1 = max(wid(r['slug']) for r in rows)
    w2 = max(wid(r['name']) for r in rows)
    for r in rows:
        print(f"{pad(r['slug'], w1)}  {pad(r['name'], w2)}  [{r['status']}]  파이프라인 {r.get('pipelines') or 0}개  stale {r.get('stale_count') or 0}  막힘 {r.get('blocked_count') or 0}")


# ---------- 쓰기 명령 ----------
def parse_bool(s):
    v = str(s).strip().lower()
    if v in ('yes', 'y', 'true', '1', '성공', 'ok'):
        return True
    if v in ('no', 'n', 'false', '0', '실패'):
        return False
    die(f'--ok 는 yes/no 중 하나: {s}')


def need_pipeline(slug):
    gate('slug', slug)
    if not sel('data_pipelines', 'slug', where={'slug': f'eq.{slug}'}):
        die(f'파이프라인 없음: {slug} (status 로 목록 확인)')


def parse_at(s):
    """--at ISO 시각 -> UTC ISO 문자열. 형식이 틀리거나 미래면 거부(시간대 없으면 로컬 시각으로 본다)."""
    try:
        t = datetime.datetime.fromisoformat(str(s).strip())
    except ValueError:
        die(f'--at 형식 오류(ISO 8601 필요): {s}')
    t = t.astimezone() if t.tzinfo is None else t
    t = t.astimezone(datetime.timezone.utc)
    if t > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=1):
        die(f'--at 미래 시각 거부: {s}')
    return t.isoformat()


def cmd_add_run(a):
    ok = parse_bool(a.ok)
    at = parse_at(a.at) if getattr(a, 'at', None) else None
    row = gate_row({'pipeline_slug': a.slug, 'note': a.note, 'evidence': a.evidence})
    row['ok'] = ok
    if a.rows is not None:
        row['rows_in'] = a.rows
    row['ran_at'] = at or now_iso()
    row = {k: v for k, v in row.items() if v is not None}
    need_pipeline(a.slug)
    _, body, _h = call(opsdb._call, 'POST', '/pipeline_runs', [row], 'return=representation')
    rid = body[0]['id'] if body else '?'
    upd = {'last_checked': row['ran_at'], 'updated_at': row['ran_at']}
    if ok:
        upd['last_success'] = row['ran_at']
    call(opsdb.patch, 'data_pipelines', {'slug': f'eq.{a.slug}'}, upd)
    print(f"실행 기록 추가: run_id={rid} ({a.slug}) {'성공, last_success 갱신' if ok else '실패, last_success 그대로'}")


def cmd_set_status(a):
    if a.status not in STATUSES:
        die(f'상태는 {STATUSES} 중 하나')
    vals = gate_row({'status': a.status, 'status_note': a.note})
    vals['updated_at'] = now_iso()
    need_pipeline(a.slug)
    call(opsdb.patch, 'data_pipelines', {'slug': f'eq.{a.slug}'}, {k: v for k, v in vals.items() if v is not None})
    print(f'상태 변경: {a.slug} -> {a.status}' + (f' ({a.note})' if a.note else ''))


def cmd_register(a):
    if a.kind and a.kind not in KINDS:
        die(f'--kind 는 {KINDS} 중 하나')
    row = gate_row({'slug': a.slug, 'name': a.name, 'kind': a.kind, 'source': a.source, 'owner': a.owner, 'schedule': a.schedule, 'engine': a.engine,
                    'destination': a.destination, 'watch_job_id': a.watch_job, 'ledger_slug': a.ledger})
    row['status'] = '계획'
    row['updated_at'] = now_iso()
    row = {k: v for k, v in row.items() if v is not None}
    if sel('data_pipelines', 'slug', where={'slug': f'eq.{a.slug}'}):
        die(f'이미 있는 파이프라인: {a.slug} (고치려면 set-status 또는 seed)')
    if a.ledger and not sel('pipeline_ledgers', 'slug', where={'slug': f'eq.{a.ledger}'}):
        die(f'데이터 대장 없음: {a.ledger} (ledgers 로 목록 확인)')
    call(opsdb.upsert, 'data_pipelines', [row], 'slug')
    print(f'등록: {a.slug} [계획]')
    print('다음 절차: 감시 대장(scripts/ops/jobs.toml) 등록 -> 지금 1회 실행하고 add-run 으로 증거 -> 첫 자동 실행 확인 -> set-status 작동으로 갱신 (docs/대장_체계.md)')


def load_json(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        die(f'{path.name} 을 읽지 못했습니다: {e}')
    if not isinstance(data, list):
        die(f'{path.name} 은 JSON 목록이어야 합니다')
    return data


def pick(rows, cols, label, skip=None):
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            die(f'{label} {i + 1}번째 항목이 객체가 아닙니다')
        if skip:
            r = {k: v for k, v in r.items() if k != skip}
            if not r:  # non_pipeline_jobs 만 담은 메모용 객체
                continue
        unknown = set(r) - set(cols)
        if unknown:
            die(f'{label} {i + 1}번째 항목에 알 수 없는 열: {sorted(unknown)}')
        out.append(gate_row({k: r[k] for k in cols if k in r}))
    return out


def cmd_seed(a):
    folder = Path(a.folder)
    done = []
    f = folder / 'seed_ledgers.json'
    if f.exists():  # 대장을 먼저 넣어야 파이프라인의 ledger_slug 외래키가 맞는다
        leds = pick(load_json(f), LEDGER_COLS, 'ledgers')
        for i, l in enumerate(leds):
            if not l.get('slug') or not l.get('name') or l.get('status') not in STATUSES:
                die(f'ledgers {i + 1}번째: slug·name·status(작동/부분/막힘/계획/폐기) 필수')
        now = now_iso()
        for l in leds:
            l['updated_at'] = now
        call(opsdb.upsert, 'pipeline_ledgers', leds, 'slug')
        done.append(f'대장 {len(leds)}')
    f = folder / 'seed_pipelines.json'
    if f.exists():
        pls = pick(load_json(f), PIPELINE_COLS, 'pipelines', skip=SKIP_FIELD)
        for i, p in enumerate(pls):
            if not p.get('slug') or not p.get('name') or p.get('status') not in STATUSES:
                die(f'pipelines {i + 1}번째: slug·name·status(작동/부분/막힘/계획/폐기) 필수')
            if p.get('kind') and p['kind'] not in KINDS:
                die(f'pipelines {i + 1}번째: kind 는 {KINDS} 중 하나')
        now = now_iso()
        for p in pls:
            p['updated_at'] = now
        call(opsdb.upsert, 'data_pipelines', pls, 'slug')
        done.append(f'파이프라인 {len(pls)}')
    print('시드 반영: ' + ', '.join(done) if done else f'시드 파일 없음({folder})')


def build_parser():
    ap = argparse.ArgumentParser(description='데이터 수집 파이프 대장 DB 조회·기록', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    sub.add_parser('stale')
    sub.add_parser('ledgers')
    p = sub.add_parser('howto'); p.add_argument('slug')
    p = sub.add_parser('add-run'); p.add_argument('slug')
    p.add_argument('--ok', required=True)
    p.add_argument('--at', help='실제 실행 시각 ISO 8601(없으면 지금, 미래 거부)')
    p.add_argument('--rows', type=int)
    p.add_argument('--note')
    p.add_argument('--evidence')
    p = sub.add_parser('set-status'); p.add_argument('slug'); p.add_argument('status'); p.add_argument('--note')
    p = sub.add_parser('register'); p.add_argument('slug')
    p.add_argument('--name', required=True)
    for k in ('kind', 'source', 'owner', 'schedule', 'engine', 'destination', 'watch-job', 'ledger'):
        p.add_argument('--' + k)
    p = sub.add_parser('seed'); p.add_argument('folder')
    return ap


CMDS = {'status': cmd_status, 'stale': cmd_stale, 'howto': cmd_howto, 'ledgers': cmd_ledgers, 'add-run': cmd_add_run,
        'set-status': cmd_set_status, 'register': cmd_register, 'seed': cmd_seed}


def main(argv):
    a = build_parser().parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    CMDS[a.cmd](a)


if __name__ == '__main__':
    main(sys.argv[1:])
