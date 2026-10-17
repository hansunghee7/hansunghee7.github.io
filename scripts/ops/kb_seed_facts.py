# -*- coding: utf-8 -*-
"""지식DB 재발방지 1단계 - 사실 시딩(페이블 보완 2: "도구 동작·대체 경로" 사실을 resources 행으로 승격).
hard-inject가 이름·별칭 매칭에 의존하므로, 과거에 놓친 4건을 별칭 사전과 함께 resources에 upsert한다(2026-10-17 오퍼스).
멱등: 같은 id로 다시 넣으면 갱신만. aliases/last_verified/fact_state 칸은 migrate_kb_phase1.sql 적용 뒤에 채워진다
(칸이 없으면 자동으로 기본 칸만 넣고 경고 — 마이그레이션 적용 후 재실행하면 전부 채워진다).
사용: python scripts/ops/kb_seed_facts.py [--dry]"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
import opsdb  # noqa: E402

NOW = time.strftime('%Y-%m-%dT%H:%M:%S+09:00')

# 질의 → 올바른 사실로 라우팅되도록 별칭을 질의 키워드까지 포함해 설계(보완 2 별칭 사전).
FACTS = [
    {
        'id': 'openrouter', 'kind': 'llm-route', 'label': 'OpenRouter', 'owner': '탐',
        'aliases': ['openrouter', '오픈라우터'],
        'note': '$10 평생크레딧 이미 충전됨 → 무료 1000회/일 적용 중, 추가 결제 불필요.',
        'fact_state': 'current', 'last_verified': NOW,
    },
    {
        'id': 'self-hosted-runner', 'kind': 'infra', 'label': '자체 GitHub 실행기(구PC)', 'owner': '탐',
        'aliases': ['구피시', '자체실행기', 'saegim-test', 'self-hosted runner', 'github actions', 'ubuntu-latest', '실행기'],
        'note': '구PC 자체 GitHub 실행기. Carvit/saegim 배포는 여기(무료). 이 저장소 22개 워크플로는 아직 ubuntu-latest(유료).',
        'fact_state': 'current', 'last_verified': NOW,
    },
    {
        'id': 'bt-routing', 'kind': 'llm-route', 'label': '비티 라우팅(ask_bt.sh)', 'owner': '탐',
        'aliases': ['비티', 'ask_bt.sh', 'vertex 폴백'],
        'note': 'ask_bt.sh는 제미나이→라우터→소넷→Vertex(GCP유료) 자동폴백. 무료 캡 시 Vertex 유료로 끊김없이 돈다.',
        'fact_state': 'current', 'last_verified': NOW,
    },
    {
        'id': 'azure-credit', 'kind': 'cloud-credit', 'label': 'Azure(MS for Startups)', 'owner': '탐',
        'aliases': ['azure', '애저', 'ms for startups', 'founders hub'],
        'note': 'Founders Hub $5000 승인(10/14). GitHub Actions 유료분 결제 가능(탐#46). env 등록 남음.',
        'fact_state': 'current', 'last_verified': NOW,
    },
]

BASE_COLS = ('id', 'kind', 'label', 'owner', 'note')
NEW_COLS = ('aliases', 'last_verified', 'fact_state')


def main():
    dry = '--dry' in sys.argv
    full = [dict(f) for f in FACTS]
    base = [{k: f[k] for k in BASE_COLS} for f in FACTS]
    if dry:
        import json
        print(json.dumps(full, ensure_ascii=False, indent=2))
        return 0
    try:
        n = opsdb.upsert('resources', full, on_conflict='id')
        print(f'시딩 완료(전체 칸): {n}행 upsert. 별칭·신선도·사실상태 포함.')
        return 0
    except RuntimeError as e:
        if 'PGRST204' in str(e) or 'column' in str(e).lower():
            n = opsdb.upsert('resources', base, on_conflict='id')
            print(f'[주의] aliases/last_verified/fact_state 칸이 아직 없습니다(마이그레이션 미적용).')
            print(f'       기본 칸만 {n}행 넣었습니다. migrate_kb_phase1.sql 적용 뒤 이 스크립트를 다시 실행하세요.')
            return 2
        raise


if __name__ == '__main__':
    sys.exit(main())
