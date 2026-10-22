-- 슈퍼프로젝트 진행표 복사본(문서 -> DB 단방향). 이 파일은 만들기만 했고 실행하지 않았다.
-- 복사 도구: scripts/ops/import_ops_tables.py --with-steps
-- 접근 규칙: 기존 tasks 표와 같은 정책 적용 필요, 적용은 사장님 승인 뒤(아래 RLS 켜기까지만 적어 두고, 읽기 정책은 tasks와 맞춰 적용한다).
create table if not exists project_steps (
  id bigint generated always as identity primary key,
  project text not null,
  ord int not null,
  step_no text,
  item text not null,
  status text not null,
  pr text,
  ci text,
  next text,
  source text,
  updated_at timestamptz default now(),
  unique (project, ord)
);
alter table project_steps enable row level security;
