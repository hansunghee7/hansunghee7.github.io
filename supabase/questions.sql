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
-- service_role은 RLS를 우회하므로 정책이 필요 없다.
