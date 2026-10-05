# -*- coding: utf-8 -*-
"""상시 검수 큐(N161, 2026-10-05 탐, 사장님 지시 "비티와 덱스는 최대한 활용"): 하루에 main에 병합된 코드 PR의 diff를 덱스(코덱스)와 비티(제미나이)에게 각각 독립 리뷰로 맡긴다.
탐이 다음 날 두 리뷰를 읽고 판정한다(리뷰는 가설, 채택 전 실측). 결과: C:/work/_ops/reviews/<날짜>/ (PR별 dex_·bt_ 파일과 INDEX.md).
대상: 최근 25시간 안에 병합된 PR 중 코드 파일(.py .js .sh .toml .ps1 .html .css)이 바뀐 것. 문서·로그만 바뀐 PR은 건너뜀. 비밀값이 의심되는 diff는 보내지 않음.
한도: 하루 PR 최대 5건(MAX_PR). 덱스 한도 신호가 나면 비티만 계속하고, 비티가 막히면(비티 쪽이 Vertex로 우회) 그대로 진행한다.
사용: python scripts/ops/review_queue.py [--dry]   종료 코드 0 = 정상(리뷰할 PR이 없어도 0), 1 = 실행 도구 오류"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT_ROOT = Path(r'C:\work\_ops\reviews')
BASH = r'C:\Program Files\Git\bin\bash.exe'
CODE_EXT = ('.py', '.js', '.sh', '.toml', '.ps1', '.html', '.css')
MAX_PR = 15  # 한 번 실행의 상한(목표가 더 커도 이 수까지, 나머지는 다음 실행에서)
LOOKBACK_DAYS = 14
MAX_DIFF = 40_000
SECRET = re.compile(r'(api[_-]?key|password|secret|sk-[A-Za-z0-9]|AIza[0-9A-Za-z_-]{20})', re.I)
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PROMPT = ('# 코드 리뷰 요청: PR #{n} {title} (읽기만, 수정 금지)\n'
          '관점: ① 실제로 틀릴 수 있는 버그(예외, 중복, 멱등성, 경계값) ② 데이터·설정이 조용히 망가지는 경로 ③ 안전·권한 문제 ④ 고칠 때 가장 효과 큰 3가지.\n'
          '형식: 한국어 25줄 이내, 파일명:줄 인용, 확신 없으면 "불확실". 새 사실을 지어내지 말 것. diff에 없는 코드는 추측하지 말 것.\n\n```diff\n{diff}\n```\n')


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=FLAGS, **kw)


def code_diff(n):
    r = run(['gh', 'pr', 'diff', str(n)], cwd=str(REPO), timeout=120)
    if r.returncode != 0:
        return ''
    parts = re.split(r'(?m)^(?=diff --git )', r.stdout)
    keep = [p for p in parts if p.startswith('diff --git') and re.match(r'diff --git a/(\S+)', p) and re.match(r'diff --git a/(\S+)', p).group(1).lower().endswith(CODE_EXT)]
    return ''.join(keep)


def ask(script, card, out, extra_env=None):
    env = {**os.environ, **(extra_env or {})}
    r = run([BASH, str(HERE / script), str(card), str(out)], env=env, timeout=900)
    return r.returncode


def main():
    dry = '--dry' in sys.argv
    sys.path.insert(0, str(HERE))
    import dynamic_quota as dq
    st = dq.measure()  # 어제까지 기록·이월 갱신, 오늘 목표 계산(다이나믹 한도)
    need = max(0, st['today']['targets']['덱스'] - dq.used_on('덱스', datetime.now().strftime('%Y-%m-%d')))
    reviewed = {int(m.group(1)) for f in OUT_ROOT.glob('*/dex_pr*.md') for m in [re.search(r'dex_pr(\d+)', f.name)] if m}
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    r = run(['gh', 'pr', 'list', '--state', 'merged', '--search', f'merged:>={since}', '--json', 'number,title', '--limit', '30'], cwd=str(REPO), timeout=120)
    if r.returncode != 0:
        print('gh 실패:', r.stderr[:200])
        return 1
    prs = json.loads(r.stdout or '[]')
    day = OUT_ROOT / datetime.now().strftime('%Y%m%d')
    day.mkdir(parents=True, exist_ok=True)
    lines, done = [], 0
    print(f'덱스 오늘 목표 {st["today"]["targets"]["덱스"]}회 중 남은 {need}회 → 리뷰할 PR 최대 {min(need, MAX_PR)}건 (미검수 {len([p for p in prs if p["number"] not in reviewed])}건)')
    for pr in sorted(prs, key=lambda x: -x['number']):  # 최근 것부터, 밀린 것은 뒤에서 채운다
        if done >= min(need, MAX_PR):
            break
        n = pr['number']
        if n in reviewed:
            continue  # 이미 리뷰함
        diff = code_diff(n)
        if not diff:
            continue
        if SECRET.search(diff):
            lines.append(f'- #{n} {pr["title"]}: 비밀값 의심 문자열이 있어 보내지 않음')
            continue
        card = day / f'card_pr{n}.md'
        card.write_text(PROMPT.format(n=n, title=pr['title'], diff=diff[:MAX_DIFF]), encoding='utf-8')
        done += 1
        if dry:
            lines.append(f'- #{n} {pr["title"]}: (dry) 카드 {card.stat().st_size}바이트')
            continue
        rc_d = ask('ask_dex.sh', card, day / f'dex_pr{n}.md', {'DEX_WORKDIR': r'C:\work\_ops\dex_wd'})
        # 서로 다른 계열의 두 번째 의견을 섞는다(사장님 10/5 "소넷 쓰면 해결"): 홀수 PR은 비티-소넷(클로드 계열, 크레딧 안 씀), 짝수 PR은 기본 순서(제미나이 계열)
        rc_b = ask('ask_bt.sh', card, day / f'bt_pr{n}.md', {'BT_MODEL': 'sonnet'} if n % 2 else None)
        lines.append(f'- #{n} {pr["title"]}: 덱스 rc={rc_d} → dex_pr{n}.md / 비티 rc={rc_b} → bt_pr{n}.md')
    idx = day / 'INDEX.md'
    old = idx.read_text(encoding='utf-8') if idx.exists() else f'# 검수 큐 {day.name}\n'
    idx.write_text(old + '\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
    print(f'병합 PR {len(prs)}건 중 리뷰 대상 {done}건', '\n'.join(lines))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print('실패:', type(e).__name__, str(e)[:200])
        sys.exit(1)
