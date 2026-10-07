-- N156 M3: 덧붙이기 전용 잠금 (클라우드 탐 초안 2026-10-07)
-- 이 표들의 수정·삭제·비우기를 DB가 막는다. 서비스 키가 있어도 막힌다(키가 새도 로그가 안 지워진다).
-- 적용 순서(중요): import_ops_tables.py가 로그 표를 "비우고 다시 채움"에서 "DB에 없는 줄만 이어 붙임"으로 바뀌어 안정된 뒤에만 적용한다.
--                  순서가 뒤집히면 가져오기가 delete에서 멈춘다.
-- 관리자 우회(긴급): alter table <표> disable trigger <표>_ro_row; 한 뒤 작업하고 enable trigger로 되돌린다(기록을 남길 것).
-- 되돌리기: tools/db/rollback_N156.sql 의 M3 절.

begin;

create or replace function block_mutation() returns trigger
language plpgsql as $$
begin
  raise exception 'append-only table: % on % is not allowed', tg_op, tg_table_name
    using errcode = 'insufficient_privilege';
end $$;

do $$
declare
  t text;
  tbls text[] := array['agent_calls', 'gpu_gate_log', 'vertex_usage',
                       'task_events', 'ingest_runs', 'metrics_snapshots', 'quota_snapshots'];
begin
  foreach t in array tbls loop
    if to_regclass(format('public.%I', t)) is null then
      raise notice 'skip (table missing): %', t;
      continue;
    end if;
    execute format('drop trigger if exists %I on %I', t || '_ro_row', t);
    execute format('create trigger %I before update or delete on %I for each row execute function block_mutation()', t || '_ro_row', t);
    execute format('drop trigger if exists %I on %I', t || '_ro_stmt', t);
    execute format('create trigger %I before truncate on %I for each statement execute function block_mutation()', t || '_ro_stmt', t);
  end loop;
end $$;

commit;
