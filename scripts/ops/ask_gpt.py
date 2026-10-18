"""Azure gpt-5-mini 호출 래퍼(마야·핏 등이 "아이디어 주제가 없을 때" 부른다).

사용:
  python scripts/ops/ask_gpt.py --who 마야 --task ideas "프롬프트"
  python scripts/ops/ask_gpt.py --who 핏 --task ideas --file 카드.md --out 답.md

원칙:
  - 키는 비밀 파일(AZURE_ENV_FILE, 기본 C:/work/_ops/ops-data/.env)에서 코드로만 읽고 출력·기록하지 않는다.
  - 비밀값 의심 문자열이 프롬프트에 있으면 보내지 않는다(ask_dex.sh 1차 관문과 같은 기준).
  - 호출 기록은 usage.jsonl에 한 줄씩(답 본문은 기록하지 않는다). 하루 호출 상한 AZURE_GPT_DAILY_CALLS(기본 300).
  - gpt-5-mini는 추론에 토큰을 쓰므로 max_output_tokens 기본 4000(200이면 답이 빈다, 실측).
종료 코드: 0 성공, 2 입력 오류, 3 비밀값 의심, 4 키 없음, 5 하루 상한 초과, 6 호출 실패.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ENDPOINT = 'https://simon-7978-resource.openai.azure.com/openai/v1/responses'
MODEL = 'gpt-5-mini'
TIMEOUT = 90
DEFAULT_ENV = 'C:/work/_ops/ops-data/.env'
DEFAULT_USAGE = 'C:/work/_ops/azure/usage.jsonl'
SECRET = re.compile(r'(api[_-]?key|token|password|secret|sk-[A-Za-z0-9])', re.I)
IDEAS_SYSTEM = ('너는 주제 발굴 보조다. 아래 요청에 대해 주제·흐름 아이디어를 한국어 번호 목록 5개로 낸다. '
                '각 항목은 한 줄 제목 뒤에 한 줄 근거를 붙인다. 군더더기 설명은 쓰지 않는다.')


class AskError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def env_path():
    return os.environ.get('AZURE_ENV_FILE', DEFAULT_ENV)


def usage_path():
    return Path(os.environ.get('AZURE_USAGE_LOG', DEFAULT_USAGE))


def load_key():
    try:
        lines = Path(env_path()).read_text(encoding='utf-8').splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith('AZURE_OPENAI_API_KEY='):
            return line.split('=', 1)[1].strip().strip('"').strip("'") or None
    return None


def daily_limit():
    try:
        return int(os.environ.get('AZURE_GPT_DAILY_CALLS', '300'))
    except ValueError:
        return 300


def calls_today(now=None):
    day = (now or datetime.now()).strftime('%Y-%m-%d')
    p = usage_path()
    if not p.exists():
        return 0
    n = 0
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            if json.loads(line).get('time', '').startswith(day):
                n += 1
        except ValueError:
            continue
    return n


def log_usage(who, task, usage, ok):
    p = usage_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    usage = usage or {}
    details = usage.get('output_tokens_details') or {}
    rec = {'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'who': who, 'task': task,
           'input_tokens': usage.get('input_tokens', 0), 'output_tokens': usage.get('output_tokens', 0),
           'reasoning_tokens': details.get('reasoning_tokens', 0), 'ok': bool(ok)}
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def extract_text(d):
    return ''.join(c.get('text', '') for o in d.get('output', []) if o.get('type') == 'message'
                   for c in o.get('content', []))


def call_azure(key, text, max_tokens):
    body = json.dumps({'model': MODEL, 'input': text, 'max_output_tokens': max_tokens}).encode('utf-8')
    req = urllib.request.Request(ENDPOINT, data=body, method='POST',
                                 headers={'api-key': key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode('utf-8'))


def run(who, task, prompt, max_tokens=4000, caller=None):
    """성공하면 답 텍스트를 돌려주고, 실패하면 AskError(code, 한 줄 사유)를 던진다."""
    if not prompt.strip():
        raise AskError(2, '프롬프트가 비어 있음')
    if SECRET.search(prompt):
        raise AskError(3, '프롬프트에 비밀값 의심 문자열이 있음: 보내지 않음')
    key = load_key()
    if not key:
        raise AskError(4, 'AZURE_OPENAI_API_KEY를 찾지 못함')
    if calls_today() >= daily_limit():
        raise AskError(5, '하루 호출 상한(AZURE_GPT_DAILY_CALLS=%d) 초과' % daily_limit())
    text = (IDEAS_SYSTEM + '\n\n' + prompt) if task == 'ideas' else prompt
    try:
        d = (caller or call_azure)(key, text, max_tokens)
    except urllib.error.HTTPError as e:
        log_usage(who, task, None, False)
        raise AskError(6, 'HTTP %s' % e.code)
    except Exception as e:  # 타임아웃·네트워크. 사유에는 예외 종류만(키가 들어갈 여지를 없앤다)
        log_usage(who, task, None, False)
        raise AskError(6, '호출 실패: %s' % type(e).__name__)
    answer = extract_text(d)
    log_usage(who, task, d.get('usage'), bool(answer))
    if not answer:
        raise AskError(6, '답이 비어 있음(추론에 토큰이 다 쓰였을 수 있음, --max-tokens를 늘릴 것)')
    return answer


def main(argv=None):
    ap = argparse.ArgumentParser(description='Azure gpt-5-mini 호출 래퍼')
    ap.add_argument('--who', required=True)
    ap.add_argument('--task', default='ideas')
    ap.add_argument('--file')
    ap.add_argument('--out')
    ap.add_argument('--max-tokens', type=int, default=4000)
    ap.add_argument('prompt', nargs='?', default='')
    a = ap.parse_args(argv)
    prompt = a.prompt
    if a.file:
        try:
            prompt = Path(a.file).read_text(encoding='utf-8')
        except OSError:
            print('입력 파일을 읽지 못함', file=sys.stderr)
            return 2
    try:
        answer = run(a.who, a.task, prompt, a.max_tokens)
    except AskError as e:
        print('실패(%d): %s' % (e.code, e.msg), file=sys.stderr)
        return e.code
    if a.out:
        Path(a.out).write_text(answer, encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    print(answer)
    return 0


if __name__ == '__main__':
    sys.exit(main())
