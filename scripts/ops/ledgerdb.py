# -*- coding: utf-8 -*-
"""작업기 장부(worker_ledger) 쓰기·읽기 도구 (클라우드 탐 2026-10-08, 요청: 핏). proc.py처럼 명령만 쓰면 된다.
표 정의: tools/db/worker_ledger_schema.sql. 접속은 opsdb.py(키 값은 이 코드에 없고, 카빗 패스 금고가 넣어 준 값을 읽어 쓰기만 한다).
계정 칸에는 이메일이 들어가므로 읽을 때는 기본으로 가려서(앞 2글자만) 보여 주고, --show-account를 줘야 전체가 나온다. 값은 로그·화면에 남기지 않는다.

쓰기(있으면 고치고 없으면 넣는다. 준 칸만 바뀐다)
  ledgerdb.py upsert w01 --account <계정> --port 8101 --credit 1250.5 --read-at 2026-10-08T12:00:00+09:00 --cut 100 --deduct 20 --status 정상 --reason ""
  ledgerdb.py upsert w01 --credit 1100 --read-at now          (잔여만 갱신. now = 지금 시각)
읽기
  ledgerdb.py select                   전체(계정은 가림)
  ledgerdb.py select --worker w01 [--show-account] [--fmt md|csv|json]
  ledgerdb.py select --status 이상     상태가 같은 것만"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

TABLE = 'worker_ledger'
COLS = ('worker_id', 'account', 'port', 'credit_remaining', 'read_at', 'today_cut', 'today_deduct', 'status', 'status_reason', 'updated_at')


def mask(account):
    if not account or '@' not in account:
        return account
    name, _, dom = account.partition('@')
    return name[:2] + '***@' + dom


def build_row(args):
    row = {'worker_id': args.worker_id}
    pairs = {'account': args.account, 'port': args.port, 'credit_remaining': args.credit, 'read_at': args.read_at,
             'today_cut': args.cut, 'today_deduct': args.deduct, 'status': args.status, 'status_reason': args.reason}
    for k, v in pairs.items():
        if v is not None:
            row[k] = v
    if row.get('read_at') == 'now':
        row['read_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    return row


def main(argv):
    p = argparse.ArgumentParser(prog='ledgerdb')
    sub = p.add_subparsers(dest='cmd', required=True)
    u = sub.add_parser('upsert')
    u.add_argument('worker_id')
    u.add_argument('--account')
    u.add_argument('--port', type=int)
    u.add_argument('--credit', type=float)
    u.add_argument('--read-at', dest='read_at')
    u.add_argument('--cut', type=float)
    u.add_argument('--deduct', type=float)
    u.add_argument('--status')
    u.add_argument('--reason')
    s = sub.add_parser('select')
    s.add_argument('--worker')
    s.add_argument('--status')
    s.add_argument('--show-account', action='store_true')
    s.add_argument('--fmt', choices=('md', 'csv', 'json'), default='md')
    a = p.parse_args(argv)
    if a.cmd == 'upsert':
        row = build_row(a)
        if len(row) == 1:
            print('고칠 칸이 없습니다(--credit 등을 주세요)', file=sys.stderr)
            return 2
        opsdb.upsert(TABLE, [row], on_conflict='worker_id')
        print(f"ok {row['worker_id']} 칸={','.join(k for k in row if k != 'worker_id')}")
        return 0
    where = {}
    if a.worker:
        where['worker_id'] = f'eq.{a.worker}'
    if a.status:
        where['status'] = f'eq.{a.status}'
    rows = opsdb.select(TABLE, cols=','.join(COLS), where=where or None, order='worker_id.asc')
    if not a.show_account:
        for r in rows:
            r['account'] = mask(r.get('account'))
    if a.fmt == 'json':
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(opsdb.to_md(rows, list(COLS)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
