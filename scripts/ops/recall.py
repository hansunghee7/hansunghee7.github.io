# -*- coding: utf-8 -*-
"""기억 도우미(G5, 2026-10-05 탐, 사장님: "새 세션이 되면 잊어버리고 사장이 이상한 얘기하는 사람처럼 만든다. 해당 대화를 할 때는 프로세스표에서 기억을 찾아서(수파베이스) 답해 주길"):
사장님이 말을 걸면 답하기 전에 ① 공정 단계 카드(DB section=step) ② 사장님 말 원장(section=boss, 최근 14일 = 최신 의사결정)에서 같은 주제의 기억을 찾아 짧게 보여 준다. 이것이 1차 검색이다.
슈퍼색인관리(사장님 10/15 명명): 1차=정본 프로세스(공정 카드)+최신 의사결정, 2차=정본 문서, 그 밖(업무 기록 worklog·handoff·closed·open·fact·history)은 히스토리라 1차 결과에 섞지 않는다. 히스토리는 `--history`로만 본다.
사고(2026-10-15): 노트가 10/13에 적은 'GitHub Actions 분 절감' 행이 worklog 구역이라 이 도구가 한 번도 찾지 못해 사장님이 같은 설명을 되풀이하셨다(공정 카드 탐 #65·#68).
속도: 매번 DB를 부르면 1초 이상 걸리므로 시간당 한 번 로컬 캐시(C:/work/_ops/recall_cache.json)로 내려받고, 조회는 캐시만 읽는다(수십 ms).
사용:
  python scripts/ops/recall.py build                      캐시 갱신(카드 전체 + 최근 14일 사장님 발화)
  python scripts/ops/recall.py "사장님이 한 말 그대로"      관련 카드·발화 상위 몇 개
  python scripts/ops/recall.py --hook < prompt.json        훅용: stdin JSON의 prompt로 찾아 관련 있을 때만 출력(없으면 조용히 종료)
기억 검색 개선(2026-10-21, 공정 카드 탐-슈퍼글로벌 #103~#105, 사장님: "찾아야 하는 것은 찾기 쉽게, 혼란스러운 정보는 찾기 어렵게"):
  - 순위: 층(편 상태·지원현황·카드·사장님 말·문서)을 고정 순서로 잇지 않고 질문 낱말 적중 비율로 합친다. 정본 문서는 상위 3개 안에 한 자리를 보장한다.
  - 낱말: 조사 뒤 흔한 어미(-할·-하는·-된 등)를 뗀다. 같은 뜻 묶음은 한 단위(적중 1점)로 센다.
  - 낡음: 제목 맨 앞 [대체됨]·[폐기] 같은 표시가 붙은 카드·문서 절은 기본 검색에서 뺀다(--history에서는 보인다).
  - 히스토리 문서(진행상황·이력·기록 문서)는 기본 검색의 정본 문서 층에서 뺀다(--history에서는 보인다).
  - 캐시: 30분이 지나면 훅·직접 실행 때 뒤에서 새로 만들고, 3시간이 지나면 결과 맨 위에 캐시 시각을 알린다.
  - 지식DB 층 오류는 삼키지 않고 결과 끝에 원인 한 줄(값·키 없이)을 보인다.
  - 출력에서 이메일·전화번호·키 형식은 가린다(캐시 원본은 그대로).
  변경별 효과를 따로 재려고 환경 변수 RECALL_OFF=rank,norm,syn,stale,histdoc,docname,mask 로 하나씩 끌 수 있다(기본은 모두 켬)."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
CACHE = Path(r'C:\work\_ops\recall_cache.json')
REFRESH_AFTER_MIN = 30   # 감시 대장(fn:recall-cache)은 60분마다 만든다. 그 사이 새 카드가 빠지지 않게 쓸 때 뒤에서 한 번 더 만든다
NOTE_AFTER_H = 3         # 정기 갱신이 세 번 넘게 빠졌으면 결과 맨 위에 알린다
BUILD_LOCK_MIN = 15      # 뒤에서 만드는 중이면 이 시간 동안 다시 띄우지 않는다


def on(feature):
    """RECALL_OFF에 이름이 없으면 켜짐(측정용 스위치, 기본 모두 켬)."""
    return feature not in {x.strip() for x in os.environ.get('RECALL_OFF', '').split(',') if x.strip()}


JOSA =('에서는', '으로는', '이라는', '에서', '으로', '에게', '한테', '까지', '부터', '처럼', '보다', '하고', '이나', '이랑', '은', '는', '이', '가', '을', '를', '의', '에', '로', '와', '과', '도', '만', '요', '죠', '야', '나')
STOP = {'그냥', '이제', '그리고', '그런데', '그래서', '하는', '있는', '없는', '있어', '있다', '해서', '해주', '주세', '것이', '거를', '이거', '저거', '우리', '탐이', '사장', '사장님', '같은', '대한', '위해', '때문', '아니', '정말', '지금', '계속', '다시', '이런', '그런', '어떤', '어떻', '하면', '해요', '하세요', '합니다', '입니다', '있나', '있는지', '되었', '되어', '됩니다', '않고', '않는', '말고', '그게', '이게', '뭐가', '무엇', '어디', '언제', '얼마', '몇개', '어떻게', '됐지', '됐나', '됐나요', '어디까지',
        '하나', '되나', '했나', '뭐였', '알려', '알려줘', '어떤가', '건가', '건지', '인가', '인지', '맞나', '맞죠',
        '때는', '되죠', '됐죠', '다른', '없이', '써도', '해도', '돼요', '되요', '받아', '뜨면'}  # 질문 꼬리(2026-10-21)

# 편 상태 정본(10/15 핏 사모에드 사고, 페이블 진단 개선안 C): 편을 물으면 손글씨 카드보다 컨펌대장의 마지막 사건을 맨 위에 둔다
SHORTS = Path(r'C:\work\shorts-lab')
EP_LEDGER = SHORTS / 'pilot-shorts2' / '컨펌대장.jsonl'
EP_HOLD = re.compile(r'(보류|대기|중단|만들지 마|하지 마)')
LOG_CAP = 2000
LOG_SECTIONS = ('worklog', 'handoff', 'closed', 'open', 'fact', 'history')
# 같은 뜻으로 쓰이는 말(사장님은 '깃 배포', 기록은 'Actions 분 절감'으로 적은 사고): 묶음 안의 말은 서로 바꿔 찾는다.
SYN = (('배포', 'deploy', '디플로이', 'actions', '워크플로'), ('분', 'minutes', '분량', '사용량'), ('한도', '상한', 'limit', '2000', '2,000'), ('횟수', '회수', '묶음', '줄이기', '절감'), ('깃', 'git', 'github', '깃허브'),
       # 슈퍼 계열 이름과 옛 이름은 같은 뜻(사장님 10/15 "슈퍼로 다 맞출까요", 별칭 방식: docs/슈퍼_용어집.md)
       # 지원사업 회사 이름(사장님은 '구글', 지원현황 DB는 'Google'로 적는다, 10/16 CF004)
       ('구글', 'google'), ('엔비디아', 'nvidia', '인셉션', 'inception'), ('마이크로소프트', 'microsoft', '애저', 'azure'), ('아마존', 'aws'), ('앤트로픽', 'anthropic', '클로드'),
       ('슈퍼오케스트라', '오케스트레이션', '오케스트레이터', '비상모드'), ('슈퍼버닝', '버닝', '백로그버닝'), ('슈퍼인덱싱', '색인관리', '슈퍼색인', '문서리팩토링', '구조문서'),
       ('슈퍼사서', '사서', '감수', '컨텍스트감수', 'context-audit'))
# 일상어 사전(2026-10-21): 질문은 일상어, 기록은 업무어로 적혀 낱말이 갈리는 흔한 쌍. 특정 질문용이 아니라 사전 성격으로만 둔다(20쌍 이내).
SYN_DAILY = (('휴식', '쉬게', '쉬는', '쉬어', '쉬기', '쉬고'), ('승인', '허락', '허가', '컨펌'), ('삭제', '지우', '지워'), ('비용', '요금', '과금'),
             ('오류', '에러', 'error'), ('일정', '스케줄', 'schedule'), ('교신', '소통', '연락'), ('이름', '명칭', '네이밍'),
             ('순서', '차례'), ('금지', '불가'), ('시험', '테스트'), ('동영상', '비디오', 'video'), ('질문', '물어', '묻'),
             ('기억', '회상', 'recall'), ('고객', '손님'), ('예약', '스케줄링'), ('스타트업', 'startup'), ('클라우드', 'cloud'))
# 흔한 어미(조사를 뗀 뒤 한 번 더 뗀다, 긴 것부터). 떼고 남는 말이 두 글자 이상일 때만 뗀다('제한'·'권한'은 그대로)
EOMI = tuple(sorted(('했었죠', '했었나요', '했나요', '하나요', '되나요', '됐나요', '했던', '하는', '하고', '하게', '하면', '해서', '해야', '하려면',
                     '하기로', '되는', '되면', '할지', '려면', '으면', '할', '한', '된', '될', '했', '됐',
                     '했나', '했죠', '됐죠', '되죠', '이죠', '다고', '라고', '하', '일'), key=len, reverse=True))
# 낡음 표시: 제목 맨 앞 괄호 안의 말(recall_eval·confusion_scan과 같은 계열, '정정'·'→ 정본'은 바로잡은 현행이라 뺀다)
STALE_MARK = re.compile(r'(대체됨|폐기|무효|옛 방식|옛 규칙|이전 규칙|더 이상 쓰지|롤백)')
LEAD_BRACKET = re.compile(r'^\s*[\[(（【]([^\])）】]{0,200})[\])）】]')


def stale_mark(title):
    """제목 맨 앞 괄호에 낡음 표시가 있으면 그 표시 문자열, 없으면 ''."""
    m = LEAD_BRACKET.match(title or '')
    return m.group(1) if m and STALE_MARK.search(m.group(1)) else ''


def syn_table():
    return SYN + (SYN_DAILY if on('syn') else ())


def syn_groups(q, text=''):
    """질의에서 켜진 동의어 그룹마다 새로 붙는 말 목록(그룹 하나는 적중 1점으로만 센다, 비티 10/15 지적)."""
    raw = text.lower()
    out = []
    for g in syn_table():
        # '깃배포'처럼 붙여 쓴 말도 잡도록 두 글자 이상 동의어는 원문 부분 문자열로도 찾는다
        if any(t in g for t in q) or any((len(w) >= 2 or w == '깃') and w in raw for w in g):
            extra = [x for x in g if x not in q]
            if extra:
                out.append(extra)
    return out


def expand(q, text=''):
    out = list(q)
    for extra in syn_groups(q, text):
        out += [x for x in extra if x not in out]
    return out


def tokens(text):
    out = []
    for w in re.findall(r'[0-9A-Za-z가-힣_]{2,}', text):
        base = w
        for j in JOSA:
            if len(base) > len(j) + 1 and base.endswith(j):
                base = base[:-len(j)]
                break
        if on('norm'):
            for e in EOMI:
                if base.endswith(e) and len(base) - len(e) >= 2:
                    base = base[:-len(e)]
                    break
        if len(base) >= 2 and base not in STOP:
            out.append(base.lower())
    return list(dict.fromkeys(out))


DOC_RE = re.compile(r'^(CLAUDE\.md|\.claude/skills/[^/]+/SKILL\.md|docs/[^/]+\.md)$')
# 히스토리 문서: 인수인계·이력·기록 문서는 정본이 아니라 히스토리다(docs/슈퍼색인관리.md: 1차 결과에 섞지 않고 --history로만).
# 절이 많고 온갖 낱말이 들어 있어 아무 질문에나 걸려 정본 문서 자리를 빼앗았다(2026-10-21 측정).
HIST_DOC = re.compile(r'(진행상황|이력|히스토리|_기록)[^/]*\.md$')


def doc_chunks():
    """2차 정본 문서 색인(마찰 #1, 마야 10/15): origin/main의 CLAUDE.md·스킬·docs/*.md(역할노트·정책 포함)를 제목(헤딩) 단위로 쪼갠다.
    공정 카드·대화 기록에 안 잡히고 문서 안에만 있는 확정 결정(예: CTA 문구)을 찾기 위한 것. 실패하면 빈 목록(1차 검색은 영향 없음)."""
    import subprocess
    repo = str(Path(__file__).resolve().parents[2])
    git = ['git', '-c', 'core.quotepath=false', '-C', repo]
    try:
        names = subprocess.run(git + ['ls-tree', '-r', '--name-only', 'origin/main'], capture_output=True, text=True, encoding='utf-8', timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.split('\n')
    except Exception:  # noqa: BLE001
        return []
    out = []
    for n in (x for x in names if DOC_RE.match(x)):
        try:
            txt = subprocess.run(git + ['show', f'origin/main:{n}'], capture_output=True, text=True, encoding='utf-8', timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
        except Exception:  # noqa: BLE001
            continue
        head, buf = Path(n).stem, []
        for ln in txt.split('\n') + ['# ']:
            if ln.startswith('#'):
                body = ' '.join(buf)[:500]
                if body.strip():
                    out.append({'f': n, 'h': head, 'd': re.sub(r'\s+', ' ', body)})
                head, buf = ln.lstrip('# ').strip()[:80], []
            else:
                buf.append(ln)
    return out


def episode_states():
    """편마다 컨펌대장 마지막 사건과 이름(제목·태그·주제)을 모은다. shorts-lab이 없는 기기면 빈 값."""
    eps = {}
    try:
        lines = EP_LEDGER.read_text(encoding='utf-8').splitlines()
    except OSError:
        return eps
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        ep = r.get('episode') or ''
        at = r.get('response_at') or r.get('requested_at') or ''
        if not re.match(r'\d{4}-', at):
            at = ''  # version 칸('v1')은 시각이 아니다(첫 시험에서 'v1'이 최신으로 뽑힌 오류)
        if not ep or (ep in eps and eps[ep]['at'] >= at):
            continue
        eps[ep] = {'at': at, 'gate': r.get('gate', ''), 'st': r.get('status', ''), 'x': (r.get('response_text') or r.get('note') or '')[:160]}
    names, descs = {}, {}
    for d in (SHORTS / 'channels').glob('*/episodes/*'):
        meta = d / '06-publish' / 'meta.json'
        try:
            m = json.loads(meta.read_text(encoding='utf-8'))
            # 설명문까지 넣는다: 태그는 '사모예드', 사장님은 '사모에드'처럼 표기가 갈린다
            names[d.name] = ' '.join([m.get('title', '')] + list(m.get('hashtags') or []))
            descs[d.name] = (m.get('description') or '')[:300]
        except (OSError, ValueError):
            pass
    try:
        for r in json.loads((SHORTS / 'pilot-shorts2' / '대본대장.json').read_text(encoding='utf-8')).get('rows', []):
            if r.get('ep'):
                names[r['ep']] = names.get(r['ep'], '') + ' ' + (r.get('topic') or '')
    except (OSError, ValueError):
        pass
    for ep, v in eps.items():
        v['n'] = (ep.replace('-', ' ') + ' ' + names.get(ep, ''))[:600]
        v['d'] = descs.get(ep, '')
    return eps


GRANT_GENERIC = {'지원', '사업', '프로그램', 'program', 'startup', 'startups', '스타트업', '신청', '크레딧', 'cloud', '클라우드', '2026', '지원사업', 'for', '혜택', '참가', '확인'}


def grant_states():
    """지원사업 상태 정본(지원현황 DB, section=grant). 10/16 CF004: 구글 크레딧을 10/14에 신청했는데(G18 지원함) 1차 검색에 이 층이 없어
    탐이 순서 카드를 상태로 읽고 '미신청'으로 보고했다. 슈퍼사서 판정: 카드 문구만으론 부족, 1차에 지원현황 층을 넣는다."""
    try:
        import opsdb
        rs = opsdb.select('tasks', 'no,title,status,next_action,source_date,raw', where={'section': 'eq.grant'}, order='id.asc', limit=1000)
    except Exception:
        return []
    out = []
    for r in rs:
        raw = r.get('raw') or {}
        raw = json.loads(raw) if isinstance(raw, str) else raw
        out.append({'no': r['no'], 't': r['title'] or '', 'st': r['status'] or '', 'org': str(raw.get('org', '')), 'memo': str(raw.get('memo', ''))[:160],
                    'next': (r.get('next_action') or '')[:120], 'at': r.get('source_date') or ''})
    return out


def build():
    import opsdb
    cards, boss = [], []
    off = 0
    while True:
        rs = opsdb.select('tasks', 'id,owner,no,title,next_action,status,raw', where={'section': 'eq.step', 'id': f'gt.{off}'}, order='id.asc', limit=1000)
        if not rs:
            break
        cards += [r for r in rs if r['status'] != '숨김']
        off = rs[-1]['id']
    since = time.strftime('%Y-%m-%d', time.localtime(time.time() - 14 * 86400))
    off = 0
    while True:
        rs = opsdb.select('tasks', 'id,owner,raw', where={'section': 'eq.boss', 'source_date': f'gte.{since}', 'id': f'gt.{off}'}, order='id.asc', limit=1000)
        if not rs:
            break
        # 대체된 결정(raw.superseded_by)은 1차에서 뺀다(10/15 페이블 수명주기 설계 3절: 시간 창이 아니라 대체 표시로 내린다)
        boss += [r for r in rs if not (r.get('raw') or {}).get('superseded_by')]
        off = rs[-1]['id']
    logs = []
    for sec in LOG_SECTIONS:
        off = 0
        while True:
            rs = opsdb.select('tasks', 'id,owner,no,title,status,next_action,result,evidence,source_date', where={'section': f'eq.{sec}', 'id': f'gt.{off}'}, order='id.asc', limit=1000)
            if not rs:
                break
            logs += [dict(r, sec=sec) for r in rs]
            off = rs[-1]['id']
        # 이력 캐시가 끝없이 커지지 않게 구역마다 최근 2000행까지만 둔다(비티 10/15 지적)
        n_sec = sum(1 for r in logs if r['sec'] == sec)
        if n_sec > LOG_CAP:
            drop = n_sec - LOG_CAP
            logs = [r for r in logs if r['sec'] != sec or (drop := drop - 1) < 0]
    data = {'at': time.strftime('%F %T'),
            'logs': [{'s': r['sec'], 'p': r['owner'], 'no': r.get('no') or '', 't': (r.get('title') or '')[:300], 'd': ' '.join(str(r.get(k) or '') for k in ('next_action', 'result', 'evidence'))[:400], 'at': r.get('source_date') or ''} for r in logs],
            'docs': doc_chunks(),
            'eps': episode_states(),
            'grants': grant_states(),
            'cards': [{'p': r['owner'], 'no': r['no'], 't': r['title'], 'd': (r.get('next_action') or '')[:400], 'b': (r['raw'].get('boss') or '')[:400]} for r in cards],
            'boss': [{'at': r['raw'].get('at', ''), 'w': r['owner'], 'x': re.sub(r'\s+', ' ', r['raw'].get('text', ''))[:500]} for r in boss]}
    # 뒤에서 만드는 동안 훅이 반쯤 쓴 파일을 읽지 않게 임시 파일에 쓰고 바꿔 끼운다
    tmp = CACHE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, CACHE)
    print(f"캐시 갱신: 정본 문서 {len(data['docs'])}덩어리, 카드 {len(data['cards'])}개, 사장님 발화 {len(data['boss'])}건, 업무 기록 {len(data['logs'])}건 ({data['at']})")


def cache_age_h(at, now=None):
    """캐시 'at'(YYYY-MM-DD HH:MM:SS, 로컬 시각)이 몇 시간 전인지. 읽을 수 없으면 None."""
    try:
        return ((now if now is not None else time.time()) - time.mktime(time.strptime(at, '%Y-%m-%d %H:%M:%S'))) / 3600
    except (TypeError, ValueError):
        return None


def cache_note(res):
    """캐시가 NOTE_AFTER_H보다 오래됐으면 결과 맨 위에 붙일 한 줄, 아니면 ''."""
    age = res.get('cache_age_h') if res else None
    if age is None or age < NOTE_AFTER_H:
        return ''
    return f"· 캐시가 {age:.0f}시간 전({res.get('cache_at')}) 것입니다. 그 뒤 기록은 빠졌을 수 있습니다(새로 만들기: python scripts/ops/recall.py build)"


def refresh_in_background(res, lock=None):
    """캐시가 REFRESH_AFTER_MIN보다 오래됐으면 창 없이 뒤에서 build를 띄운다(훅을 기다리게 하지 않는다). 띄웠으면 True."""
    age = res.get('cache_age_h') if res else None
    if age is None or age * 60 < REFRESH_AFTER_MIN:
        return False
    lock = lock or CACHE.with_suffix('.building')
    try:
        if lock.exists() and time.time() - lock.stat().st_mtime < BUILD_LOCK_MIN * 60:
            return False
        lock.write_text(time.strftime('%F %T'), encoding='utf-8')
        exe = Path(sys.executable)
        pyw = exe.with_name('pythonw.exe')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
        subprocess.Popen([str(pyw if pyw.exists() else exe), str(Path(__file__).resolve()), 'build'], creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return True
    except Exception:  # noqa: BLE001
        return False


# 층 순서(같은 적중 비율일 때 앞선다): 상태 정본 → 공정 카드 → 사장님 말 → 정본 문서 → 업무 기록
LAYER_ORDER = ('eps', 'grants', 'cards', 'boss', 'docs', 'logs')


def merge_ranked(layers, total=10, doc_slot=3, ep_slot=4):
    """층마다 (적중 비율, 항목) 목록(층 안 순서 유지)을 받아 한 줄로 합친다.
    고정 층 순서로 이으면 정본 문서가 늘 7위 밑으로 밀리고, 흔한 낱말 하나로 걸린 편 상태·지원현황이 1위를 차지했다(2026-10-21 기준선).
    그래서 층 머리끼리 적중 비율로 고르고(같으면 LAYER_ORDER), 정본 문서가 있으면 가장 나은 문서 하나는 doc_slot위 안에 둔다."""
    heads = {k: list(v) for k, v in layers.items() if v}
    out = []
    while heads and len(out) < total:
        k = max(heads, key=lambda k: (heads[k][0][0], -LAYER_ORDER.index(k)))
        out.append((k, heads[k].pop(0)[1]))
        if not heads[k]:
            del heads[k]
    if doc_slot and layers.get('docs'):
        idx = next((i for i, (k, _) in enumerate(out) if k == 'docs'), None)
        if idx is None or idx >= doc_slot:
            item = out.pop(idx)[1] if idx is not None else layers['docs'][0][1]
            out.insert(min(doc_slot - 1, len(out)), ('docs', item))
            out = out[:total]
        # 문서는 2차 정본이고 절이 길어 낱말이 잘 걸린다. 상위 doc_slot 안에는 한 자리만 주고 나머지 문서 절은 그 뒤로 미룬다
        top, rest = out[:doc_slot], out[doc_slot:]
        doc_idx = [i for i, (k, _) in enumerate(top) if k == 'docs']
        if len(doc_idx) > 1:
            extra = [top[i] for i in doc_idx[1:]]
            top = [x for i, x in enumerate(top) if i not in doc_idx[1:]]
            fill = [x for x in rest if x[0] != 'docs'][:doc_slot - len(top)]
            rest = [x for x in rest if x not in fill]
            out = top + fill + extra + rest
    # 편을 물으면 컨펌대장 마지막 사건이 눈에 띄는 자리에 있어야 한다(2026-10-15 사모에드 사고). 맨 위는 아니어도 상위 ep_slot위 안에 가장 나은 편 하나를 둔다
    if ep_slot and layers.get('eps'):
        idx = next((i for i, (k, _) in enumerate(out) if k == 'eps'), None)
        if idx is None or idx >= ep_slot:
            item = out.pop(idx)[1] if idx is not None else layers['eps'][0][1]
            out.insert(min(ep_slot - 1, len(out)), ('eps', item))
            out = out[:total]
    return out


def query(text, n_cards=3, n_boss=3, n_logs=2, min_hits=2, history=False):
    try:
        data = json.loads(CACHE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    meta = {'cache_at': data.get('at', ''), 'cache_age_h': cache_age_h(data.get('at', ''))}
    q = tokens(text)
    qx = expand(q, text)
    if len(q) < 2:
        return dict(meta, cards=[], boss=[], logs=[], q=q, ranked=[])
    if on('syn'):
        # 같은 뜻 묶음은 질문 낱말과 합쳐 한 단위로 센다('휴식'과 '쉬게'가 둘 다 있어도 1점)
        units = []
        groups = [g for g in syn_table() if any(t in g for t in q) or any((len(w) >= 2 or w == '깃') and w in text.lower() for w in g)]
        for t in q:
            g = next((g for g in groups if t in g), None)
            u = sorted(set([t] + list(g))) if g else [t]
            if u not in units:
                units.append(u)
        units += [list(g) for g in groups if not any(t in g for t in q) and list(g) not in units]
    else:
        units = [[t] for t in q] + syn_groups(q, text)
    n_units = max(1, len(units))
    use_rank = on('rank')
    if use_rank:  # 합쳐서 자르므로 층마다 조금 넉넉히 후보를 둔다
        n_cards, n_docs = max(n_cards, 5), 3
    else:
        n_docs = 2
    drop_stale = on('stale') and not history

    def uh(blob):
        return sum(1 for u in units if any(t in blob for t in u))

    # 층 사이 비교용 적중 비율 = 맞힌 단위 수 / 전체 단위 수(IDF 무게는 시험에서 오히려 나빠져 쓰지 않는다, 2026-10-21 d1idf)
    card_blobs = [((c['p'] + ' ' if use_rank else '') + c['t'] + c['d'] + c['b']).lower() for c in data['cards']]
    # 문서는 절 단위로 쪼개 주제어(파일 이름)가 첫 절에만 남는다. 카드에 공정 이름을 넣듯 절마다 파일 이름 낱말을 붙인다(스위치 docname)
    doc_blobs = [((Path(d['f']).stem.replace('_', ' ') + ' ' if on('docname') else '') + d['h'] + ' ' + d['d']).lower() for d in data.get('docs', [])]

    def ratio(blob):
        # 제목 가중(BM25F식)도 시험했으나 상위3 적중은 그대로이고 혼입이 1건 늘어 쓰지 않는다(2026-10-21 d1w)
        return uh(blob) / n_units

    def score(blob, tw=1):
        b = blob.lower()
        return sum(tw for t in q if t in b)
    card_min = min_hits if on('syn') else max(min_hits, 3 if len(qx) > len(q) else min_hits)
    cs = []
    for c, blob in zip(data['cards'], card_blobs):
        if drop_stale and stale_mark(c['t']):
            continue  # 제목 앞 [대체됨]·[폐기] 카드는 현행 카드를 가린다(2026-10-21 기준선 측정). 이력은 --history로 본다
        s = sum(3 for t in qx if t in c['t'].lower()) + sum(1 for t in qx if t in c['d'].lower()) + sum(2 for t in qx if t in c['b'].lower())
        # 공정 이름(예: 핏-영상생성)도 주제 낱말이라 적중에 넣는다(카드 본문에는 주제어가 빠지는 일이 잦다)
        hits = uh(blob)
        if hits >= card_min:
            cs.append((s, ratio(blob), c))
    bs = []
    for b in data['boss']:
        bx = b['x'].lower()
        hits = sum(1 for t in q if t in bx)
        if hits >= max(min_hits, min(3, len(q) // 2)) and b['x'] != text.strip():
            bs.append((hits * 10 + (1 if b['at'] > '2026-10-05' else 0), ratio(bx) if use_rank else hits / max(1, len(q)), b))  # 다른 층과 같은 분모(단위 수)로 잰다
    ls = []
    for g in (data.get('logs', []) if history else []):
        blob = (g['t'] + ' ' + g['d']).lower()
        hits = uh(blob)
        if hits >= max(min_hits, 3):
            ls.append((hits * 3 + sum(3 for t in qx if t in g['t'].lower()), ratio(blob), g))
    ds = []
    for d, blob in zip(data.get('docs', []), doc_blobs):
        if drop_stale and stale_mark(d['h']):
            continue
        if not history and on('histdoc') and HIST_DOC.search(d['f']):
            continue
        hits = uh(blob)
        if hits >= max(min_hits, 3):
            ds.append((hits * 3 + sum(3 for t in qx if t in d['h'].lower()), ratio(blob), d))
    # 편 상태: 질문 낱말이 편 이름에 있고 그 낱말이 편 3개 이하에만 나오면(흔한 말 제외) 그 편으로 본다
    eps = data.get('eps', {})
    ep_hit, ep_words, ep_n = [], set(), {}
    for t in q:
        if len(t) < 2:
            continue
        m = [e for e, v in eps.items() if t in v.get('n', '').lower()]
        # 설명문은 흔한 낱말('공간'·'기준'·'사용')이 걸려 엉뚱한 편이 붙었다(10/16). 설명문으로는 4자 이상이고 한 편에만 있는 낱말만 인정한다(예: 사모에드)
        if not m and len(t) >= 4:
            m = [e for e, v in eps.items() if t in v.get('d', '').lower()]
            m = m if len(m) == 1 else []
        if 0 < len(m) <= 3:
            ep_words.add(t)
            ep_hit += [e for e in m if e not in ep_hit]
            for e in m:
                ep_n[e] = ep_n.get(e, 0) + 1
    if ep_hit:
        # 같은 편을 '보류' 등으로 적은 손글씨 카드는 1차에서 뺀다(정본은 편 사건 기록)
        cs = [x for x in cs if not (EP_HOLD.search(x[2]['t']) and any(w in x[2]['t'].lower() for w in ep_words))]
    # 지원사업 상태: 회사·사업 이름 낱말(흔한 말 제외)이 사업명·기관에 있으면 지원현황 DB 행을 1차로 보인다(10/16 CF004)
    gs = []
    for g in data.get('grants', []):
        blob = (g['t'] + ' ' + g['org']).lower()
        hits = sum(1 for t in qx if len(t) >= 2 and t not in GRANT_GENERIC and t in blob)
        if hits:
            # 이름 낱말로 걸렸으면 비교용 비율은 다른 층처럼 단위 수로 잰다(사업명·기관·메모 전체, 흔한 말도 이때는 센다)
            gs.append((hits, ratio((blob + ' ' + g['memo'] + ' ' + g['st']).lower()) if use_rank else min(1.0, hits / n_units), g))
    for lst in (gs, ds, ls, cs):
        # 합쳐 고를 때는 서로 다른 낱말을 몇 개 맞혔나(적중 비율)를 먼저, 제목 가중 점수를 다음으로 본다(옛 방식은 점수만)
        lst.sort(key=(lambda x: (-x[1], -x[0])) if use_rank else (lambda x: -x[0]))
    bs.sort(key=lambda x: (-x[0], x[2]['at']))
    ep_rows = [(ep_n.get(e, 0) / n_units, dict(eps[e], ep=e)) for e in ep_hit[:3]]
    layers = {'eps': ep_rows, 'grants': [(cv, g) for _, cv, g in gs[:2]], 'cards': [(cv, c) for _, cv, c in cs[:n_cards]],
              'boss': [(cv, b) for _, cv, b in bs[:n_boss]], 'docs': [(cv, d) for _, cv, d in ds[:n_docs]], 'logs': [(cv, g) for _, cv, g in ls[:n_logs]]}
    if use_rank:
        ranked = merge_ranked(layers)
    else:  # 옛 방식: 층 고정 순서로 잇기
        ranked = [(k, x) for k in LAYER_ORDER for _, x in layers[k]]
    kept = {k: [x for kk, x in ranked if kk == k] for k in LAYER_ORDER}
    return dict(meta, q=q, ranked=ranked, **kept)


def _embed(text):
    """질의 임베딩(로컬 bge-m3). ollama가 꺼져 있으면 None → kb_search는 trgm+주입만 쓴다. 절대 예외를 올리지 않는다."""
    try:
        import json as _json
        import urllib.request
        req = urllib.request.Request('http://127.0.0.1:11434/api/embeddings',
                                     data=_json.dumps({'model': 'bge-m3', 'prompt': text[:3000]}).encode(),
                                     headers={'Content-Type': 'application/json'})
        v = _json.loads(urllib.request.urlopen(req, timeout=3).read())['embedding']
        return v + [0.0] * (1024 - len(v))
    except Exception:  # noqa: BLE001
        return None


KB_ERR = ''  # 마지막 kb_layer 호출의 실패 원인 한 줄(성공이면 '')


def kb_error_line(e):
    """예외에서 원인 한 줄을 만든다. 오류 본문(질의·값이 섞일 수 있다)은 옮기지 않고 종류·HTTP 상태·코드만 쓴다."""
    msg = str(e)
    parts = [type(e).__name__]
    m = re.search(r'HTTP (\d{3})', msg)
    if m:
        parts.append(f'HTTP {m.group(1)}')
    m = re.search(r'\bPGRST\d{3}\b', msg)
    if m:
        parts.append(m.group(0))
    if 'PGRST202' in msg or (m is None and 'HTTP 404' in msg):
        parts.append('운영 DB에 kb_search 함수가 없음(미적용)')
    elif isinstance(e, SystemExit):
        parts.append('운영 DB 설정 없음')
    return ' '.join(parts)


def kb_layer(text, match_count=8):
    """1차 검색에 지식DB 층(자원·정본·문서임베딩)을 추가로 읽는다(kb_search RPC). 기존 캐시 기반 검색은 그대로 두고 덧붙이기만 한다.
    실패해도 1차 검색은 영향 없이 빈 목록을 돌려주되, 원인은 KB_ERR에 남겨 결과 끝에 보인다(2026-10-21: 404를 조용히 삼켜 매번 0건인 줄 몰랐다)."""
    global KB_ERR
    KB_ERR = ''
    try:
        import opsdb
        rows = opsdb.rpc('kb_search', {'q': text, 'q_embedding': _embed(text), 'match_count': match_count})
        return rows if isinstance(rows, list) else []
    except (Exception, SystemExit) as e:  # noqa: BLE001  opsdb는 설정이 없으면 SystemExit을 던진다(훅을 끝내면 안 된다)
        KB_ERR = kb_error_line(e)
        return []


def kb_error_note():
    return f'· 지식DB 층 오류: {KB_ERR}' if KB_ERR else ''


# ---------- 출력 가림(이메일·전화·키 형식). 캐시 원본은 바꾸지 않고 사람·에이전트 눈에 보이는 줄만 가린다 ----------
try:
    from check_public_leaks import EMAIL as _EMAIL, KEYS as _KEYS, email_allowed as _email_allowed
except Exception:  # noqa: BLE001
    _EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
    _KEYS = {}

    def _email_allowed(addr):
        return addr.lower().rsplit('@', 1)[1].endswith(('simplifier.co.kr', 'example.com'))
_IMG = re.compile(r'\.(png|jpe?g|webp|gif|svg|avif)$', re.I)
_PHONE = (re.compile(r'(?<![\d-])(01[016789])[- .]?\d{3,4}[- .]?\d{4}(?![\d-])'),
          re.compile(r'(?<![\d-])(02|0[3-6][1-5]|070)[- .]\d{3,4}[- .]\d{4}(?![\d-])'))
_MORE_KEYS = (re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'), re.compile(r'\bsb_secret_[A-Za-z0-9_-]{20,}'))


def _mask_email(m):
    addr = m.group(0)
    if _IMG.search(addr) or _email_allowed(addr):  # 이미지 파일명(logo@2x.png)·회사 공용 주소는 그대로
        return addr
    local, domain = addr.split('@', 1)
    return f'{local[0]}***@{domain}'


def mask_pii(s):
    """보이는 줄에서 이메일은 a***@도메인, 전화번호는 앞자리만, 키 형식은 [키 가림]으로 바꾼다."""
    if not s or not on('mask'):
        return s
    s = _EMAIL.sub(_mask_email, s)
    for rx in _PHONE:
        s = rx.sub(lambda m: f'{m.group(1)}-****-****', s)
    for rx in list(_KEYS.values()) + list(_MORE_KEYS):
        s = rx.sub('[키 가림]', s)
    return s


def render_kb(rows):
    lines = []
    for r in rows:
        if r.get('rank') == 0:  # 결정적 주입(자원·정본): 0순위 권위
            fresh = f" (확인 {str(r.get('last_verified'))[:10]})" if r.get('last_verified') else ''
            state = f" [{r.get('fact_state')}]" if r.get('fact_state') else ''
            lines.append(f"· 지식DB 0순위[{r.get('src')}:{r.get('ref_id')}] {r.get('title')}: {(r.get('content') or '')[:180]}{state}{fresh}")
        else:
            lines.append(f"· 지식DB 문서[{r.get('ref_id')}] {r.get('title')} ({r.get('dt')}): {(r.get('content') or '')[:120]}")
    return [mask_pii(x) for x in lines]


def render_item(kind, x):
    """층 하나의 항목을 한 줄로(가리기 전)."""
    if kind == 'eps':
        at = x['at']
        if at.endswith('Z'):  # 컨펌대장은 UTC로 적는다, 사람 눈엔 한국 시각
            at = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.mktime(time.strptime(at[:16], '%Y-%m-%dT%H:%M')) - time.timezone + 9 * 3600)) + ' KST'
        return f"· 편 상태(정본=컨펌대장 마지막 사건) [{x['ep']}] {at[:20]} {x['gate']} {x['st']}: {x['x'][:120]}"
    if kind == 'grants':
        return (f"· 지원현황(정본=지원현황 DB) [{x['no']}] {x['t'][:60]} — 상태 {x['st']} ({x['at']})" + (f" / {x['memo'][:100]}" if x['memo'] else '')
                + (f" / 다음: {x['next'][:80]}" if x['next'] else ''))
    if kind == 'cards':
        return f"· 공정 카드 [{x['p']}#{x['no']}] {x['t'][:60]}" + (f" ★사장님: {x['b'][:160]}" if x['b'] else '')
    if kind == 'boss':
        return f"· 사장님이 {x['at'][:16]}에 한 말: {x['x'][:200]}"
    if kind == 'docs':
        return f"· 정본 문서 {x['f']} > {x['h'][:50]}: {x['d'][:140]}"
    return f"· 업무 기록({x['s']}) [{x['p']}{('#' + x['no']) if x['no'] else ''}] {x['t'][:120]}"


def render(res):
    """결과 줄 목록. 캐시가 오래됐으면 맨 위에 알림, 순서는 query의 ranked(없으면 옛 층 순서)."""
    lines = []
    note = cache_note(res)
    if note:
        lines.append(note)
    ranked = res.get('ranked')
    if ranked is None:
        ranked = [(k, x) for k in LAYER_ORDER for x in res.get(k, [])]
    lines += [mask_pii(render_item(k, x)) for k, x in ranked]
    return lines


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if a[:1] == ['build']:
        try:
            return build()
        finally:
            try:
                CACHE.with_suffix('.building').unlink()
            except OSError:
                pass
    if a[:1] == ['--hook']:
        try:
            prompt = json.loads(sys.stdin.buffer.read().decode('utf-8')).get('prompt', '')
        except Exception:
            return
        if not prompt or len(prompt) < 8 or prompt.lstrip().startswith(('<', '/')) or 'SYSTEM NOTIFICATION' in prompt[:200]:
            return
        res = query(prompt)
        refresh_in_background(res)
        kb = render_kb(kb_layer(prompt))
        has_cache = bool(res and res.get('ranked'))
        if has_cache or kb:
            print('[기억 도우미] 이 주제로 프로세스표(수파베이스)·사장님 말 원장·정본 문서·지식DB에 이미 있는 기억입니다. 답하기 전에 이것과 모순되지 않게 하세요:')
            if has_cache:
                print('\n'.join(render(res)))
            if kb:
                print('\n'.join(kb))
            if kb_error_note():
                print(kb_error_note())
        return
    hist = '--history' in a
    text = ' '.join(x for x in a if x != '--history')
    res = query(text, history=hist)
    if res is None:
        sys.exit('캐시가 없습니다: python scripts/ops/recall.py build')
    refresh_in_background(res)
    out = render(res) + render_kb(kb_layer(text))
    if kb_error_note():
        out.append(kb_error_note())
    print('\n'.join(out) if out else '(관련 기억 없음)')


if __name__ == '__main__':
    main()
