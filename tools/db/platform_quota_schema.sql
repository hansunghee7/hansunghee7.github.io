-- 플랫폼·계정별 한도 장부와 시도 기록 표 초안 (핏, 2026-10-09, 사장님 10/9: "플랫폼별·계정별로 따로 관리, 수파베이스에 DB 만들어 관리")
-- 대상: 운영 상태 DB(opsdb.py가 붙는 곳). worker_ledger_schema.sql(Flow 잔여 위주 초안)의 확장판이다. 실행(SQL 편집기)은 사장님 승인 1회가 필요하다(N156 규칙). 이 파일은 초안이며 아직 실행하지 않았다.
-- 성질: 여러 번 실행해도 안전(멱등). 기존 표는 건드리지 않는다.
-- 보안: 계정 칸에 이메일이 들어간다. 값은 DB에만 두고 저장소·로그에 올리지 않는다. RLS를 켜고 정책을 만들지 않아 서비스 키(opsdb.py)로만 읽고 쓴다.
-- 설계 원칙: 정지·휴식은 계정×플랫폼 한 줄 단위로만 건다(전면 중단 금지, 사장님 10/9). 시도(성공·정책 거절·한도·차단)를 한 줄씩 쌓아 A/B와 정책 분석에 쓴다.
-- 되돌리기: 맨 아래 주석의 drop 문장(새로 만든 것만 지운다).

begin;

-- 1) 계정×플랫폼 현재 상태 (한 줄 = 한 계정의 한 플랫폼)
create table if not exists platform_quota (
  account         text not null,               -- 계정(이메일, 출력할 때 가린다)
  platform        text not null,               -- flow | vids | gemini_app
  unit            text,                        -- credit(Flow) | video(제미나이·Vids 횟수)
  daily_limit     numeric,                     -- 하루 한도(제미나이 3, Flow는 크레딧 50 등 관측값)
  remaining       numeric,                     -- 마지막으로 읽은 잔여
  read_at         timestamptz,                 -- 잔여를 읽은 시각
  reuse_at        timestamptz,                 -- 화면이 알려 준 재사용·초기화 시각(소진 직후 팝업 문구가 정본)
  reset_model     text,                        -- 가설 메모: 고정 시각 / 24h 롤링 / 12h 롤링
  status          text,                        -- 정상 | 대기 | 소진 | 차단 | 로그인필요 | 정지(사장님지시)
  status_reason   text,                        -- 화면 문구 원문 또는 사유
  pc              text,                        -- 실행 위치: 신PC | 구PC
  port            integer,
  updated_at      timestamptz not null default now(),
  primary key (account, platform)
);

-- 2) 시도 기록 (한 줄 = 한 번의 생성 시도)
create table if not exists quota_events (
  id              bigint generated always as identity primary key,
  at              timestamptz not null default now(),
  account         text not null,
  platform        text not null,               -- flow | vids | gemini_app
  runner          text,                        -- night_runner | account_worker | 사람 | 서브에이전트
  pc              text,
  episode         text,
  scene           text,
  result          text not null,               -- 성공 | 정책거절 | 한도소진 | 차단 | 오류 | 시간초과
  refusal_text    text,                        -- 거절·차단 화면 문구 원문(짧게)
  remaining_after numeric,                     -- 시도 뒤 화면에 보인 남은 횟수·크레딧
  secs            integer,                     -- 걸린 시간(초)
  prompt_variant  text,                        -- 원문 | 순화본 | A | B (A/B 비교용)
  note            text
);
create index if not exists quota_events_acct_at on quota_events (account, platform, at desc);

-- 갱신 시각 자동
create or replace function platform_quota_touch() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;
drop trigger if exists platform_quota_touch on platform_quota;
create trigger platform_quota_touch before update on platform_quota
  for each row execute function platform_quota_touch();

alter table platform_quota enable row level security;
alter table quota_events enable row level security;

commit;

-- 되돌리기(실행하려면 주석을 풀고 따로 실행):
-- drop trigger if exists platform_quota_touch on platform_quota;
-- drop function if exists platform_quota_touch();
-- drop table if exists quota_events;
-- drop table if exists platform_quota;
