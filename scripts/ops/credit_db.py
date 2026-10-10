# -*- coding: utf-8 -*-
"""크레딧 대장 DB 도구(2026-10-11, 사장님 지시: 오픈라우터·GCP 등 유·무료 모든 잔액, 무료 크레딧을 대장에 기록해 관리).
표 정의: tools/db/credit_schema.sql(운영 상태 DB simplifier-ops-data, 실행은 별도 승인). 접속은 opsdb.py(키 값은 이 코드에 없고 출력하지 않는다).
DB가 정본이다. 문서(docs/대장_체계.md)는 이 도구 사용법만 가리킨다. 비밀값(키·결제번호)은 어떤 칸에도 넣지 않는다(참조 이름만).

읽기
  credit_db.py status                        계정별 종류·상태·잔액·만료까지 일수·낡음 표시 한 장
  credit_db.py expiring                      30일 안 만료·잔액 부족·확인이 72시간 넘게 낡은 것만
  credit_db.py howto <slug>                  잔액 확인 방법·명령·계정 이메일·워크스페이스 여부·관련 대장·공정
  credit_db.py events <slug>                 최근 사건(충전·차감·리셋·만료·조정·확인)
쓰기(값 길이 제한, 비밀값 모양 거부)
  credit_db.py add-event <slug> --kind 차감 --amount -3 --balance-after 97 --who 탐 --note "..." --evidence "..."
                                             사건을 넣으면서 계정의 balance·balance_at 도 balance_after 로 같이 갱신
  credit_db.py set-balance <slug> <값> --note "..."   잔액 확인 기록(계정 갱신 + '확인' 사건)
  credit_db.py set-status <slug> <정상|주의|소진|만료|미확인> --note "..."
  credit_db.py seed <폴더>                   seed_accounts.json, seed_events.json 을 upsert(있는 파일만, 계정 먼저)"""
import argparse
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

STATUSES = ('정상', '주의', '소진', '만료', '미확인')
KINDS = ('유료선불', '무료크레딧', '무료티어', '구독', '한도형', '플랫폼')
CURRENCIES = ('KRW', 'USD', 'calls', 'credits', 'minutes')
EVENT_KINDS = ('충전', '차감', '리셋', '만료', '조정', '확인')
NO_TABLE = '표 미생성: credit_schema.sql 실행 필요'
STALE_HOURS = 72

ACCOUNT_COLS = ('slug', 'name', 'kind', 'provider', 'owner', 'account_email', 'workspace', 'currency', 'balance', 'balance_at', 'expires_at',
                'refill_rule', 'how_to_check', 'check_command', 'resource_id', 'billing_ref', 'alert_threshold', 'status', 'note', 'evidence')
EVENT_COLS = ('account_slug', 'at', 'kind', 'amount', 'balance_after', 'who', 'note', 'evidence')

# 비밀값 모양(키 접두어). 걸리면 쓰기를 거부한다.
SECRET = re.compile(
    r'(sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|sb_secret_|sb_publishable_|sbp_[0-9a-f]{20,}|ghp_|gho_|github_pat_|xox[abp]-|AKIA[0-9A-Z]{12,}'
    r'|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|-----BEGIN|Bearer\s+[A-Za-z0-9._-]{20,}|[?&](api_?key|key|token|secret|access_token)=)', re.I)
MAXLEN = {'slug': 60, 'account_slug': 60, 'name': 100, 'default': 1500}


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
    """숫자를 읽기 좋게(정수면 소수점 없이)."""
    if v is None:
        return '-'
    f = float(v)
    return str(int(f)) if f == int(f) else f'{f:g}'


def money(r):
    if r.get('balance') is None:
        return '잔액 미확인'
    return f"{num(r['balance'])} {r.get('currency') or ''}".strip()


def expiry_label(r):
    d = r.get('days_to_expiry')
    if d is None:
        return '만료 없음'
    d = int(d)
    return f'만료 {d}일 남음' if d >= 0 else f'만료 {-d}일 지남'


def stale_label(r):
    age = r.get('balance_age_hours')
    if r.get('balance_at') is None or age is None:
        return '확인 기록 없음'
    age = float(age)
    return f'낡음 {num(age)}시간' if age > STALE_HOURS else f'확인 {num(age)}시간 전'


def flags(r):
    return ' <잔액 부족>' if r.get('low') else ''


