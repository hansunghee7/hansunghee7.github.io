# -*- coding: utf-8 -*-
"""코디네이터 최소 스윕(N192-⑥, 2026-10-18 탐): 매일 한 번 업무대장을 훑어 조율 문제 3가지만 뽑는다.

새 에이전트도, 상주 데몬도 아니다. 운영 DB tasks 표에서 **열린 업무대장**(section=open)만
읽어(읽기 전용) 모닝 브리핑에 한 줄로 얹을 요약을 낸다. 어떤 표도 쓰지 않는다.

뽑는 2가지:
  1) 같은 일 두 곳(중복)  : 제목을 정규화해 거의 같은 열린 작업이 서로 다른 번호/담당으로 2개 이상.
                           단, 날짜·회차(N주차·N월·숫자)만 다른 반복 업무 템플릿은 중복으로 보지 않는다.
  2) 주인 없는 일(미배정)  : 열린 상태인데 담당(owner)이 비었거나 '미정/미상'.

('정체(stale)' 지표는 뺐다 — 갱신 시각 신호가 없어 source_date(대개 생성일)로 판정하면
열린 작업 대부분이 정체로 잡혀 노이즈뿐이다. 갱신 시각이 생기면 다시 넣는다.)

데이터: python scripts/ops/opsdb.py 가 쓰는 opsdb.select 를 그대로 import 해서 읽는다(DB 직접 접속 없음,
새 비밀값 없음). '열린' 정본은 section=='open' 이고, 그 안에서 완료·종결·취소·폐기·이관·닫힘·병합 상태는 제외한다.
'오늘'은 KST 기준.

사용:
  python scripts/ops/coordinator_sweep.py            # 사람용 한 줄 + 분류별 상세
  python scripts/ops/coordinator_sweep.py --json     # 기계용 JSON
  python scripts/ops/coordinator_sweep.py --dup-threshold 0.85
"""
import argparse
import datetime as _dt
import difflib
import json
import re
import sys
from pathlib import Path

# ── 순수 함수(단위시험 대상) ────────────────────────────────────────────────

# 열린 섹션 안에서도 '사실상 닫힌' 상태는 열린 작업으로 치지 않는다(접두어로 판정, 변형 흡수).
RESOLVED_PREFIXES = ('완료', '종결', '취소', '폐기', '이관', '닫힘', '병합', '제외', '반영')
# 담당이 비었다고 볼 값.
UNASSIGNED_VALUES = {'', '미정', '미상', '?', 'none', 'tbd', '-'}
KST = _dt.timezone(_dt.timedelta(hours=9))


def is_resolved_status(status):
    """완료·종결 등 사실상 닫힌 상태면 True(=열린 작업 아님)."""
    s = (status or '').strip()
    return s.startswith(RESOLVED_PREFIXES)


def is_unassigned(owner):
    """담당이 비었거나 미정/미상이면 True."""
    return (owner or '').strip().lower() in UNASSIGNED_VALUES


def normalize_title(title):
    """제목을 비교용으로 정규화: 마크다운 강조·괄호 주석·기호·공백 제거, 소문자화.

    '**롱폼 3관문 운영**(사장님 10/5: ...)' → '롱폼 3관문 운영'. 괄호 안 근거·날짜 주석은 떼어
    핵심 문구만 남긴다."""
    t = title or ''
    t = t.replace('*', ' ')
    # 괄호류 안의 주석 제거(중첩은 단순 반복 제거).
    for _ in range(4):
        new = re.sub(r'[\(\[（【][^\(\)\[\]（）【】]*[\)\]）】]', ' ', t)
        if new == t:
            break
        t = new
    t = re.sub(r'[^0-9a-z가-힣]+', ' ', t.lower())
    return re.sub(r'\s+', ' ', t).strip()


def title_similarity(a, b):
    """정규화 제목 두 개의 유사도(0~1). 완전 일치는 1.0."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _strip_variable_tokens(norm):
    """정규화된 제목에서 숫자·회차 토큰(숫자, N주차/N월의 숫자부)을 떼어 뼈대만 남긴다.
    '정기 10월 1주차 수집' → '정기 월 주차 수집'. 숫자를 지우면 주차·월 같은 공통어만 남는다."""
    t = re.sub(r'\d+', ' ', norm)
    return re.sub(r'\s+', ' ', t).strip()


def is_recurring_variant(a, b):
    """두 제목이 '날짜·회차·숫자만 다른 반복 업무 템플릿'이면 True(=중복 아님).

    정규화 제목이 서로 다르지만(=완전 동일 복제는 아님) 숫자 토큰을 제거하면 같아지는 경우.
    예: '[정기] 10월 1주차 수집' vs '[정기] 10월 2주차 수집' → True.
    완전히 같은 제목(진짜 중복)은 숫자를 빼도 같지만 na==nb라 False로 걸러 중복으로 남긴다."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb or na == nb:
        return False
    sa, sb = _strip_variable_tokens(na), _strip_variable_tokens(nb)
    return bool(sa) and sa == sb


