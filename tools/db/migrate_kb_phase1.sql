-- 지식DB 재발방지 1단계 (오퍼스 서브에이전트 2026-10-17, 설계: C:/work/_ops/kb_design_final.md)
-- 대상: 비공개 운영 상태 DB simplifier-ops-data. PostgREST로는 DDL 불가 → SQL 편집기에서 탐이 1회 적용(승인 관례: migrate_N156.sql과 동일).
-- 성질: 추가 전용·멱등(여러 번 실행해도 안전). 기존 표의 데이터는 지우거나 바꾸지 않는다(새 칸·새 표·새 함수·새 색인만).
-- 되돌리기: tools/db/rollback_kb_phase1.sql (새로 만든 것만 지운다. 기존 데이터 불변).
-- 파라미터 근거: kb_tech_research.md — HNSW(m=16, ef_construction=64), RRF k=60 동등 가중.

begin;

-- 0) 확장(있으면 그대로)
create extension if not exists vector;
create extension if not exists pg_trgm;

-- 1) is_active: 구버전 물리 차단용(기본 true = 현행). 기존 행은 전부 true로 채워진다(default).
alter table docs          add column if not exists is_active boolean not null default true;
alter table resources     add column if not exists is_active boolean not null default true;
alter table canonical_map add column if not exists is_active boolean not null default true;
alter table tasks         add column if not exists is_active boolean not null default true;  -- 결정/카드 성격 표

-- 2) resources: 신선도·별칭·사실상태 필드(보완 2: 도구동작·대체경로 사실 승격, 낡은 사실 색출용)
alter table resources add column if not exists aliases       text[];
alter table resources add column if not exists last_verified timestamptz;
alter table resources add column if not exists fact_state    text;   -- current / stale / deprecated 등

-- 3) links 엣지표(신설): 자원·문서·결정 사이 관계를 이름(문자열 열쇠)으로 잇는다(가져오기가 id를 갈아끼워도 안전)
create table if not exists links (
  id         bigint generated always as identity primary key,
  src_id     text not null,
  src_type   text not null,      -- resource / doc / canonical / task
  dst_id     text not null,
  dst_type   text not null,
  rel        text not null,      -- supersedes / relates / routes_to / verified_by ...
  note       text,
  created_at timestamptz not null default now(),
  unique (src_id, src_type, dst_id, dst_type, rel)
);
create index if not exists links_src on links (src_type, src_id);
create index if not exists links_dst on links (dst_type, dst_id);
alter table links enable row level security;  -- 서비스 키는 우회, 공개 키로는 못 읽음(기존 새 표 관례)

-- 4) 색인: 벡터(HNSW) + 키워드(trgm)
--    6천~2만 행에선 seq scan도 빠르나, 색인은 재현율·일관성을 위해 둔다(연구 권장 HNSW).
create index if not exists docs_embedding_hnsw on docs
  using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
create index if not exists docs_title_trgm   on docs          using gin (title gin_trgm_ops);
create index if not exists docs_summary_trgm on docs          using gin (summary gin_trgm_ops);
create index if not exists res_label_trgm    on resources     using gin (label gin_trgm_ops);
create index if not exists canon_topic_trgm  on canonical_map using gin (topic gin_trgm_ops);

