-- N156 운영 상태 DB 스키마 v4, M2 단계 (클라우드 탐 초안 2026-10-07, 설계: docs/설계_N156_운영DB화.md)
-- 대상: 시험용 Supabase 프로젝트(운영 Carvit DB와 분리). 운영 DB 쓰기는 사장님 몫이므로 SQL 편집기 실행은 승인 1회가 필요하다.
-- 성질: 여러 번 실행해도 안전(멱등). 기존 표의 데이터는 지우거나 바꾸지 않는다(새 표·새 칸·새 뷰만 추가, tasks.status_family는 계산 칸).
-- 주의: 가져오기 스크립트(import_ops_tables.py)는 일부 표를 "비우고 다시 채운다". 그래서 아래 새 표는 그 표들의 id를 참조하지 않고
--       이름(문자열 열쇠)으로만 잇는다. 로그 표 잠금(트리거)은 이 파일이 아니라 migrate_N156_M3_lock.sql이다(M1 안정 뒤).
-- 되돌리기: tools/db/rollback_N156.sql (새로 만든 것만 지운다).

begin;

-- 1) 상태값 목록: 업무대장의 상태 변종을 family 하나로 접는다
create table if not exists task_status (
  code   text primary key,
  family text not null check (family in ('open', 'waiting', 'done', 'hold', 'decision')),
  note   text
);
insert into task_status (code, family, note) values
  ('진행',     'open',     '지금 하는 중'),
  ('대기',     'waiting',  '조건이 풀리면 시작'),
  ('확인필요', 'waiting',  '누군가 확인해야 함'),
  ('사장님',   'waiting',  '사장님 몫'),
  ('보류',     'hold',     '의도적으로 미룸'),
  ('완료',     'done',     null),
  ('완료·증거', 'done',    '증거 첨부 완료'),
  ('결정',     'decision', '결정 기록')
on conflict (code) do nothing;

-- tasks에 계산 칸 추가(가져오기가 이 칸을 모르므로 가져온 뒤 아래 갱신 문장으로 채운다)
alter table tasks add column if not exists status_family text;
update tasks t
   set status_family = s.family
  from task_status s
 where t.status = s.code
   and t.status_family is distinct from s.family;

-- 2) 변경 이력(덧붙이기 전용으로 쓸 표): 가져오기가 이전 값과 비교해 바뀐 칸만 넣는다
create table if not exists task_events (
  id         bigint generated always as identity primary key,
  owner      text not null,
  task_no    text,
  section    text not null,
  field      text not null,
  old_value  text,
  new_value  text,
  changed_at timestamptz not null default now(),
  source     text not null              -- import-diff(md가 바뀌어 DB에 반영) / agent-write
);
create index if not exists task_events_key on task_events (owner, task_no, changed_at desc);
create index if not exists task_events_at on task_events (changed_at desc);

-- 3) 가져오기 실행 기록: 감시와 별개로 DB에서 "몇 행 넣고 바꿨나"를 질의(실패도 기록)
create table if not exists ingest_runs (
  id           bigint generated always as identity primary key,
  job          text not null,
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  rows_in      integer,
  rows_changed integer,
  rc           integer,                 -- 0 성공, 그 밖은 실패
  note         text
);
create index if not exists ingest_runs_job_at on ingest_runs (job, started_at desc);

-- 4) 한도 스냅샷: 값(키·비밀번호)은 없고 남은 양만. accounts의 id가 가져올 때마다 바뀌므로 이름(account_key)으로 잇는다
create table if not exists quota_snapshots (
  id           bigint generated always as identity primary key,
  account_key  text not null,           -- accounts.display_name 또는 표준 약칭(문자열 열쇠)
  resource     text not null,           -- flow-credit / gemini-free / vertex-credit ...
  remaining    numeric,
  unit         text,
  measured_at  timestamptz not null default now(),
  source       text not null            -- manual / script
);
create index if not exists quota_snapshots_key on quota_snapshots (account_key, resource, measured_at desc);

-- 금고 안의 이름(참조)만. 값은 어떤 칸에도 두지 않는다
create table if not exists account_vault_refs (
  account_key text primary key,
  vault_ref   text not null,
  updated_at  timestamptz not null default now()
);

-- 5) 제목과 한국 시각이 붙은 영상 성과 뷰
create or replace view v_content_perf as
select ci.id                                   as content_id,
       ci.channel_id,
       ci.kind,
       ci.title,
       ci.status,
       ci.scheduled_at  at time zone 'Asia/Seoul' as scheduled_kst,
       ci.published_at  at time zone 'Asia/Seoul' as published_kst,
       m.captured_at    at time zone 'Asia/Seoul' as measured_kst,
       m.views, m.likes, m.comments, m.watch_hours, m.followers_delta,
       m.source                                as metrics_source
  from content_items ci
  left join v_latest_metrics m on m.content_id = ci.id;

-- 6) 점검용 뷰
create or replace view v_tasks_unmapped_status as
select owner, section, status, count(*) as n
  from tasks
 where status_family is null
 group by owner, section, status
 order by n desc;

create or replace view v_ingest_latest as
select distinct on (job) job, started_at, finished_at, rows_in, rows_changed, rc, note
  from ingest_runs
 order by job, started_at desc;

-- 7) 새 표는 행 수준 보안을 켠다(서비스 키는 우회하므로 에이전트 동작은 그대로, 공개 키로는 못 읽는다)
alter table task_status        enable row level security;
alter table task_events        enable row level security;
alter table ingest_runs        enable row level security;
alter table quota_snapshots    enable row level security;
alter table account_vault_refs enable row level security;

commit;
