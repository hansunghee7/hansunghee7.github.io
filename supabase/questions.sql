-- "심플리파이어에게 질문하기" 접수함 (2026-09-02, 탐)
--
-- 방문자가 공개 글 하단 폼에서 남긴 질문+이메일을 받는 테이블.
-- 이 저장소는 공개라 이메일은 절대 저장소로 오지 않는다 — 여기(Supabase,
-- simplifier-agent 프로젝트)에만 있고, Actions가 service_role 키로 읽는다.
--
-- 행 단위 보안(RLS)이 이 설계의 핵심 자물쇠다:
--   - 공개 페이지는 anon 키로 "삽입만" 할 수 있다. 읽기·수정·삭제는 불가.
--     anon 키는 원래 브라우저에 노출되는 공개 키이고, 안전은 키가 아니라
--     아래 정책이 만든다. (역할 노트의 핵심 학습 주제 "칸막이"의 첫 사례)
--   - service_role 키(Actions 시크릿)는 RLS를 우회해 전부 다룬다.
--
-- 실행 방법: Supabase 대시보드 → SQL Editor → 이 파일 전체 붙여넣기 → Run.
-- 한 번만 실행한다(if not exists 라 두 번 돌려도 안전).

create table if not exists public.questions (
  id           uuid primary key default gen_random_uuid(),
  created_at   timestamptz not null default now(),
  question     text not null check (char_length(question) between 5 and 2000),
  -- 방문자 질문(visitor)은 이메일 필수, 사장님 픽(pick, 후보 이슈에서 체크)은 이메일 없음
  source       text not null default 'visitor' check (source in ('visitor', 'pick')),
  email        text check (
                 email is null or (
                   char_length(email) <= 254
                   and email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
                 )
               ),
  page         text check (char_length(page) <= 500),   -- 질문을 남긴 글의 경로 (픽은 issue#N)
  -- 상태 어휘는 쇼츠 파이프라인(시트 "상태" 열)과 맞춘다: 대기 → 처리중 → 초안 → 발행 / 반려
  status       text not null default '대기'
               check (status in ('대기', '처리중', '초안', '발행', '반려')),
  attempts     int  not null default 0,                 -- 초안 생성 시도 횟수(3회 넘으면 반려)
  draft_branch text,
  draft_pr     int,
  draft_path   text,
  error        text,
  website      text                                     -- 허니팟: 사람은 못 보는 칸, 값이 있으면 봇
);

create index if not exists questions_status_created_idx
  on public.questions (status, created_at);

alter table public.questions enable row level security;

-- 공개 페이지(anon)는 삽입만. 방문자 질문(이메일 있음)이고, 허니팟이 비어 있고,
-- 상태가 기본값일 때만. 'pick'은 service_role(Actions)만 넣을 수 있다.
drop policy if exists "anon insert only" on public.questions;
create policy "anon insert only"
  on public.questions
  for insert
  to anon
  with check (
    source = 'visitor' and email is not null
    and coalesce(website, '') = '' and status = '대기'
  );

-- select/update/delete 정책은 일부러 만들지 않는다 → anon은 아무것도 못 읽는다.
-- service_role은 RLS를 우회하므로 "정책"은 필요 없다 — 단 아래 GRANT는 필요하다.

-- RLS 정책은 "이미 있는 권한을 좁히는" 역할만 한다 — 권한 자체는 만들지
-- 않는다. anon에게 이 테이블의 INSERT 권한을 명시적으로 주지 않으면 위
-- 정책이 있어도 "permission denied for table questions"(42501)로 막힌다
-- (2026-09-03 실측: GET 테스트에서 "GRANT SELECT ON public.questions TO
-- anon" 힌트로 발견 — 여긴 SELECT를 안 주는 게 의도이므로 INSERT만 준다).
grant insert on public.questions to anon;

-- service_role(Actions)도 마찬가지다 — RLS를 우회한다는 것과 테이블 권한이
-- 있다는 것은 별개. 이 프로젝트는 service_role에도 기본 권한이 없어서
-- 초안 워크플로(클로드 API 경로, 2026-09-04 드랍)가 42501로 5회 연속
-- 실패했다(실측 힌트 "GRANT SELECT ON public.questions TO service_role").
--   select/update: 접수함을 읽고 상태를 바꾸는 쪽(초안 단계를 무엇으로
--                  다시 만들든 Actions가 접수함을 만지면 필요)
--   insert:        사장님 픽 질문 넣기 (pick_questions.py, source='pick')
-- delete는 어떤 스크립트도 안 쓰므로 주지 않는다.
grant select, insert, update on public.questions to service_role;

-- ✅ 체크리스트 — 이 저장소에 Supabase 테이블을 새로 만들 때(계단 5 뉴스레터 등):
--   [ ] RLS 정책을 썼는가 → 그 정책이 걸리는 역할에 GRANT도 썼는가
--   [ ] 그 테이블을 읽고 쓰는 스크립트마다 필요한 동사(select/insert/update)를
--       역할별로 세었는가 (anon, service_role 각각)
--   [ ] 대시보드 SQL Editor에서 실행 후, 실제 호출 1회로 42501이 안 나는지 확인했는가
