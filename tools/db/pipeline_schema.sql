-- 데이터 수집 파이프 대장 DB(2026-10-11, 사장님 지시: API·스크래핑 등 데이터 수집 파이프 대장을 만들고, 이 대장의 프로세스로 각 데이터수집 대장이 관리되도록 구조화). 프로젝트 simplifier-ops-data.
-- 구조: pipeline_ledgers(데이터 대장 = 수집 결과가 쌓이는 곳) 1 : N data_pipelines(수집 경로) 1 : N pipeline_runs(실행 기록).
-- 원칙: DB가 정본, 문서(docs/대장_체계.md)는 가리키기만 한다. 조회·기록은 scripts/ops/pipeline_db.py. 비밀값은 열에 넣지 않고 auth_ref 에 참조 이름만 쓴다.
-- 위치 관례: 기존 SQL은 tools/db/ 에 있어 여기에 둔다. 서비스 키로만 접근(RLS 켬, 정책 없음). 실행은 별도 승인 절차(이 파일은 아직 실행하지 않았다).
-- 성질: 여러 번 실행해도 안전(멱등). 기존 표는 건드리지 않는다. 되돌리기: 맨 아래 rollback.

begin;

create table if not exists pipeline_ledgers (
  slug text primary key,
  name text not null,
  table_name text, owner text, update_process text,
  freshness_hours int,
  status text not null check (status in ('작동','부분','막힘','계획','폐기')),
  status_note text,
  updated_at timestamptz default now()
);

create table if not exists data_pipelines (
  slug text primary key,
  name text not null,
  kind text check (kind in ('API','스크래핑','파일','구독','웹훅','이메일')),
  source text, owner text, schedule text, engine text, destination text, auth_ref text,
  freshness_hours int,
  status text not null check (status in ('작동','부분','막힘','계획','폐기')),
  status_note text, watch_job_id text,
  ledger_slug text references pipeline_ledgers(slug),
  process_ref text, how_to text, limits text, tos_risk text, evidence text,
  last_success timestamptz, last_checked timestamptz,
  updated_at timestamptz default now()
);

create table if not exists pipeline_runs (
  id bigserial primary key,
  pipeline_slug text references data_pipelines(slug) on delete cascade,
  ran_at timestamptz default now(),
  ok boolean, rows_in bigint, note text, evidence text
);

create index if not exists pipeline_runs_slug_ran_at on pipeline_runs (pipeline_slug, ran_at desc);
create index if not exists data_pipelines_ledger on data_pipelines (ledger_slug);

-- 신선도 기준은 파이프라인 값이 우선, 없으면 소속 대장 값. 계획·폐기는 stale 로 치지 않는다. 한 번도 성공 못 한 작동 건은 stale.
create or replace view v_pipeline_status as
select p.slug, p.name, p.kind, p.status, p.status_note, p.ledger_slug,
  p.watch_job_id, p.schedule, p.last_success, p.last_checked,
  coalesce(p.freshness_hours, l.freshness_hours) as freshness_hours,
  case when p.last_success is null then null
       else round((extract(epoch from (now() - p.last_success)) / 3600)::numeric, 1) end as hours_since_success,
  (p.status not in ('계획','폐기')
    and coalesce(p.freshness_hours, l.freshness_hours) is not null
    and (p.last_success is null
         or now() - p.last_success > make_interval(hours => coalesce(p.freshness_hours, l.freshness_hours)))) as stale
from data_pipelines p
left join pipeline_ledgers l on l.slug = p.ledger_slug;

create or replace view v_ledger_health as
select l.slug, l.name, l.status, l.status_note, l.freshness_hours,
  count(s.slug) as pipelines,
  count(s.slug) filter (where s.stale) as stale_count,
  count(s.slug) filter (where s.status = '막힘') as blocked_count
from pipeline_ledgers l
left join v_pipeline_status s on s.ledger_slug = l.slug
group by l.slug, l.name, l.status, l.status_note, l.freshness_hours;

-- 뷰는 기본이 소유자 권한이라 RLS를 우회해 익명 키로 읽힐 수 있다. 호출자 권한으로 바꾸고 익명·로그인 사용자 권한을 거둔다.
alter view v_pipeline_status set (security_invoker = true);
alter view v_ledger_health set (security_invoker = true);
revoke all on v_pipeline_status, v_ledger_health from anon, authenticated;

alter table pipeline_ledgers enable row level security;
alter table data_pipelines enable row level security;
alter table pipeline_runs enable row level security;

commit;
-- rollback: drop view v_ledger_health; drop view v_pipeline_status; drop table pipeline_runs, data_pipelines, pipeline_ledgers;
