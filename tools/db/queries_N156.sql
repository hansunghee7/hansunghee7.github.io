-- N156 운영 상태 DB 질의 모음 (클라우드 탐 초안 2026-10-07). 읽기 전용. 에이전트가 md 대신 이 질의로 읽는다.
-- 각 질의 위 한 줄이 "무엇을 알려 주나"다. 실행 전 migrate_N156.sql(M2)이 적용되어 있어야 한다.

-- Q1. 담당별 열린 일 요약(상태 family별 개수)
select owner, status_family, count(*) as n
  from tasks
 where section = 'open'
 group by owner, status_family
 order by owner, status_family;

-- Q2. 진행 중인 일 목록(번호·제목만, 세부는 그 행만 따로 읽는다)
select owner, no, left(title, 60) as title
  from tasks
 where section = 'open' and status = '진행'
 order by owner, no;

-- Q3. 상태 이름이 목록에 없는 행(task_status에 추가하거나 대장 표기를 고칠 후보)
select * from v_tasks_unmapped_status;

-- Q4. 최근 변경 이력 50건(어떤 일이 언제 어떻게 바뀌었나)
select changed_at at time zone 'Asia/Seoul' as changed_kst, owner, task_no, field, old_value, new_value, source
  from task_events
 order by changed_at desc
 limit 50;

-- Q5. 사람 손 갱신 주당 횟수(md가 바뀌어 DB에 반영된 변경 수, 다음 단계 신호 "주 1회 이하" 측정)
select date_trunc('week', changed_at at time zone 'Asia/Seoul')::date as week_kst, count(*) as changes
  from task_events
 where source = 'import-diff'
 group by 1
 order by 1 desc;

-- Q6. 가져오기 작업별 최근 7일 성공·실패 횟수와 실패율
select job,
       count(*) filter (where rc = 0)             as ok,
       count(*) filter (where rc is distinct from 0) as fail,
       round(100.0 * count(*) filter (where rc is distinct from 0) / nullif(count(*), 0), 1) as fail_pct
  from ingest_runs
 where started_at > now() - interval '7 days'
 group by job
 order by fail_pct desc nulls last;

-- Q7. 마지막 성공 이후 2시간 넘게 조용하거나 한 번도 성공하지 못한 가져오기 작업(감시 대장 보조)
select job,
       max(started_at) filter (where rc = 0) as last_ok,
       max(started_at)                       as last_try
  from ingest_runs
 group by job
having max(started_at) filter (where rc = 0) is null
    or max(started_at) filter (where rc = 0) < now() - interval '2 hours';

-- Q8. 영상 성과 상위 5(제목·한국 시각 포함)
select content_id, left(title, 40) as title, published_kst, views, likes
  from v_content_perf
 where views is not null
 order by views desc
 limit 5;

-- Q9. 오늘(한국 날짜) 호출 기록: 누가 몇 번, 평균 소요, 실패 수(agent_calls, rc != 0이 실패)
select who, count(*) as calls, round(avg(sec)::numeric, 1) as avg_sec, count(*) filter (where rc is distinct from 0) as fail
  from agent_calls
 where (called_at at time zone 'Asia/Seoul')::date = (now() at time zone 'Asia/Seoul')::date
 group by who
 order by calls desc;

-- Q10. 오늘 Vertex 추정 비용 합계(원)와 호출 수
select count(*) as calls, round(coalesce(sum(est_krw), 0)) as est_krw
  from vertex_usage
 where (used_at at time zone 'Asia/Seoul')::date = (now() at time zone 'Asia/Seoul')::date;

-- Q11. GPU 관문 결과 분포(통과·거절·반납) 최근 7일
select result, count(*) as n
  from gpu_gate_log
 where logged_at > now() - interval '7 days'
 group by result
 order by n desc;

-- Q12. 계정·자원별 가장 최근 한도(값은 없고 남은 양만)
select distinct on (account_key, resource) account_key, resource, remaining, unit, measured_at at time zone 'Asia/Seoul' as measured_kst
  from quota_snapshots
 order by account_key, resource, measured_at desc;

-- Q13. 덧붙이기 전용 잠금이 걸린 표 목록(M3 적용 확인)
select c.relname as table_name, count(*) as triggers
  from pg_trigger t
  join pg_class c on c.oid = t.tgrelid
 where not t.tgisinternal and t.tgname like '%\_ro\_%'
 group by c.relname
 order by c.relname;
