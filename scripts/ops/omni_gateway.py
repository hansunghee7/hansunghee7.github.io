# -*- coding: utf-8 -*-
"""OmniRoute 장애 전환 출구(N161, 2026-10-05 탐, 사장님 지시): GCP 크레딧(Vertex) 상한에 닿았을 때 무료 모델 풀을 라우터 콤보로 넓게 쓴다.
콤보 `hermes-flash` = 제미나이 3.8 flash → 3.7 flash → 3.1 flash-lite(전부 무료 키, 한 곳이 429면 다음으로). 크레딧이 12/23에 끝난 뒤에도 같은 입구로 무료 풀을 쓴다.
방식: 호출 때만 기동(평소엔 꺼 둠). 기동 약 40초, 이미 떠 있으면 재사용. 호출이 끝나면 직접 띄운 경우에만 종료한다(OMNI_KEEP=1이면 유지).
설정 파일(저장소 밖): C:/work/_ops/n152/omniroute.env (데이터 폴더·포트·키 요구 켬·외부 동기화 끔), 에이전트 키 omniroute_agent_keys.env. 값은 출력하지 않는다.
시간 제한: 기동 최대 60초 + 호출 60초, 넘기면 실패로 돌려주고 호출자가 직접 무료 키로 넘어간다(10/5 냉기동 3회 중 2회 성공 47~163초, 1회 125초 시간 초과 실측).
검색 연동 호출은 이 경로로 처리하지 않는다(콤보는 일반 대화 호출). 반환: {"ok": bool, "text": str, "model": str, "secs": float} """
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

N152 = Path(r'C:\work\_ops\n152')
BASE = 'http://127.0.0.1:20128'
SERVER_DIR = N152 / 'omniroute-iso' / 'node_modules' / 'omniroute'
LOGF = N152 / 'router_failover.log'
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _env():
    env = dict(os.environ)
    for l in (N152 / 'omniroute.env').read_text(encoding='utf-8').splitlines():
        if '=' in l and not l.startswith('#'):
            k, v = l.split('=', 1)
            env[k] = v
    return env


def _up():
    try:
        urllib.request.urlopen(BASE + '/api/health', timeout=3)
        return True
    except Exception as e:  # noqa: BLE001
        return bool(getattr(e, 'code', None))  # 401 등 응답이 오면 떠 있는 것


def _agent_key(agent='hermes-test'):
    for l in (N152 / 'omniroute_agent_keys.env').read_text(encoding='utf-8').splitlines():
        if l.startswith('OMNIROUTE_KEY_' + agent.upper().replace('-', '_') + '='):
            return l.split('=', 1)[1].strip()
    raise KeyError(agent)


def chat(prompt, model='hermes-flash', agent='hermes-test', max_tokens=4096, timeout=60, startup_wait=60):
    t0 = time.time()
    started = None
    try:
        if not _up():
            started = subprocess.Popen(['node', 'bin/omniroute.mjs', 'serve', '--no-open', '--no-tray'], cwd=str(SERVER_DIR), env=_env(),
                                       stdout=open(LOGF, 'a'), stderr=subprocess.STDOUT, creationflags=FLAGS)
            for _ in range(max(1, startup_wait // 3)):
                time.sleep(3)
                if _up():
                    break
            else:
                return {'ok': False, 'text': '', 'model': model, 'secs': round(time.time() - t0, 1), 'why': '라우터 기동 시간 초과'}
        key = _agent_key(agent)
        body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens, 'stream': False}
        req = urllib.request.Request(BASE + '/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode('utf-8', 'replace'))
        text = ((j.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
        return {'ok': bool(text.strip()), 'text': text, 'model': j.get('model', model), 'secs': round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {'ok': False, 'text': '', 'model': model, 'secs': round(time.time() - t0, 1), 'why': type(e).__name__}
    finally:
        if started is not None and os.environ.get('OMNI_KEEP') != '1':
            # 감독 프로세스를 끄면 일꾼 프로세스가 남아 포트를 계속 잡는다(10/5 실측) → 자식까지 한 번에 끈다
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(started.pid)], capture_output=True, creationflags=FLAGS)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    r = chat(sys.argv[1] if len(sys.argv) > 1 else '한 단어로 답: 안녕')
    print({k: (v if k != 'text' else v[:40]) for k, v in r.items()})
    sys.exit(0 if r['ok'] else 1)
