# -*- coding: utf-8 -*-
"""플랫폼·계정별 한도 장부(platform_quota)와 시도 기록(quota_events) 쓰기·읽기 도구 (핏, 2026-10-09, 사장님 10/9: 플랫폼별·계정별로 DB 관리).
표 정의: tools/db/platform_quota_schema.sql(10/9 운영 상태 DB simplifier-ops-data에 실행). 접속은 opsdb.py(키 값은 이 코드에 없다).
계정 칸에는 이메일이 들어가므로 읽을 때는 앞 2글자만 보인다(--show-account로 전체).
정지·휴식은 계정×플랫폼 한 줄 단위로만 건다(전면 중단은 사장님 지시 때만).

쓰기
  quotadb.py state --account simon@paywork.io --platform gemini_app --unit video --daily-limit 3 --remaining 0 --status 소진 --reason "..." --reuse-at 2026-10-09T21:00:00+09:00 --pc 신PC
  quotadb.py event --account simon@paywork.io --platform gemini_app --scene 씬48 --result 성공 --remaining-after 1 --secs 124 --runner night_runner --pc 신PC --episode lf07
읽기
  quotadb.py show [--platform flow] [--show-account]
  quotadb.py events [--account ...] [--limit 20] [--show-account]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402


def mask(a):
    if not a or '@' not in a:
        return a
    n, _, d = a.partition('@')
    return n[:2] + '***@' + d


def state(account, platform, **kw):
    row = {'account': account, 'platform': platform}
    row.update({k: v for k, v in kw.items() if v is not None})
    opsdb.upsert('platform_quota', [row], on_conflict='account,platform')


def event(account, platform, result, **kw):
    row = {'account': account, 'platform': platform, 'result': result}
    row.update({k: v for k, v in kw.items() if v is not None})
    opsdb.insert('quota_events', [row])


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('state')
    s.add_argument('--account', required=True); s.add_argument('--platform', required=True)
    for k in ('unit', 'status', 'reason', 'pc', 'reset-model', 'reuse-at', 'read-at'):
        s.add_argument('--' + k)
    for k in ('daily-limit', 'remaining'):
        s.add_argument('--' + k, type=float)
    s.add_argument('--port', type=int)
    e = sub.add_parser('event')
    e.add_argument('--account', required=True); e.add_argument('--platform', required=True); e.add_argument('--result', required=True)
    for k in ('runner', 'pc', 'episode', 'scene', 'refusal-text', 'prompt-variant', 'note'):
        e.add_argument('--' + k)
    e.add_argument('--remaining-after', type=float); e.add_argument('--secs', type=int)
    sh = sub.add_parser('show'); sh.add_argument('--platform'); sh.add_argument('--show-account', action='store_true')
    ev = sub.add_parser('events'); ev.add_argument('--account'); ev.add_argument('--limit', type=int, default=20); ev.add_argument('--show-account', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'state':
        state(a.account, a.platform, unit=a.unit, daily_limit=a.daily_limit, remaining=a.remaining, status=a.status,
              status_reason=a.reason, pc=a.pc, port=a.port, reset_model=a.reset_model, reuse_at=a.reuse_at, read_at=a.read_at)
        print('ok')
    elif a.cmd == 'event':
        event(a.account, a.platform, a.result, runner=a.runner, pc=a.pc, episode=a.episode, scene=a.scene, refusal_text=a.refusal_text,
              prompt_variant=a.prompt_variant, note=a.note, remaining_after=a.remaining_after, secs=a.secs)
        print('ok')
    elif a.cmd == 'show':
        rows = opsdb.select('platform_quota', where=f'platform=eq.{a.platform}' if a.platform else None, order='account.asc')
        for r in rows:
            if not a.show_account:
                r['account'] = mask(r['account'])
        print(opsdb.to_md(rows, ['account', 'platform', 'unit', 'daily_limit', 'remaining', 'status', 'reuse_at', 'pc', 'updated_at']))
    else:
        rows = opsdb.select('quota_events', where=f'account=eq.{a.account}' if a.account else None, order='at.desc', limit=a.limit)
        for r in rows:
            if not a.show_account:
                r['account'] = mask(r['account'])
        print(opsdb.to_md(rows, ['at', 'account', 'platform', 'scene', 'result', 'remaining_after', 'secs', 'prompt_variant']))


if __name__ == '__main__':
    main(sys.argv[1:])
