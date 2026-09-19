import os, subprocess, sys, json, shutil, pathlib, itertools
CNT = itertools.count()
HERE = pathlib.Path(__file__).parent
SCRIPT = HERE / 'mailbox_courier.py'
MB = HERE / 'tmb'
ST = HERE / 'tstate.json'


def reset():
    shutil.rmtree(MB, ignore_errors=True)
    ST.unlink(missing_ok=True)
    MB.mkdir()


def mail(to, frm, title, body, ask=None, urgent=False, name=None):
    d = MB / to
    d.mkdir(exist_ok=True)
    name = name or f"20260920-0700-{frm}-{next(CNT):03d}.md"
    txt = f"# {title}\n\n받는이: {to}\n보낸이: {frm}\n시각: 2026-09-20 07:00:00\n긴급: {'예' if urgent else '아니오'}\n"
    if ask:
        txt += f"요청: {ask}\n"
    txt += f"\n{body}\n"
    (d / name).write_text(txt, encoding='utf-8')


def run(agent_chat=None, extra=()):
    env = dict(os.environ)
    env.pop('COURIER_TEST_AGENT_CHAT', None)
    if agent_chat:
        env['COURIER_TEST_AGENT_CHAT'] = agent_chat
    r = subprocess.run([sys.executable, str(SCRIPT), '--mailbox-dir', str(MB), '--state-file', str(ST), *extra],
                       capture_output=True, text=True, encoding='utf-8', env=env)
    return (r.stdout + r.stderr).strip(), r.returncode


def check(label, cond, out):
    print(('PASS ' if cond else 'FAIL ') + label)
    if not cond:
        print('   출력:', out)


reset()
# 과거 우편(폭주 재현): 긴급 시험 우편 3건 + 사장님 앞 12건
for i in range(3):
    mail('마야', '탐', f'긴급 우편 테스트{i}', '시험', urgent=True)
for i in range(12):
    mail('사장님', '탐', f'옛 우편 {i}', '옛 본문')

out, rc = run()
check('a 개정 첫 실행: 기존 15건을 발송 없이 처리, 종료 0', '발송 없이 처리 표시함' in out and '15건' in out and rc == 0, out)
out, rc = run(agent_chat='X')
check('a2 첫 실행 뒤 재실행: 옛 우편 발송 0(폭주 없음)', '발송 예정' not in out, out)

mail('사장님', '탐', '결정 필요: 크론 재개', '배달원 수정판 배포 뒤 재개 여부입니다.', ask='재개해도 되는지 답해 주세요')
mail('사장님', '탐', '참고: 작업 끝', '단순 보고입니다.')
out, rc = run(agent_chat='X')
check('b 사장님+요청 우편은 신솔라 형식으로 발송 예정', '→ 사장님(신솔라)' in out and '👉 재개해도 되는지' in out and '배달원 수정판' in out, out)
check('c 사장님 앞 요청 없는 우편은 폰 미발송', '참고: 작업 끝' not in out, out)

mail('마야', '탐', '글 초안 검토', '초안 3편을 확인해 주세요.')
out, rc = run(agent_chat=None)
check('d 에이전트 채널 미설정이면 에이전트 우편은 어디에도 안 감', '발송 예정' not in out and '글 초안' not in out, out)

mail('마야', '탐', '슬롯 확정', '토요일 슬롯을 확정했습니다.')
out, rc = run(agent_chat='X')
check('e 에이전트 채널 설정 시 모니터링 형식 발송 예정', '📨 탐 → 마야 | 슬롯 확정' in out and '토요일 슬롯' in out, out)
out, rc = run(agent_chat='X')
check('f 같은 우편 재발송 없음(중복 방지)', '발송 예정' not in out, out)

for i in range(65):
    mail('핏', '마야', f'대량 {i:02d}', '대량 시험')
out, rc = run(agent_chat='X')
n = out.count('발송 예정')
check(f'g 에이전트 채널 하루 상한 60건 넘으면 나머지는 조용히 처리(발송 예정 {n}건)', n <= 60, out[-300:])
out, rc = run(agent_chat='X')
check('g2 상한 뒤 재실행에도 발송 0', '발송 예정' not in out, out)

out, rc = run(agent_chat='X', extra=['--dry-run'])
check('h --dry-run은 상태를 쓰지 않음', 'DRY-RUN' in out and rc == 0, out)
st = json.loads(ST.read_text(encoding='utf-8'))
check('i 상태 파일에 baseline과 notified가 기록됨', st.get('baseline') == 'policy_20260920' and len(st['notified_files']) > 15, str(st)[:200])
