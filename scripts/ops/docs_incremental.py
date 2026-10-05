# -*- coding: utf-8 -*-
"""문서 DB(docs 표) 증분 갱신: 새로 생기거나 바뀐 md만 다시 적재하고 지워진 문서는 DB에서 뺀 뒤, 임베딩이 빈 행만 로컬 bge-m3로 채운다
(N156 문서 적재·임베딩 하루 1회 증분 자동화, 2026-10-05 탐). 전체 재적재(import_docs_to_opsdb.py)와 달리 안 바뀐 행은 건드리지 않아 보강 칸(tags 등)이 보존된다.
바뀐 판정: 날짜(mtime)·바이트 수가 DB와 다를 때. 같은 날 같은 바이트 수로 고친 문서는 놓칠 수 있다(전체 재적재로 보정).
임베딩: 로컬 ollama(bge-m3)만 쓴다. 비공개 문서가 외부로 나가지 않는다. ollama가 꺼져 있으면 적재만 하고 임베딩은 다음 실행으로 넘긴다(종료 코드 0, 빈 행 수를 출력).
사용: python scripts/ops/docs_incremental.py [--dry]    종료 코드 1 = DB 오류"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opsdb  # noqa: E402
import import_docs_to_opsdb as imp  # noqa: E402

MODEL = 'bge-m3'


def embed(text):
    req = urllib.request.Request('http://127.0.0.1:11434/api/embeddings', data=json.dumps({'model': MODEL, 'prompt': text[:3000]}).encode(), headers={'Content-Type': 'application/json'})
    v = json.loads(urllib.request.urlopen(req, timeout=60).read())['embedding']
    return v + [0.0] * (1024 - len(v))


def existing():
    out, off = {}, 0
    while True:
        rows = opsdb.select('docs', 'id,path,mtime,bytes', order='id.asc', limit=1000, where={'id': f'gt.{off}'})
        if not rows:
            return out
        for r in rows:
            out[r['path']] = (r['mtime'], r['bytes'])
        off = rows[-1]['id']


def main():
    dry = '--dry' in sys.argv
    old = existing()
    rows = imp.collect()
    now = {r['path'] for r in rows}
    changed = [r for r in rows if old.get(r['path']) != (r['mtime'], r['bytes'])]
    gone = [p for p in old if p not in now]
    print(f'DB {len(old)}개 / 지금 {len(rows)}개 → 새로·바뀐 {len(changed)}개, 사라진 {len(gone)}개')
    if dry:
        return 0
    for r in changed:
        r['embedding'] = None  # 본문이 바뀌었으니 옛 임베딩은 버리고 아래에서 다시 채운다
    n = 0
    for i in range(0, len(changed), 40):
        n += opsdb.upsert('docs', changed[i:i + 40], 'path')
    for p in gone:
        opsdb.delete('docs', {'path': f'eq.{p}'})
    empty = opsdb.select('docs', 'path,title,headings,summary,tags,questions', where={'embedding': 'is.null'}, limit=2000)
    done = 0
    for r in empty:
        text = f"{r['title']}\n{(r['headings'] or '')[:800]}\n{(r['summary'] or '')[:600]}\n{r.get('tags') or ''}\n{r.get('questions') or ''}"
        try:
            v = embed(text)
        except Exception as e:  # ollama 꺼짐 등: 다음 실행에서 이어 채운다
            print(f'임베딩 중단({type(e).__name__}), 남은 빈 행 {len(empty) - done}개는 다음 실행으로')
            break
        opsdb.upsert('docs', [{'path': r['path'], 'embedding': '[' + ','.join(f'{x:.6f}' for x in v) + ']'}], 'path')
        done += 1
    print(f'적재 {n}, 삭제 {len(gone)}, 임베딩 {done}/{len(empty)} | DB 행 수 {opsdb.count("docs")}')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except RuntimeError as e:
        print('DB 오류:', e)
        sys.exit(1)
