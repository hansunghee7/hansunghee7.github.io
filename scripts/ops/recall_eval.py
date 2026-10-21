#!/usr/bin/env python3
"""기억 검색 시험 도구(에이전트 기억 검색 2주 시험 0단계 기준선, 공정 카드 탐-슈퍼글로벌 #102·#103).

질문 세트(JSON)를 읽어 recall.py와 같은 경로(recall.query + recall.kb_layer, 훅과 같은 기본값)로 결과를 얻고 채점한다.
  - 적중: 정답 지정(공정 카드 '공정#번호', 문서 경로, '지원현황#번호' 등)이 상위 3개 안에 있는가
  - 혼입: 대체·폐기 표시가 된 항목이 상위 5개에 섞였는가
      · 공정 카드 상태 '숨김'(proc.py retire가 붙인다), 결정 raw.superseded_by(recall.build가 빼는 표시)
      · 카드 제목 맨 앞 [..] 안의 낡음 표시(confusion_scan.STALE과 같은 말: 대체됨·폐기·무효 등)
      · 지식DB 행 fact_state가 current가 아닌 것
      · 질문마다 지정한 must_not(내용상 대체된 카드)
  - 비공개 노출: 상위 5개 본문에 이메일(허용 도메인 제외)·전화번호·주민번호·키 형식 문자열이 있는가(값은 저장하지 않고 가린다)
  - 소요 시간: query와 kb_layer 각각

순위는 recall.render와 hook 출력 순서 그대로다: 편 상태 → 지원현황 → 공정 카드 → 사장님 말 → 정본 문서 → (업무 기록) → 지식DB.

읽기만 한다. 쓰기는 출력 폴더(기본 C:/work/_ops/recall_eval/)뿐이다. 캐시를 새로 만들지 않는다(recall.py build는 별도).
운영 DB는 숨김 카드·대체 결정 목록을 읽을 때만 select로 읽는다(--offline이면 읽지 않고 캐시·제목 표시만 쓴다).

사용:
  python scripts/ops/recall_eval.py --questions C:/work/_ops/recall_eval/questions_v1.json --label baseline
  python scripts/ops/recall_eval.py ... --no-kb      지식DB 층(RPC·임베딩) 없이
  python scripts/ops/recall_eval.py ... --offline    운영 DB를 읽지 않음(숨김·대체 목록 없이 채점)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

OUT_DIR = Path(r'C:\work\_ops\recall_eval')
TOP_HIT = 3
TOP_MIX = 5

# confusion_scan.STALE과 같은 말(정본을 하나로 두려고 가져다 쓰고, 없으면 같은 정규식)
try:
    from confusion_scan import STALE
except Exception:  # noqa: BLE001
    STALE = re.compile(r"(폐기|롤백|정정|대체됨|옛 방식|옛 규칙|이전 규칙|무효|더 이상 쓰지|부분 폐기|→ 정본)")
BRACKET = re.compile(r'^\s*\[([^\]]{0,200})\]')

# 비공개 노출 판정: 공개 저장소 검사(check_public_leaks)의 이메일·키 정규식을 그대로 쓰고, 개인정보 형식 몇 개를 더한다
try:
    from check_public_leaks import EMAIL, KEYS, email_allowed
except Exception:  # noqa: BLE001
    EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    KEYS = {}

    def email_allowed(addr):
        return addr.lower().rsplit('@', 1)[1].endswith(('simplifier.co.kr', 'anthropic.com', 'example.com'))
EXTRA_PII = {
    '휴대전화': re.compile(r'(?<!\d)01[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)'),
    '주민번호': re.compile(r'(?<!\d)\d{6}-[1-4]\d{6}(?!\d)'),
    'JWT': re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    '수파베이스 비밀키': re.compile(r'\bsb_secret_[A-Za-z0-9_-]{20,}'),
}


# ---------- 결과 모으기 ----------

def rank_items(res, kb_rows):
    """recall.query 결과와 kb_layer 행을 출력 순서대로 한 줄 목록으로 편다. 항목: kind, id, text."""
    res = res or {}
    items = []
    for e in res.get('eps', []):
        items.append({'kind': 'ep', 'id': f"편#{e.get('ep', '')}", 'text': f"{e.get('gate', '')} {e.get('st', '')} {e.get('x', '')}"})
    for g in res.get('grants', []):
        items.append({'kind': 'grant', 'id': f"지원현황#{g.get('no', '')}", 'text': f"{g.get('t', '')} {g.get('st', '')} {g.get('memo', '')} {g.get('next', '')}"})
    for c in res.get('cards', []):
        items.append({'kind': 'card', 'id': f"{c.get('p', '')}#{c.get('no', '')}", 'text': f"{c.get('t', '')} {c.get('d', '')} {c.get('b', '')}"})
    for b in res.get('boss', []):
        items.append({'kind': 'boss', 'id': f"사장님말#{b.get('at', '')}", 'text': b.get('x', ''), 'at': b.get('at', '')})
    for d in res.get('docs', []):
        items.append({'kind': 'doc', 'id': d.get('f', ''), 'text': f"{d.get('h', '')} {d.get('d', '')}", 'head': d.get('h', '')})
    for g in res.get('logs', []):
        items.append({'kind': 'log', 'id': f"기록:{g.get('p', '')}#{g.get('no', '')}", 'text': f"{g.get('t', '')} {g.get('d', '')}"})
    for r in kb_rows or []:
        items.append({'kind': 'kb', 'id': f"kb:{r.get('src', '')}:{r.get('ref_id', '')}", 'text': f"{r.get('title', '')} {r.get('content', '')}",
                      'fact_state': r.get('fact_state')})
    return items


def collect(text, use_kb=True, history=False, recall_mod=None):
    """recall과 같은 경로로 한 질문의 결과를 얻는다. 돌려주는 값: (항목 목록, 시간 dict, 오류 문자열)."""
    if recall_mod is None:
        import recall as recall_mod
    t0 = time.perf_counter()
    res = recall_mod.query(text, history=history)
    t1 = time.perf_counter()
    kb = recall_mod.kb_layer(text) if use_kb else []
    t2 = time.perf_counter()
    err = '' if res is not None else '캐시 없음(recall.py build 필요)'
    return rank_items(res, kb), {'query_ms': round((t1 - t0) * 1000, 1), 'kb_ms': round((t2 - t1) * 1000, 1), 'total_ms': round((t2 - t0) * 1000, 1)}, err


# ---------- 낡음·대체 표시 ----------

def norm_text(s):
    return re.sub(r'\s+', ' ', s or '')


def load_flags(offline=False):
    """운영 DB에서 숨김 카드 id와 대체된 결정(at)을 읽는다(select만). 실패하면 ok=False로 표시하고 빈 목록."""
    flags = {'ok': False, 'hidden_cards': set(), 'superseded_boss': set(), 'note': ''}
    if offline:
        flags['note'] = '--offline: 운영 DB 표시를 읽지 않음'
        return flags
    try:
        import opsdb
        rows, off = [], 0
        while True:
            rs = opsdb.select('tasks', 'id,owner,no,status', where={'section': 'eq.step', 'id': f'gt.{off}'}, order='id.asc', limit=1000)
            if not rs:
                break
            rows += rs
            off = rs[-1]['id']
        active = {f"{r['owner']}#{r['no']}" for r in rows if r.get('status') != '숨김'}
        # 같은 이름이 살아 있는 카드에도 있으면 숨김으로 치지 않는다(오판 방지)
        flags['hidden_cards'] = {f"{r['owner']}#{r['no']}" for r in rows if r.get('status') == '숨김'} - active
        bs = opsdb.select('tasks', 'id,raw', where={'section': 'eq.boss', 'raw->>superseded_by': 'not.is.null'}, limit=5000)
        flags['superseded_boss'] = {str((r.get('raw') or {}).get('at', '')) for r in bs if (r.get('raw') or {}).get('at')}
        flags['ok'] = True
        flags['note'] = f"숨김 카드 {len(flags['hidden_cards'])}개, 대체 결정 {len(flags['superseded_boss'])}건 (운영 DB 읽기)"
    except Exception as e:  # noqa: BLE001
        flags['note'] = f'운영 DB 표시 읽기 실패: {type(e).__name__}'
    return flags


def item_flags(item, flags, must_not=()):
    """항목에 붙은 낡음·대체 표시 이유 목록(없으면 빈 목록)."""
    why = []
    iid = item['id']
    if item['kind'] == 'card':
        if iid in flags.get('hidden_cards', ()):
            why.append('카드 상태 숨김')
        m = BRACKET.match(item['text'])
        if m and STALE.search(m.group(1)):
            why.append(f"제목 앞 표시 [{m.group(1)[:30]}]")
    if item['kind'] == 'boss' and item.get('at') and item['at'] in flags.get('superseded_boss', ()):
        why.append('결정 superseded_by')
    if item['kind'] == 'kb' and item.get('fact_state') and item['fact_state'] != 'current':
        why.append(f"지식DB fact_state={item['fact_state']}")
    if iid in must_not:
        why.append('질문 지정 대체 항목(must_not)')
    return why


# ---------- 비공개 노출 ----------

def leak_hits(text):
    """본문에서 비공개 형식 이름 목록을 돌려준다(값은 돌려주지 않는다)."""
    out = []
    for addr in EMAIL.findall(text or ''):
        if not email_allowed(addr):
            out.append('이메일')
            break
    for name, rx in list(KEYS.items()) + list(EXTRA_PII.items()):
        if rx.search(text or ''):
            out.append(name)
    return out


def mask_text(text):
    """결과 파일에 남길 때 비공개 형식 문자열을 가린다."""
    s = text or ''
    s = EMAIL.sub(lambda m: m.group(0) if email_allowed(m.group(0)) else '[이메일 가림]', s)
    for name, rx in list(KEYS.items()) + list(EXTRA_PII.items()):
        s = rx.sub(f'[{name} 가림]', s)
    return s


# ---------- 채점 ----------

def matches(item, expected):
    iid = item['id']
    for e in expected:
        if iid == e:
            return True
        if item['kind'] == 'kb' and e and e in iid:
            return True
    return False


def score_question(q, items, flags, top_hit=TOP_HIT, top_mix=TOP_MIX):
    expected = q.get('expected') or []
    must_not = set(q.get('must_not') or [])
    rank = next((i + 1 for i, it in enumerate(items) if matches(it, expected)), None)
    hit = bool(expected) and rank is not None and rank <= top_hit
    mixed, leaks = [], []
    for i, it in enumerate(items[:top_mix]):
        why = item_flags(it, flags, must_not)
        if why:
            mixed.append({'rank': i + 1, 'id': it['id'], 'why': why})
        lk = leak_hits(it['text'])
        if lk:
            leaks.append({'rank': i + 1, 'id': it['id'], 'kinds': lk})
    passed = (hit if expected else True) and not leaks
    return {'id': q.get('id'), 'category': q.get('category'), 'question': q.get('question'), 'expected': expected,
            'rank': rank, 'hit_top3': hit, 'mixed_top5': mixed, 'leaks_top5': leaks, 'passed': passed,
            'top5': [{'rank': i + 1, 'kind': it['kind'], 'id': it['id'], 'text': mask_text(norm_text(it['text']))[:160]} for i, it in enumerate(items[:top_mix])],
            'n_items': len(items)}


def summarize(results):
    n = len(results)
    with_exp = [r for r in results if r['expected']]
    times = sorted(r.get('timing', {}).get('total_ms', 0) for r in results)
    by_cat = {}
    for r in results:
        c = by_cat.setdefault(r['category'] or '-', {'n': 0, 'passed': 0})
        c['n'] += 1
        c['passed'] += 1 if r['passed'] else 0
    return {'n': n, 'passed': sum(1 for r in results if r['passed']),
            'hit_top3': sum(1 for r in with_exp if r['hit_top3']), 'n_with_expected': len(with_exp),
            'found_anywhere': sum(1 for r in with_exp if r['rank'] is not None),
            'mixed_items': sum(len(r['mixed_top5']) for r in results),
            'mixed_questions': sum(1 for r in results if r['mixed_top5']),
            'leak_questions': sum(1 for r in results if r['leaks_top5']),
            'median_ms': times[len(times) // 2] if times else 0, 'max_ms': times[-1] if times else 0,
            'by_category': by_cat}


def render_md(meta, summ, results):
    L = [f"# 기억 검색 시험 결과: {meta['label']} ({meta['date']})", '',
         f"- 질문 세트: {meta['questions']} ({summ['n']}개), 캐시 시각 {meta['cache_at']}, 지식DB 층 {'켬' if meta['use_kb'] else '끔'}",
         f"- 낡음 표시 출처: {meta['flags_note']}",
         f"- **통과 {summ['passed']}/{summ['n']}** (정답 지정 질문은 상위 3개 적중, 비공개 질문은 노출 없음)",
         f"- 상위 3개 적중 {summ['hit_top3']}/{summ['n_with_expected']}, 어디든 나옴 {summ['found_anywhere']}/{summ['n_with_expected']}",
         f"- **혼입 {summ['mixed_items']}건**(질문 {summ['mixed_questions']}개), 비공개 노출 질문 {summ['leak_questions']}개",
         f"- 소요 시간 중앙값 {summ['median_ms']}ms, 최대 {summ['max_ms']}ms",
         f"- 목표(탐-슈퍼글로벌 #103): 상위 3개 적중 18개 이상, 낡은 답 혼입 1건 이하", '', '## 범주별', '']
    for c, v in summ['by_category'].items():
        L.append(f"- {c}: {v['passed']}/{v['n']}")
    L += ['', '## 질문별', '']
    for r in results:
        mark = '통과' if r['passed'] else '실패'
        L.append(f"### {r['id']} [{r['category']}] {mark}")
        L.append(f"- 질문: {r['question']}")
        L.append(f"- 정답: {', '.join(r['expected']) or '(없음: 노출 시험)'} / 순위: {r['rank'] or '없음'} / 결과 {r['n_items']}개 / {r.get('timing', {}).get('total_ms', '?')}ms")
        if r['mixed_top5']:
            L.append('- 혼입: ' + '; '.join(f"{m['rank']}위 {m['id']}({', '.join(m['why'])})" for m in r['mixed_top5']))
        if r['leaks_top5']:
            L.append('- 비공개 형식: ' + '; '.join(f"{x['rank']}위 {x['id']}({', '.join(x['kinds'])})" for x in r['leaks_top5']))
        if r.get('error'):
            L.append(f"- 오류: {r['error']}")
        if r.get('reason'):
            L.append(f"- 실패 원인: {r['reason']}")
        L.append('- 상위: ' + (' | '.join(f"{t['rank']}.{t['id']}" for t in r['top5']) or '(결과 없음)'))
        L.append('')
    return '\n'.join(L)


def apply_reasons(results, reasons):
    for r in results:
        if not r['passed'] and reasons.get(r['id']):
            r['reason'] = reasons[r['id']]
    return results


def annotate(result_json, reasons_json):
    data = json.loads(result_json.read_text(encoding='utf-8'))
    reasons = json.loads(reasons_json.read_text(encoding='utf-8')) if reasons_json else {}
    apply_reasons(data['results'], reasons)
    result_json.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    result_json.with_suffix('.md').write_text(render_md(data['meta'], data['summary'], data['results']), encoding='utf-8')
    print(f'원인 {sum(1 for r in data["results"] if r.get("reason"))}건 반영: {result_json.with_suffix(".md")}')
    return 0


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='기억 검색 시험(읽기 전용)')
    ap.add_argument('--questions', default=str(OUT_DIR / 'questions_v1.json'))
    ap.add_argument('--label', default='run')
    ap.add_argument('--out-dir', default=str(OUT_DIR))
    ap.add_argument('--no-kb', action='store_true')
    ap.add_argument('--history', action='store_true')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--annotate', help='저장된 결과 json에 실패 원인(--reasons)을 붙여 md만 다시 쓴다(검색 재실행 없음)')
    ap.add_argument('--reasons', help='{"질문id": "실패 원인 한 줄"} json')
    a = ap.parse_args(argv)
    if a.annotate:
        return annotate(Path(a.annotate), Path(a.reasons) if a.reasons else None)
    if not re.fullmatch(r'[0-9A-Za-z가-힣_-]{1,40}', a.label):
        sys.exit('라벨은 글자·숫자·_- 40자 이내')
    qs = json.loads(Path(a.questions).read_text(encoding='utf-8'))
    questions = qs['questions'] if isinstance(qs, dict) else qs
    import recall
    try:
        cache_at = json.loads(recall.CACHE.read_text(encoding='utf-8')).get('at', '?')
    except (OSError, ValueError):
        cache_at = '없음'
    flags = load_flags(offline=a.offline)
    results = []
    for q in questions:
        items, timing, err = collect(q['question'], use_kb=not a.no_kb, history=a.history, recall_mod=recall)
        r = score_question(q, items, flags)
        r['timing'] = timing
        if err:
            r['error'] = err
        results.append(r)
        print(f"{q.get('id')}: {'통과' if r['passed'] else '실패'} 순위={r['rank']} 혼입={len(r['mixed_top5'])} {timing['total_ms']}ms")
    summ = summarize(results)
    date = time.strftime('%Y-%m-%d')
    meta = {'label': a.label, 'date': date, 'at': time.strftime('%F %T'), 'questions': a.questions, 'cache_at': cache_at,
            'use_kb': not a.no_kb, 'history': a.history, 'flags_ok': flags['ok'], 'flags_note': flags['note'], 'top_hit': TOP_HIT, 'top_mix': TOP_MIX}
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = out / f'{date}_{a.label}'
    base.with_suffix('.json').write_text(json.dumps({'meta': meta, 'summary': summ, 'results': results}, ensure_ascii=False, indent=1), encoding='utf-8')
    base.with_suffix('.md').write_text(render_md(meta, summ, results), encoding='utf-8')
    print(f"통과 {summ['passed']}/{summ['n']}, 상위3 적중 {summ['hit_top3']}/{summ['n_with_expected']}, 혼입 {summ['mixed_items']}건, 비공개 노출 질문 {summ['leak_questions']}개")
    print(f'저장: {base}.json, {base}.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
