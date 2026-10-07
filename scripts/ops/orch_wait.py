# -*- coding: utf-8 -*-
"""배시 대기 루프(오케스트레이터 신호 감시): 발주한 카드가 끝났다는 신호가 올 때까지 git fetch로 기다린다.
신호 = tasks/todo 지시서가 tasks/done으로 옮겨져 main에 올라옴 / 헤르메스 카드가 solar-bible tasks/done으로 이동. 하나라도 오면 종료(0), 시간 초과는 종료 1.
사용: python scripts/ops/orch_wait.py --main <파일명...> --solar <파일명...> [--interval 120] [--timeout 7200]  (run_in_background로 실행)"""
import argparse
import subprocess
import time

CLOUD = {'main': '/home/user/hansunghee7.github.io', 'solar': '/home/user/solar-bible'}


def done_files(repo):
    subprocess.run(['git', 'fetch', '-q', '--depth', '1', 'origin', 'main'], cwd=repo, capture_output=True, timeout=120)
    p = subprocess.run(['git', 'ls-tree', '--name-only', 'origin/main', 'tasks/done/'], cwd=repo, capture_output=True, text=True, encoding='utf-8', timeout=60)
    return {l.split('/')[-1].strip('"') for l in p.stdout.splitlines()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', nargs='*', default=[])
    ap.add_argument('--solar', nargs='*', default=[])
    ap.add_argument('--interval', type=int, default=120)
    ap.add_argument('--timeout', type=int, default=7200)
    a = ap.parse_args()
    end = time.time() + a.timeout
    while time.time() < end:
        got = [f'main:{n}' for n in a.main if n in done_files(CLOUD['main'])] + [f'solar:{n}' for n in a.solar if n in done_files(CLOUD['solar'])]
        if got:
            print('신호 도착:', ', '.join(got))
            return 0
        time.sleep(a.interval)
    print('시간 초과: 신호 없음')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
