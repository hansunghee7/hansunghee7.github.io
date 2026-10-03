#!/usr/bin/env python3
"""denied_notify.py 훅의 허용 규칙 승인 요청 시험(대장 N137 ⑤, 2026-10-04 탐). 가짜 pass.py(받은 인자를 파일에 적음)·임시 기록 폴더. 텔레그램·실제 설정은 건드리지 않는다.
사용: python scripts/ops/test_denied_notify.py
"""
import json, os, pathlib, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
TMP = pathlib.Path(tempfile.mkdtemp())
STUB = TMP / 'stub_pass.py'
STUB.write_text("import sys,json,pathlib\npathlib.Path(sys.argv[0]).with_name('calls.jsonl').open('a',encoding='utf-8').write(json.dumps(sys.argv[1:],ensure_ascii=False)+'\\n')\n", encoding='utf-8')
ENV = dict(os.environ, DENIED_LOG=str(TMP / 'log.jsonl'), DENIED_STAMP=str(TMP / 'tg.stamp'), DENIED_NO_TG='1', DENIED_PASS_CLI=str(STUB), DENIED_RULE_STAMPS=str(TMP / 'stamps.json'), PYTHONIOENCODING='utf-8')
out, fails = [], 0


def check(name, cond, extra=''):
    global fails
    out.append(f"{'통과' if cond else '실패'} {name}{(' — ' + str(extra)) if not cond and extra != '' else ''}")
    fails += 0 if cond else 1


def fire(payload):
    subprocess.run([sys.executable, str(HERE / 'denied_notify.py')], input=json.dumps(payload).encode('utf-8'), env=ENV, timeout=30)
    time.sleep(1.2)


def calls():
    f = TMP / 'calls.jsonl'
    return [json.loads(x) for x in f.read_text(encoding='utf-8').splitlines()] if f.exists() else []


fire({'tool_name': 'Write', 'reason': '[Security Weaken]', 'tool_input': {'file_path': 'C:\\work\\saegim-pass-dev\\recipe.js', 'content': 'SECRET_BODY'}, 'cwd': 'C:/work/hansunghee7.github.io'})
c = calls()
check('Write 거부 → 승인 요청 한 번(분류·도구·저장소 폴더·요청자)', len(c) == 1 and c[0][:1] == ['claude_rule'] and c[0][c[0].index('--category') + 1] == 'Security Weaken' and c[0][c[0].index('--tool') + 1] == 'Write' and c[0][c[0].index('--target') + 1] == 'C:/work/saegim-pass-dev', c)
check('요청 인자에 파일 내용·명령 본문이 없음', 'SECRET_BODY' not in json.dumps(c, ensure_ascii=False))
fire({'tool_name': 'Write', 'reason': '[Security Weaken]', 'tool_input': {'file_path': 'C:/work/saegim-pass-dev/other.js'}})
check('같은 분류·도구·저장소는 30분에 한 번만(승인 피로 방지)', len(calls()) == 1)
fire({'tool_name': 'Bash', 'reason': '[Create RCE Surface]', 'tool_input': {'command': 'python x.py'}, 'cwd': 'C:\\work\\simplifier-cxo-db\\reports'})
c = calls()
check('Bash 거부는 작업 폴더의 저장소 루트로', len(c) == 2 and c[1][c[1].index('--target') + 1] == 'C:/work/simplifier-cxo-db' and c[1][c[1].index('--category') + 1] == 'Create RCE Surface', c[1:])
fire({'tool_name': 'Bash', 'reason': '[Auto-Mode Bypass]', 'tool_input': {'command': 'x'}, 'cwd': 'C:/work/saegim-pass-dev'})
check('검사 우회 시도 분류는 요청하지 않음(대화로만)', len(calls()) == 2)
fire({'tool_name': 'mcp__claude-in-chrome__javascript_tool', 'reason': '[Secret-Store Writes]', 'tool_input': {}})
check('브라우저 도구는 요청하지 않음(범위를 폴더로 못 정함)', len(calls()) == 2)
fire({'tool_name': 'Write', 'reason': '[Security Weaken]', 'tool_input': {'file_path': 'D:/other/x.txt'}})
check('C:/work 밖은 요청하지 않음', len(calls()) == 2)
fire({'tool_name': 'Bash', 'reason': 'The server-side auto mode classifier judged this action dangerous (it gave no explanation)', 'tool_input': {'command': 'x'}, 'cwd': 'C:/work/dex-trial-1'})
c = calls()
check('설명 없는 거부는 Unsafe Action 분류로 요청', len(c) == 3 and c[2][c[2].index('--category') + 1] == 'Unsafe Action', c[2:])
rows = [json.loads(x) for x in (TMP / 'log.jsonl').read_text(encoding='utf-8').splitlines()]
check('거부 기록(denied_log)은 계속 남고 본문은 기록 안 함', len(rows) == 7 and all('SECRET_BODY' not in json.dumps(r, ensure_ascii=False) for r in rows))
ENV2 = dict(ENV, DENIED_NO_RULE='1')
subprocess.run([sys.executable, str(HERE / 'denied_notify.py')], input=json.dumps({'tool_name': 'Write', 'reason': '[Security Weaken]', 'tool_input': {'file_path': 'C:/work/zzz/a.js'}}).encode('utf-8'), env=ENV2, timeout=30)
time.sleep(1)
check('DENIED_NO_RULE이면 요청 안 함(끄는 스위치)', len(calls()) == 3)

print('\n'.join(out)); print(f'실패 {fails}건'); sys.exit(1 if fails else 0)
