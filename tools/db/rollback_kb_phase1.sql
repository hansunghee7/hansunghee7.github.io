-- 지식DB 재발방지 1단계 되돌리기 (새로 만든 것만 지운다. 기존 표·데이터는 건드리지 않는다)
-- 주의: is_active/aliases/last_verified/fact_state 칸은 되돌릴 때 지우면 그 칸에 넣은 값도 사라진다.
--       데이터 보존이 우선이면 함수·색인·links만 지우고 칸(alter ... drop)은 남겨 두어도 된다.
begin;

drop function if exists kb_search(text, vector, int, boolean);

drop index if exists docs_embedding_hnsw;
drop index if exists docs_title_trgm;
drop index if exists docs_summary_trgm;
drop index if exists res_label_trgm;
drop index if exists canon_topic_trgm;

drop table if exists links;

-- 칸 제거는 선택(값 보존하려면 아래 4블록을 주석 처리한 채로 둔다)
alter table resources     drop column if exists aliases;
alter table resources     drop column if exists last_verified;
alter table resources     drop column if exists fact_state;
alter table docs          drop column if exists is_active;
alter table resources     drop column if exists is_active;
alter table canonical_map drop column if exists is_active;
alter table tasks         drop column if exists is_active;

commit;
