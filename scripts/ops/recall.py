# -*- coding: utf-8 -*-
"""기억 도우미(G5, 2026-10-05 탐, 사장님: "새 세션이 되면 잊어버리고 사장이 이상한 얘기하는 사람처럼 만든다. 해당 대화를 할 때는 프로세스표에서 기억을 찾아서(수파베이스) 답해 주길"):
사장님이 말을 걸면 답하기 전에 ① 공정 단계 카드(DB section=step) ② 사장님 말 원장(section=boss)에서 같은 주제의 기억을 찾아 짧게 보여 준다.
속도: 매번 DB를 부르면 1초 이상 걸리므로 시간당 한 번 로컬 캐시(C:/work/_ops/recall_cache.json)로 내려받고, 조회는 캐시만 읽는다(수십 ms).
사용:
  python scripts/ops/recall.py build                      캐시 갱신(카드 전체 + 최근 14일 사장님 발화)
  python scripts/ops/recall.py "사장님이 한 말 그대로"      관련 카드·발화 상위 몇 개
  python scripts/ops/recall.py --hook < prompt.json        훅용: stdin JSON의 prompt로 찾아 관련 있을 때만 출력(없으면 조용히 종료)"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
CACHE = Path(r'C:\work\_ops\recall_cache.json')
JOSA = ('에서는', '으로는', '이라는', '에서', '으로', '에게', '한테', '까지', '부터', '처럼', '보다', '하고', '이나', '이랑', '은', '는', '이', '가', '을', '를', '의', '에', '로', '와', '과', '도', '만', '요', '죠', '야', '나')
STOP = {'그냥', '이제', '그리고', '그런데', '그래서', '하는', '있는', '없는', '있어', '있다', '해서', '해주', '주세', '것이', '거를', '이거', '저거', '우리', '탐이', '사장', '사장님', '같은', '대한', '위해', '때문', '아니', '정말', '지금', '계속', '다시', '이런', '그런', '어떤', '어떻', '하면', '해요', '하세요', '합니다', '입니다', '있나', '있는지', '되었', '되어', '됩니다', '않고', '않는', '말고', '그게', '이게', '뭐가', '무엇', '어디', '언제', '얼마', '몇개'}


def tokens(text):
    out = []
    for w in re.findall(r'[0-9A-Za-z가-힣_]{2,}', text):
        base = w
        for j in JOSA:
            if len(base) > len(j) + 1 and base.endswith(j):
                base = base[:-len(j)]
                break
        if len(base) >= 2 and base not in STOP:
            out.append(base.lower())
    return list(dict.fromkeys(out))


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
        boss += rs
        off = rs[-1]['id']
    data = {'at': time.strftime('%F %T'),
            'cards': [{'p': r['owner'], 'no': r['no'], 't': r['title'], 'd': (r.get('next_action') or '')[:400], 'b': (r['raw'].get('boss') or '')[:400]} for r in cards],
            'boss': [{'at': r['raw'].get('at', ''), 'w': r['owner'], 'x': re.sub(r'\s+', ' ', r['raw'].get('text', ''))[:500]} for r in boss]}
    CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    print(f"캐시 갱신: 카드 {len(data['cards'])}개, 사장님 발화 {len(data['boss'])}건 ({data['at']})")


def query(text, n_cards=3, n_boss=3, min_hits=2):
    try:
        data = json.loads(CACHE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    q = tokens(text)
    if len(q) < 2:
        return {'cards': [], 'boss': [], 'q': q}
    def score(blob, tw=1):
        b = blob.lower()
        return sum(tw for t in q if t in b)
    cs = []
    for c in data['cards']:
        s = score(c['t'], 3) + score(c['d'], 1) + score(c['b'], 2)
        hits = sum(1 for t in q if t in (c['t'] + c['d'] + c['b']).lower())
        if hits >= min_hits:
            cs.append((s, c))
    bs = []
    for b in data['boss']:
        hits = sum(1 for t in q if t in b['x'].lower())
        if hits >= max(min_hits, min(3, len(q) // 2)) and b['x'] != text.strip():
            bs.append((hits * 10 + (1 if b['at'] > '2026-10-05' else 0), b))
    cs.sort(key=lambda x: -x[0])
    bs.sort(key=lambda x: (-x[0], x[1]['at']))
    return {'cards': [c for _, c in cs[:n_cards]], 'boss': [b for _, b in bs[:n_boss]], 'q': q}


def render(res):
    lines = []
    for c in res['cards']:
        lines.append(f"· 공정 카드 [{c['p']}#{c['no']}] {c['t'][:60]}" + (f" ★사장님: {c['b'][:160]}" if c['b'] else ''))
    for b in res['boss']:
        lines.append(f"· 사장님이 {b['at'][:16]}에 한 말: {b['x'][:200]}")
    return lines


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if a[:1] == ['build']:
        return build()
    if a[:1] == ['--hook']:
        try:
            prompt = json.loads(sys.stdin.buffer.read().decode('utf-8')).get('prompt', '')
        except Exception:
            return
        if not prompt or len(prompt) < 8 or prompt.lstrip().startswith(('<', '/')) or 'SYSTEM NOTIFICATION' in prompt[:200]:
            return
        res = query(prompt)
        if res and (res['cards'] or res['boss']):
            print('[기억 도우미] 이 주제로 프로세스표(수파베이스)와 사장님 말 원장에 이미 있는 기억입니다. 답하기 전에 이것과 모순되지 않게 하세요:')
            print('\n'.join(render(res)))
        return
    text = ' '.join(a)
    res = query(text)
    if res is None:
        sys.exit('캐시가 없습니다: python scripts/ops/recall.py build')
    out = render(res)
    print('\n'.join(out) if out else '(관련 기억 없음)')


if __name__ == '__main__':
    main()