# ---------- 읽기 명령 ----------
def cmd_status(a):
    rows = sel('v_credit_status', order='slug.asc')
    if not rows:
        print('(등록된 계정 없음. seed 로 넣으세요)')
        return
    print(f'크레딧 대장 현황 {len(rows)}개 계정')
    w1 = max(wid(r['slug']) for r in rows)
    w2 = max(wid(r['name']) for r in rows)
    for r in rows:
        print(f"{pad(r['slug'], w1)}  {pad(r['name'], w2)}  {r.get('kind') or '-'}  [{r['status']}]  {money(r)}  {expiry_label(r)}  {stale_label(r)}{flags(r)}")
    cnt = {}
    for r in rows:
        cnt[r['status']] = cnt.get(r['status'], 0) + 1
    print('합계: ' + ', '.join(f'{k} {v}' for k, v in cnt.items()))


def cmd_expiring(a):
    rows = sel('v_credit_expiring', order='days_to_expiry.asc.nullslast')
    if not rows:
        print('곧 만료·부족·낡은 계정 없음')
        return
    print(f'주의가 필요한 계정 {len(rows)}개')
    for r in rows:
        print(f"{r['slug']}  {r['name']}  [{r['status']}]  {money(r)}  {expiry_label(r)}  {stale_label(r)}  사유: {r.get('reasons') or ''}")


def cmd_howto(a):
    rows = sel('credit_accounts', where={'slug': f'eq.{a.slug}'})
    if not rows:
        die(f'계정 없음: {a.slug} (status 로 목록 확인)')
    m = rows[0]
    print(f"{m['name']} ({m['slug']})  종류: {m.get('kind') or '-'}  상태: {m['status']}")
    print(f"잔액: {money(m)} (확인 {short_time(m.get('balance_at'))}), 만료일: {m.get('expires_at') or '없음'}, 알림 기준: {num(m.get('alert_threshold'))}")
    print(f"잔액 확인 방법: {m.get('how_to_check') or '-'}")
    print(f"확인 명령: {m.get('check_command') or '-'}")
    print(f"충전·리셋 규칙: {m.get('refill_rule') or '-'}")
    print(f"계정 이메일: {m.get('account_email') or '-'}  워크스페이스: {'예' if m.get('workspace') else '아니오'}  소유: {m.get('owner') or '-'}")
    print(f"관련 대장·공정: 자원 {m.get('resource_id') or '-'}, 청구 참조 {m.get('billing_ref') or '-'}")
    if m.get('note'):
        print(f"메모: {m['note']}")


def cmd_events(a):
    rows = sel('credit_events', 'id,at,kind,amount,balance_after,who,note', where={'account_slug': f'eq.{a.slug}'}, order='at.desc', limit=a.limit)
    if not rows:
        print(f'사건 없음: {a.slug}')
        return
    print(f'{a.slug} 최근 사건 {len(rows)}건')
    for e in rows:
        amt = f" {num(e['amount'])}" if e.get('amount') is not None else ''
        bal = f" -> 잔액 {num(e['balance_after'])}" if e.get('balance_after') is not None else ''
        who = f" ({e['who']})" if e.get('who') else ''
        note = f" {e['note']}" if e.get('note') else ''
        print(f"{short_time(e['at'])} [{e['kind']}]{amt}{bal}{who}{note}")


# ---------- 쓰기 명령 ----------
def need_account(slug):
    gate('slug', slug)
    if not sel('credit_accounts', 'slug', where={'slug': f'eq.{slug}'}):
        die(f'계정 없음: {slug} (status 로 목록 확인)')


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def cmd_add_event(a):
    if a.kind not in EVENT_KINDS:
        die(f'--kind 는 {EVENT_KINDS} 중 하나')
    row = gate_row({'account_slug': a.slug, 'kind': a.kind, 'who': a.who, 'note': a.note, 'evidence': a.evidence})
    row['at'] = now_iso()
    if a.amount is not None:
        row['amount'] = a.amount
    if a.balance_after is not None:
        row['balance_after'] = a.balance_after
    row = {k: v for k, v in row.items() if v is not None}
    need_account(a.slug)
    call(opsdb.upsert, 'credit_events', [row], 'account_slug,at,kind')
    if a.balance_after is not None:  # 사건과 계정 잔액이 어긋나지 않게 같이 갱신
        call(opsdb.patch, 'credit_accounts', {'slug': f'eq.{a.slug}'}, {'balance': a.balance_after, 'balance_at': row['at'], 'updated_at': row['at']})
        print(f'사건 기록: {a.slug} [{a.kind}] 잔액 {num(a.balance_after)} 로 갱신')
    else:
        print(f'사건 기록: {a.slug} [{a.kind}] (잔액은 그대로)')