-- 5) kb_search RPC(핵심)
--    흐름: 하드필터(is_active) → 결정적 hard-inject(자원/정본 이름·별칭 매칭 = rank 0, 점수 없음)
--          → trgm 키워드 + 벡터 하이브리드(RRF k=60 동등가중, rank 1).
--    q_embedding 이 null 이면 벡터층은 건너뛰고 trgm+주입만(ollama 꺼져도 동작).
create or replace function kb_search(
  q                text,
  q_embedding      vector(1024) default null,
  match_count      int          default 12,
  include_archived boolean      default false
)
returns table (
  result_type   text,          -- resource / canonical / doc
  ref_id        text,
  title         text,
  content       text,
  src           text,          -- 출처
  dt            text,          -- 날짜(갱신/문서 수정일)
  last_verified timestamptz,   -- 신선도(보완 2)
  fact_state    text,
  rank          int,           -- 0 = 결정적 주입, 1 = 하이브리드
  score         double precision
)
language sql stable
as $$
  with inj_res as (   -- 자원 결정적 주입
    select 'resource'::text as result_type, r.id::text as ref_id, r.label as title,
           coalesce(r.note,'') as content, 'resources'::text as src,
           to_char(r.updated_at,'YYYY-MM-DD') as dt, r.last_verified, r.fact_state,
           0 as rank, null::double precision as score,
           ((case when length(r.label)>=2 and q ilike '%'||r.label||'%' then 1 else 0 end)
            + (select count(*) from unnest(coalesce(r.aliases,'{}'::text[])) a
               where length(a)>=2 and q ilike '%'||a||'%'))::double precision as ord
    from resources r
    where (include_archived or coalesce(r.is_active,true))
      and ( q ilike '%'||r.id||'%'
            or (length(r.label)>=2 and q ilike '%'||r.label||'%')
            or exists (select 1 from unnest(coalesce(r.aliases,'{}'::text[])) a
                       where length(a)>=2 and q ilike '%'||a||'%') )
  ),
  inj_canon as (      -- 정본 지도 결정적 주입(키워드 매칭)
    select 'canonical'::text, c.id::text, c.topic,
           coalesce(c.note, c.canonical_path, '') , 'canonical_map'::text,
           to_char(c.updated_at,'YYYY-MM-DD'), null::timestamptz, null::text,
           0, null::double precision,
           (select count(*) from unnest(string_to_array(lower(coalesce(c.keywords,'')),',')) k
            where length(trim(k))>=2 and q ilike '%'||trim(k)||'%')::double precision as ord
    from canonical_map c
    where (include_archived or coalesce(c.is_active,true))
      and exists (select 1 from unnest(string_to_array(lower(coalesce(c.keywords,'')),',')) k
                  where length(trim(k))>=2 and q ilike '%'||trim(k)||'%')
  ),
  kw as (             -- trgm 키워드 순위
    select d.id,
           row_number() over (order by similarity(coalesce(d.title,'')||' '||coalesce(d.summary,'')||' '||coalesce(d.headings,''), q) desc) as rk
    from docs d
    where (include_archived or coalesce(d.is_active,true))
      and similarity(coalesce(d.title,'')||' '||coalesce(d.summary,'')||' '||coalesce(d.headings,''), q) > 0.03
    limit 50
  ),
  vec as (            -- 벡터 순위(q_embedding 있을 때만)
    select d.id, row_number() over (order by d.embedding <=> q_embedding) as rk
    from docs d
    where q_embedding is not null
      and (include_archived or coalesce(d.is_active,true))
      and d.embedding is not null
    order by d.embedding <=> q_embedding
    limit 50
  ),
  fused as (          -- RRF: 1/(60+rank) 합
    select coalesce(kw.id, vec.id) as id,
           coalesce(1.0/(60+kw.rk), 0) + coalesce(1.0/(60+vec.rk), 0) as score
    from kw full outer join vec on kw.id = vec.id
  ),
  doc_rows as (
    select 'doc'::text as result_type, d.id::text as ref_id, d.title,
           left(coalesce(d.summary,''),400) as content, coalesce(d.source,'docs') as src,
           d.mtime::text as dt, null::timestamptz as last_verified, null::text as fact_state,
           1 as rank, f.score, f.score as ord
    from fused f join docs d on d.id = f.id
    order by f.score desc
    limit match_count
  ),
  allrows as (
    select * from inj_res
    union all select * from inj_canon
    union all select * from doc_rows
  )
  select result_type, ref_id, title, content, src, dt, last_verified, fact_state, rank, score
  from allrows
  order by rank asc, ord desc nulls last, score desc nulls last;
$$;

commit;
