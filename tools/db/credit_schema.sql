-- 크레딧 대장 DB(2026-10-11, 사장님 지시: 오픈라우터·GCP 등 유·무료 모든 잔액, 무료 크레딧, 오늘 등록한 것들을 대장에 기록해 관리). 프로젝트 simplifier-ops-data.
-- 원칙: DB가 정본, 문서(docs/대장_체계.md)는 가리키기만 한다. 조회·기록은 scripts/ops/credit_db.py. 비밀값(키·결제번호)은 어떤 열에도 넣지 않는다(참조 이름만).
-- 위치 관례: 기존 SQL은 tools/db/ 에 있어 여기에 둔다. 서비스 키로만 접근(RLS 켬, 정책 없음). 실행은 별도 승인 절차(이 파일은 아직 실행하지 않았다).
-- 성질: 여러 번 실행해도 안전(멱등). 기존 표는 건드리지 않는다. 되돌리기: 맨 아래 rollback.
-- 참고: credit_events 에 unique(account_slug, at, kind)를 둔 것은 seed 가 같은 사건을 중복 없이 갱신(upsert)하게 하려는 것이다.

begin;

create table if not exists credit_accounts (
  slug text primary key,
  name text not null,
  kind text check (kind in ('유료선불','무료크레딧','무료티어','구독','한도형','플랫폼')),
  provider text, owner text, account_email text,
  workspace boolean default false,
  currency text check (currency in ('KRW','USD','calls','credits','minutes')),
  balance numeric, balance_at timestamptz, expires_at date,
  refill_rule text, how_to_check text, check_command text, resource_id text, billing_ref text,
  alert_threshold numeric,
  status text not null default '미확인' check (status in ('정상','주의','소진','만료','미확인')),
  note text, evidence text,
  updated_at timestamptz default now()
);

create table if not exists credit_events (
  id bigserial primary key,
  account_slug text references credit_accounts(slug) on delete cascade,
  at timestamptz default now(),
  kind text check (kind in ('충전','차감','리셋','만료','조정','확인')),
  amount numeric, balance_after numeric, who text, note text, evidence text,
  unique (account_slug, at, kind)
);

create index if not exists credit_events_slug_at on credit_events (account_slug, at desc);

create or replace view v_credit_status as
select a.slug, a.name, a.kind, a.status, a.balance, a.currency,
  a.alert_threshold, a.expires_at, a.balance_at,
  (a.expires_at - current_date) as days_to_expiry,
  e.last_event_at,
  case when a.balance_at is null then null
       else round((extract(epoch from (now() - a.balance_at)) / 3600)::numeric, 1) end as balance_age_hours,
  (a.alert_threshold is not null and a.balance is not null and a.balance < a.alert_threshold) as low
from credit_accounts a
left join lateral (select max(at) as last_event_at from credit_events x where x.account_slug = a.slug) e on true;

-- 곧 만료(30일 안, 이미 지났는데 표시 안 된 것 포함), 알림 기준 미만, 잔액 확인이 72시간 넘게 낡은 것(확인한 적 없는 것 포함)
create or replace view v_credit_expiring as
select s.*,
  concat_ws(', ',
    case when s.days_to_expiry is not null and s.days_to_expiry <= 30 then '만료 임박' end,
    case when s.low then '잔액 부족' end,
    case when s.balance_at is null or s.balance_age_hours > 72 then '확인 낡음' end) as reasons
from v_credit_status s
where s.status <> '만료'
  and ((s.days_to_expiry is not null and s.days_to_expiry <= 30)
    or s.low
    or s.balance_at is null or s.balance_age_hours > 72);

-- 뷰는 기본이 소유자 권한이라 RLS를 우회해 익명 키로 읽힐 수 있다. 호출자 권한으로 바꾸고 익명·로그인 사용자 권한을 거둔다.
alter view v_credit_status set (security_invoker = true);
alter view v_credit_expiring set (security_invoker = true);
revoke all on v_credit_status, v_credit_expiring from anon, authenticated;

alter table credit_accounts enable row level security;
alter table credit_events enable row level security;

commit;
-- rollback: drop view v_credit_expiring; drop view v_credit_status; drop table credit_events, credit_accounts;
