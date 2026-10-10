-- 작업기 장부(worker_ledger) 표 초안 (클라우드 탐 2026-10-08, 요청: 핏 / 사장님 10/8 결정 "작업기 장부를 표로 만들어 Supabase DB로 관리")
-- 대상: 운영 상태 DB(opsdb.py가 붙는 곳). 실행(SQL 편집기)은 사장님 승인 1회가 필요하다(N156 규칙). 이 파일은 초안이며 아직 실행하지 않았다.
-- 성질: 여러 번 실행해도 안전(멱등). 기존 표는 건드리지 않는다.
-- 보안: 계정 칸(account)에 이메일이 들어간다. 값은 DB에만 두고 저장소·로그에 올리지 않는다.
--       RLS를 켜고 정책을 만들지 않아 서비스 키(opsdb.py)로만 읽고 쓴다. 공개 키로는 아무것도 안 보인다.
-- 되돌리기: 맨 아래 주석의 drop 문장(새로 만든 것만 지운다).

begin;

create table if not exists worker_ledger (
  worker_id        text primary key,          -- 작업기 id
  account          text,                      -- 계정(이메일 포함, 출력할 때 가린다)
  port             integer,                   -- 포트
  updated_at       timestamptz not null default now(),  -- 이 행을 마지막으로 고친 시각(자동)
  credit_remaining numeric,                   -- 잔여 크레딧
  read_at          timestamptz,               -- 잔여 크레딧을 읽은 시각
  today_cut        numeric,                   -- 오늘 컷
  today_deduct     numeric,                   -- 오늘 차감
  status           text,                      -- 상태
  status_reason    text                       -- 상태 원인
);

-- 행을 고칠 때마다 updated_at을 자동으로 갱신(쓰는 쪽이 깜빡해도 최신 시각이 남는다)
create or replace function worker_ledger_touch() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists worker_ledger_touch on worker_ledger;
create trigger worker_ledger_touch before update on worker_ledger
  for each row execute function worker_ledger_touch();

alter table worker_ledger enable row level security;

commit;

-- 되돌리기(실행하려면 주석을 풀고 따로 실행):
-- drop trigger if exists worker_ledger_touch on worker_ledger;
-- drop function if exists worker_ledger_touch();
-- drop table if exists worker_ledger;
