-- N156 되돌리기 (새로 만든 것만 지운다. 기존 표와 그 데이터는 건드리지 않는다)
begin;

-- M3 잠금 (있으면 먼저 푼다)
do $$
declare t text;
begin
  foreach t in array array['agent_calls', 'gpu_gate_log', 'vertex_usage', 'task_events', 'ingest_runs', 'metrics_snapshots', 'quota_snapshots'] loop
    if to_regclass(format('public.%I', t)) is not null then
      execute format('drop trigger if exists %I on %I', t || '_ro_row', t);
      execute format('drop trigger if exists %I on %I', t || '_ro_stmt', t);
    end if;
  end loop;
end $$;
drop function if exists block_mutation();

-- M2
drop view  if exists v_ingest_latest;
drop view  if exists v_tasks_unmapped_status;
drop view  if exists v_content_perf;
drop table if exists account_vault_refs;
drop table if exists quota_snapshots;
drop table if exists ingest_runs;
drop table if exists task_events;
alter table tasks drop column if exists status_family;
drop table if exists task_status;

commit;