def cmd_set_balance(a):
    vals = gate_row({'note': a.note})
    at = now_iso()
    need_account(a.slug)
    patch = {'balance': a.value, 'balance_at': at, 'updated_at': at}
    ev = {'account_slug': a.slug, 'at': at, 'kind': '확인', 'balance_after': a.value}
    if vals.get('note') is not None:
        patch['note'] = vals['note']
        ev['note'] = vals['note']
    call(opsdb.patch, 'credit_accounts', {'slug': f'eq.{a.slug}'}, patch)
    call(opsdb.upsert, 'credit_events', [ev], 'account_slug,at,kind')
    print(f'잔액 확인 기록: {a.slug} = {num(a.value)}' + (f' ({a.note})' if a.note else ''))


def cmd_set_status(a):
    if a.status not in STATUSES:
        die(f'상태는 {STATUSES} 중 하나')
    vals = gate_row({'status': a.status, 'note': a.note})
    vals['updated_at'] = now_iso()
    need_account(a.slug)
    call(opsdb.patch, 'credit_accounts', {'slug': f'eq.{a.slug}'}, {k: v for k, v in vals.items() if v is not None})
    print(f'상태 변경: {a.slug} -> {a.status}' + (f' ({a.note})' if a.note else ''))


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
    f = folder / 'seed_accounts.json'
    if f.exists():
        accs = pick(load_json(f), ACCOUNT_COLS, 'accounts')
        for i, m in enumerate(accs):
            if not m.get('slug') or not m.get('name'):
                die(f'accounts {i + 1}번째: slug·name 필수')
            if m.get('status') and m['status'] not in STATUSES:
                die(f'accounts {i + 1}번째: status 는 {STATUSES} 중 하나')
            if m.get('kind') and m['kind'] not in KINDS:
                die(f'accounts {i + 1}번째: kind 는 {KINDS} 중 하나')
            if m.get('currency') and m['currency'] not in CURRENCIES:
                die(f'accounts {i + 1}번째: currency 는 {CURRENCIES} 중 하나')
        now = now_iso()
        for m in accs:
            m['updated_at'] = now
        call(opsdb.upsert, 'credit_accounts', accs, 'slug')
        done.append(f'계정 {len(accs)}')
    f = folder / 'seed_events.json'
    if f.exists():
        evs = pick(load_json(f), EVENT_COLS, 'events')
        for i, e in enumerate(evs):
            if not e.get('account_slug') or e.get('kind') not in EVENT_KINDS or not e.get('at'):
                die(f'events {i + 1}번째: account_slug·at·kind(충전/차감/리셋/만료/조정/확인) 필수')
        call(opsdb.upsert, 'credit_events', evs, 'account_slug,at,kind')
        done.append(f'사건 {len(evs)}')
    print('시드 반영: ' + ', '.join(done) if done else f'시드 파일 없음({folder})')


def build_parser():
    ap = argparse.ArgumentParser(description='크레딧 대장 DB 조회·기록', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    sub.add_parser('expiring')
    p = sub.add_parser('howto'); p.add_argument('slug')
    p = sub.add_parser('events'); p.add_argument('slug'); p.add_argument('--limit', type=int, default=20)
    p = sub.add_parser('add-event'); p.add_argument('slug')
    p.add_argument('--kind', required=True)
    for k in ('who', 'note', 'evidence'):
        p.add_argument('--' + k)
    p.add_argument('--amount', type=float)
    p.add_argument('--balance-after', dest='balance_after', type=float)
    p = sub.add_parser('set-balance'); p.add_argument('slug'); p.add_argument('value', type=float); p.add_argument('--note')
    p = sub.add_parser('set-status'); p.add_argument('slug'); p.add_argument('status'); p.add_argument('--note')
    p = sub.add_parser('seed'); p.add_argument('folder')
    return ap


CMDS = {'status': cmd_status, 'expiring': cmd_expiring, 'howto': cmd_howto, 'events': cmd_events, 'add-event': cmd_add_event,
        'set-balance': cmd_set_balance, 'set-status': cmd_set_status, 'seed': cmd_seed}


def main(argv):
    a = build_parser().parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    CMDS[a.cmd](a)


if __name__ == '__main__':
    main(sys.argv[1:])
