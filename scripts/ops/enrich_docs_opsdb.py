# -*- coding: utf-8 -*-
"""문서 색인 보강(N156, 2026-10-05 탐, 사장님 지시: 로컬 LLM이 문서를 보고 검색 태깅): docs 표의 문서마다 로컬 LLM이 태그·역할·"이 문서가 답하는 질문"을 만들어 summary 끝에 붙인다.
로컬 ollama만 쓰므로 비공개 문서가 밖으로 나가지 않는다. GPU는 공용 관문(gpu_gate.py)을 먼저 통과해야 한다. 원본 md는 건드리지 않고, summary는 import_docs_to_opsdb.py로 언제든 원래대로 다시 만들 수 있다.
다시 실행하면 이미 보강한 문서([태그]가 있는 것)는 건너뛴다. 사용: python enrich_docs_opsdb.py [--prefix hansunghee7.github.io/docs/] [--limit 50] [--model exaone3.5:7.8b]"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402

PROMPT = """너는 회사 문서를 검색하기 좋게 정리하는 도우미다. 아래 문서를 읽고 JSON 하나만 출력하라.
{{"tags": ["검색 키워드 8~12개(문서에 나온 고유명사·과제 번호·핵심 낱말, 사람이 질문할 때 쓸 법한 말)"],
 "role": "정본|참고|기록|계획|절차 중 하나(그 주제의 기준이 되는 문서면 정본)",
 "owner": "담당 페르소나(탐/핏/마야/지투/노트/공용) 중 하나",
 "questions": ["이 문서가 답해 주는 질문 3개를 사장님이 평소 말투(짧고 구어체)로"]}}

문서 경로: {path}
제목: {title}
제목줄:
{heads}
앞부분:
{head}
"""


def ask(model, prompt):
    body = json.dumps({'model': model, 'prompt': prompt, 'stream': False, 'format': 'json', 'options': {'temperature': 0, 'num_ctx': 4096}}).encode()
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=body, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=180).read())['response']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='hansunghee7.github.io/docs/')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--model', default='exaone3.5:7.8b')
    a = ap.parse_args()
    log = open(r'C:\work\_ops\n155\enrich_docs.log', 'a', encoding='utf-8')
    rows = opsdb.select('docs', 'id,path,title,headings,summary,body', where={'path': f'like.{a.prefix}*'}, order='id.asc', limit=2000)
    todo = [r for r in rows if '[태그]' not in (r['summary'] or '')]
    if a.limit:
        todo = todo[:a.limit]
    print(f'대상 {len(rows)}개 중 보강할 것 {len(todo)}개', file=log, flush=True)
    t0, ok, bad = time.time(), 0, 0
    for r in todo:
        head = re.sub(r'\s+', ' ', (r['body'] or '')[:1500])
        try:
            d = json.loads(ask(a.model, PROMPT.format(path=r['path'], title=r['title'], heads=(r['headings'] or '')[:500], head=head)))
            tags = ', '.join(str(x) for x in d.get('tags', []))[:300]
            qs = ' / '.join(str(x) for x in d.get('questions', []))[:400]
            base = (r['summary'] or '')[:300]
            summary = f"{base}\n[태그] {tags}\n[역할] {d.get('role', '')} [담당] {d.get('owner', '')}\n[질문] {qs}"
            opsdb.upsert('docs', [{'path': r['path'], 'summary': summary}], 'path')
            ok += 1
        except Exception as e:
            bad += 1
            print(f"실패 {r['path']} {type(e).__name__}", file=log, flush=True)
        if (ok + bad) % 10 == 0:
            print(f'{ok + bad}/{len(todo)} 완료(성공 {ok}, 실패 {bad}), {time.time()-t0:.0f}초', file=log, flush=True)
    print(f'끝: 성공 {ok}, 실패 {bad}, {time.time()-t0:.0f}초, 모델 {a.model}', file=log, flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
