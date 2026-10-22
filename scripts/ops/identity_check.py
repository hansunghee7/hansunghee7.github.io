#!/usr/bin/env python3
"""P2H 신원 대조: 이 폴더에 연결된 카빗 서버 이름이 한 사람(페르소나)의 것인지 본다.

카빗DM 2차 슈퍼프로젝트 P2H (노트#127 계열). 연결 서버 이름이 섞이면(예: 한 폴더에
carvit_tam 과 carvit-jitu 가 함께 있으면) 에이전트가 남의 이름으로 DM을 보내는 사고가
난다. 서버 토큰은 읽지 않고 이름만 본다(자격증명 안 건드림).

사용: python scripts/ops/identity_check.py [--cwd 폴더] [--claude-json 경로] [--persona 탐]
종료 코드: 0 정상(내 이름 한 줄 출력), 1 경고(섞임·미등록·기대 이름 불일치·이름 없음).
"""
import argparse, json, os, re, sys, time
from pathlib import Path

LOG = Path('C:/work/_ops/identity_check.log')

# 서버 이름 → 페르소나. 이름 규칙: carvit_<영문> 또는 carvit-<영문> 또는 carvit_kabit-<영문>.
# 접두만 있는 'carvit' 은 기본 커넥터라 누구의 것인지 알 수 없다(generic).
PERSONA = {
    'tam': '탐', 'jitu': '지투', 'note': '노트', 'maya': '마야', 'fit': '핏',
    'doumi': '도우미', 'bt': '비티', 'dex': '덱스', 'book': '북',
}


def persona_of(server):
    """('generic'|'known'|'unknown', 페르소나 또는 None)"""
    if server == 'carvit':
        return 'generic', None
    m = re.fullmatch(r'carvit(?:_kabit)?[-_](.+)', server)
    if not m:
        return 'unknown', None
    key = m.group(1).replace('kabit-', '')
    if key in PERSONA:
        return 'known', PERSONA[key]
    return 'unknown', None


def servers_for(cwd, claude_json):
    names = set()
    try:
        d = json.loads(Path(claude_json).read_text(encoding='utf-8'))
        norm = lambda p: p.replace('\\', '/').rstrip('/').lower()
        for k, v in d.get('projects', {}).items():
            if norm(k) == norm(cwd):
                names |= set((v.get('mcpServers') or {}).keys())
        names |= set((d.get('mcpServers') or {}).keys())
    except (OSError, ValueError):
        pass
    mj = Path(cwd) / '.mcp.json'
    if mj.exists():
        try:
            names |= set((json.loads(mj.read_text(encoding='utf-8')).get('mcpServers') or {}).keys())
        except (OSError, ValueError):
            pass
    return sorted(n for n in names if n.startswith('carvit'))


def check(servers, expected=None):
    """경고 문장 목록(비면 정상)."""
    warns, personas = [], set()
    for s in servers:
        kind, p = persona_of(s)
        if kind == 'known':
            personas.add(p)
        elif kind == 'unknown':
            warns.append(f'미등록 서버 이름 {s}: 누구 것인지 모른다')
    if len(personas) > 1:
        warns.append('한 폴더에 여러 사람의 서버가 섞여 있다: ' + ', '.join(sorted(personas)))
    if expected and personas and personas != {expected}:
        warns.append(f'이 세션은 {expected}인데 연결된 서버는 {", ".join(sorted(personas))}')
    if not personas and not warns:
        warns.append('이름이 없다: 연결된 카빗 서버에서 내 이름을 읽지 못했다. 사장님이 이름을 붙여 시작하세요')
    return warns


def who_line(servers):
    """이름이 하나로 정해지면 세션 시작 맨 위에 보일 한 줄(사장님 10/22: 이름을 먼저 붙이고 의식을 시킨다)."""
    names = {persona_of(s)[1]: s for s in servers if persona_of(s)[0] == 'known'}
    if len(names) != 1:
        return ''
    p, srv = next(iter(names.items()))
    return f'🪪 너는 {p}({srv})이다. 세션 시작 의식(session-start 스킬)을 먼저 하세요. 이미 했다면 건너뛴다.'


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--claude-json', default=str(Path.home() / '.claude.json'))
    ap.add_argument('--persona', default=os.environ.get('CARVIT_PERSONA', ''))
    ap.add_argument('--no-log', action='store_true')
    a = ap.parse_args()
    servers = servers_for(a.cwd, a.claude_json)
    warns = check(servers, a.persona or None)
    if warns:
        print('🔴 카빗 신원 대조 실패(P2H): ' + ' / '.join(warns))
        print('   서버: ' + ', '.join(servers) + '. 이 폴더에서 DM을 보내기 전에 agents의 me가 내 이름인지 확인하고, 섞였으면 폴더를 나눈다(카빗DM_2차 P3).')
        if not a.no_log:
            try:
                LOG.parent.mkdir(parents=True, exist_ok=True)
                with LOG.open('a', encoding='utf-8') as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{a.cwd}\t{','.join(servers)}\t{' | '.join(warns)}\n")
            except OSError:
                pass
        return 1
    line = who_line(servers)
    if line:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