def find_duplicate_groups(items, threshold=0.85):
    """items: [{'no','title','owner',...}]. 번호가 서로 다른데 제목이 거의 같은 묶음을 찾는다.

    같은 번호(no)는 같은 작업이므로 묶지 않는다. 반환: 각 묶음은 멤버 2개 이상의 items 리스트."""
    groups = []
    used = set()
    for i in range(len(items)):
        if i in used:
            continue
        grp = [i]
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            if str(items[i].get('no')) == str(items[j].get('no')):
                continue  # 같은 번호는 중복이 아니다
            ti, tj = items[i].get('title', ''), items[j].get('title', '')
            if is_recurring_variant(ti, tj):
                continue  # 날짜·회차만 다른 반복 템플릿은 중복 아님
            if title_similarity(ti, tj) >= threshold:
                grp.append(j)
        if len(grp) >= 2:
            for k in grp:
                used.add(k)
            groups.append([items[k] for k in grp])
    return groups


# ── DB 읽기(읽기 전용) ──────────────────────────────────────────────────────

def _load_opsdb():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import opsdb  # noqa: E402
    return opsdb


def fetch_open_tasks():
    """열린 업무대장(section=open) 행만 읽어 활성 상태만 남긴다. 읽기 전용."""
    opsdb = _load_opsdb()
    rows = opsdb.select(
        'tasks',
        cols='id,no,title,status,section,owner,source_date,imported_at,raw',
        where='section=eq.open',
        order='id.asc',
        limit=1000,
    )
    return [r for r in rows if not is_resolved_status(r.get('status'))]


# ── 집계 ────────────────────────────────────────────────────────────────────

def build_report(rows, today, dup_threshold=0.85):
    dup_groups = find_duplicate_groups(rows, threshold=dup_threshold)

    unassigned = [r for r in rows if is_unassigned(r.get('owner'))]

    return {
        'date': today.isoformat(),
        'open_task_count': len(rows),
        'duplicates': [
            [{'no': m.get('no'), 'title': m.get('title'), 'owner': m.get('owner')} for m in grp]
            for grp in dup_groups
        ],
        'unassigned': [
            {'no': r.get('no'), 'title': r.get('title'), 'owner': r.get('owner')} for r in unassigned
        ],
    }


def _short(title, n=54):
    t = (title or '').replace('*', '').replace('\n', ' ').strip()
    return t[:n] + ('…' if len(t) > n else '')


def format_text(rep):
    one = '코디네이터 스윕: 중복 %d · 미배정 %d' % (
        len(rep['duplicates']), len(rep['unassigned']))
    lines = [one, '(열린 업무대장 %d건 기준, %s KST)' % (rep['open_task_count'], rep['date']), '']

    lines.append('■ 같은 일 두 곳(중복): %d' % len(rep['duplicates']))
    if not rep['duplicates']:
        lines.append('  없음')
    else:
        for i, grp in enumerate(rep['duplicates'], 1):
            lines.append('  [%d]' % i)
            for m in grp:
                lines.append('     %s / %s · %s' % (m['no'], m['owner'], _short(m['title'])))

    lines.append('■ 주인 없는 일(미배정): %d' % len(rep['unassigned']))
    if not rep['unassigned']:
        lines.append('  없음')
    else:
        for r in rep['unassigned']:
            lines.append('  %s / %r · %s' % (r['no'], r['owner'], _short(r['title'])))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='코디네이터 최소 스윕(읽기 전용)')
    ap.add_argument('--json', action='store_true', help='기계용 JSON 출력')
    ap.add_argument('--dup-threshold', type=float, default=0.85)
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    today = _dt.datetime.now(KST).date()
    rows = fetch_open_tasks()
    rep = build_report(rows, today, dup_threshold=a.dup_threshold)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(format_text(rep))


if __name__ == '__main__':
    main()
