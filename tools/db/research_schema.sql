-- 리서치 체계 연관 DB(2026-10-11, 사장님 지시: 제미나이리서치·슈퍼리서치 등을 모듈형 공정표로 작동 현황 관리). 프로젝트 simplifier-ops-data.
-- 원칙: DB가 정본, 문서(docs/리서치_체계.md)는 가리키기만 한다. 조회·기록은 scripts/ops/research_db.py.
-- 위치 관례: 기존 SQL은 tools/db/ 에 있어 여기에 둔다. 서비스 키로만 접근(RLS 켬, 정책 없음). 실행은 별도 승인 절차(이 파일은 아직 실행하지 않았다).
-- 성질: 여러 번 실행해도 안전(멱등). 기존 표는 건드리지 않는다. 되돌리기: 맨 아래 rollback.
-- 참고: research_issues 에 unique(slug, symptom)을 둔 것은 seed·add-issue 가 같은 증상을 중복 없이 갱신(upsert)하게 하려는 것이다.

begin;

create table if not exists research_modules (
  slug text primary key,
  name text not null,
  kind text check (kind in ('체계','모듈','도구','규칙','경로')),
  summary text, owner text,
  status text not null check (status in ('작동','부분','막힘','계획','폐기')),
  status_note text, engine text, entry text, how_to text, limits text,
  process_ref text, docs text, evidence text, last_verified date,
  created_at timestamptz default now(), updated_at timestamptz default now()
);

create table if not exists research_links (
  parent text references research_modules(slug) on delete cascade,
  child text references research_modules(slug) on delete cascade,
  seq int,
  role text check (role in ('step','fallback','gate')),
  required boolean default true,
  note text,
  primary key (parent, child, role)
);

create table if not exists research_issues (
  id bigserial primary key,
  slug text references research_modules(slug) on delete cascade,
  found_at date, symptom text, cause text, fix text,
  status text check (status in ('열림','해결','관찰')),
  evidence text,
  created_at timestamptz default now(),
  unique (slug, symptom)
);

create table if not exists research_runs (
  id bigserial primary key,
  slug text references research_modules(slug) on delete cascade,
  ran_at timestamptz default now(),
  who text, question text, route text, result_path text,
  ok boolean, cost_krw numeric, notes text
);

create table if not exists research_link_checks (
  id bigserial primary key,
  run_id bigint references research_runs(id) on delete cascade,
  url text, http int,
  verdict text check (verdict in ('확인','부분','미확인','불일치')),
  note text
);

create index if not exists research_runs_slug_ran_at on research_runs (slug, ran_at desc);
create index if not exists research_issues_slug_status on research_issues (slug, status);
create index if not exists research_link_checks_run on research_link_checks (run_id);

create or replace view v_research_status as
select m.slug, m.name, m.kind, m.status, m.status_note, m.last_verified,
  r.ran_at as last_run_at, r.ok as last_run_ok,
  (select count(*) from research_issues i where i.slug = m.slug and i.status = '열림') as open_issues
from research_modules m
left join lateral (select ran_at, ok from research_runs x where x.slug = m.slug order by ran_at desc limit 1) r on true;

create or replace view v_research_howto as
select slug, name, status, entry, how_to, limits, process_ref from research_modules;

-- 뷰는 기본이 소유자 권한이라 RLS를 우회해 익명 키로 읽힐 수 있다. 호출자 권한으로 바꾸고 익명·로그인 사용자 권한을 거둔다.
alter view v_research_status set (security_invoker = true);
alter view v_research_howto set (security_invoker = true);
revoke all on v_research_status, v_research_howto from anon, authenticated;

alter table research_modules enable row level security;
alter table research_links enable row level security;
alter table research_issues enable row level security;
alter table research_runs enable row level security;
alter table research_link_checks enable row level security;

commit;
-- rollback: drop view v_research_howto; drop view v_research_status; drop table research_link_checks, research_runs, research_issues, research_links, research_modules;
