-- =============================================================================
-- 이 파일의 책임: 리비전 0014(document_chunks.project_id 역정규화)의 근거를
--   실행계획으로 확인한다. 근거는 이것이었다.
--
--     "project_id 를 같은 테이블 컬럼으로 두어야 hnsw.iterative_scan 이 그 조건을
--      인덱스 스캔 단계에서 평가한다. 조인 조건이면 해당되지 않고, 프로젝트가
--      작을 때 에러 없이 결과가 적게 나오는 방식으로 실패한다."
--
--   청크가 0행이던 동안에는 확인할 수 없었다. 이제 확인한다.
--
--   함께 확인할 것 하나 더: 전체 검색은 project_id IN (1, 2) 가 된다.
--   IN 목록도 등호(=)처럼 인덱스 스캔 단계로 내려가는지는 문서로 확인하지
--   못했다. 계획을 눈으로 비교한다.
--
-- ⚠ 작은 데이터의 함정
--   행이 수십 개뿐이면 PostgreSQL 은 인덱스를 쓰지 않고 전체를 훑는 것이 더
--   빠르다고 판단한다(맞는 판단이다). 그러면 우리가 보려는 계획이 안 나온다.
--   그래서 여기서는 enable_seqscan 을 끄고 "인덱스를 쓴다면 어떤 모양인지"를 본다.
--   실제 성능 수치는 도구/seed_bulk_chunks.sql 로 합성 청크를 넣은 뒤 봐야 한다.
--
-- 읽는 방법 (2026-08-18 실측으로 정정)
--   project_id 가 "Index Cond" 로 나오기를 기대하면 안 된다. HNSW 인덱스에는 벡터
--   컬럼만 들어 있어 구조적으로 불가능하다. pgvector 문서대로 근사 인덱스는
--   ef_search 개의 후보를 먼저 만들고 그 다음 WHERE 를 적용하므로,
--   project_id 는 항상 "Filter" 로 나온다. 그것이 정상이다.
--
--   보아야 할 것은 그 Filter 가 어느 노드에 붙는가다.
--     "Index Scan using ix_chunk_vec" 노드의 Filter  -> 좋다. 살아남은 행이 부족하면
--                                                      iterative_scan 이 더 훑는다
--     그 위 노드의 "Join Filter"                     -> 나쁘다. HNSW 는 부족한 줄
--                                                      모르고 결과가 조용히 적어진다
--     "Order By: (embedding <=> ...)"                 -> 벡터 인덱스로 정렬했다
--     "Rows Removed by Filter: N"                     -> 선택도에 비례하면 정상 동작
--     "Sort Method: top-N heapsort"                   -> 인덱스를 못 쓰고 메모리 정렬
--
-- 실행 방법 (PowerShell)
--   docker compose cp C:\dev\deliver\도구\explain_rag_search.sql db:/tmp/explain.sql
--   docker compose exec db psql -U postgres -d tasqra -f /tmp/explain.sql
-- =============================================================================

\pset pager off
\timing off

\echo '======================================================================'
\echo '0. 준비 — 자료 현황'
\echo '======================================================================'

SELECT project_id AS prj, count(*) AS 청크, max(embedding_model) AS 모델
FROM document_chunks GROUP BY 1 ORDER BY 1;

SELECT count(*) AS 전체청크 FROM document_chunks;

\echo ''
\echo '벡터 인덱스가 있는지'
SELECT indexname FROM pg_indexes
WHERE tablename = 'document_chunks' AND indexdef LIKE '%hnsw%';

\echo ''
\echo 'pgvector 버전 (iterative_scan 은 0.8 부터)'
SELECT extversion FROM pg_extension WHERE extname = 'vector';

-- 질의 벡터를 실제 청크에서 하나 꺼내 psql 변수에 담는다.
-- ORDER BY 안에 서브쿼리를 넣으면 계획이 달라질 수 있어 리터럴로 만든다.
SELECT embedding::text AS qvec FROM document_chunks ORDER BY id LIMIT 1
\gset

\echo ''
\echo '======================================================================'
\echo '1. 단일 프로젝트 — project_id = 1  (현재 프로젝트만 검색)'
\echo '======================================================================'

BEGIN;
SET LOCAL hnsw.iterative_scan = strict_order;
SET LOCAL hnsw.ef_search = 100;
-- 행이 적을 때 PostgreSQL 이 전체 훑기를 고르는 것을 막아, 인덱스를 쓸 때의
-- 계획 모양을 본다. 운영에서 끄는 설정이 아니다.
SET LOCAL enable_seqscan = off;

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT c.id, c.seq, c.project_id
FROM document_chunks c
WHERE c.project_id = 1
  AND c.embedding_model = 'fake-hash-v1'
ORDER BY c.embedding <=> :'qvec'::vector
LIMIT 5;
COMMIT;

\echo ''
\echo '======================================================================'
\echo '2. 여러 프로젝트 — project_id IN (1, 2)  (전체 검색)'
\echo '======================================================================'

BEGIN;
SET LOCAL hnsw.iterative_scan = strict_order;
SET LOCAL hnsw.ef_search = 100;
SET LOCAL enable_seqscan = off;

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT c.id, c.seq, c.project_id
FROM document_chunks c
WHERE c.project_id IN (1, 2)
  AND c.embedding_model = 'fake-hash-v1'
ORDER BY c.embedding <=> :'qvec'::vector
LIMIT 5;
COMMIT;

\echo ''
\echo '======================================================================'
\echo '3. 대조군 — 조인으로 걸렀다면 어땠을까 (0014 없이 했을 경우)'
\echo '======================================================================'
\echo '  documents 를 조인해서 project_id 를 거는 방식이다.'
\echo '  이 계획에서는 조건이 document_chunks 스캔 단계에 없다는 것을 본다.'

BEGIN;
SET LOCAL hnsw.iterative_scan = strict_order;
SET LOCAL hnsw.ef_search = 100;
SET LOCAL enable_seqscan = off;

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT c.id, c.seq, d.project_id
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.project_id = 1
  AND c.embedding_model = 'fake-hash-v1'
ORDER BY c.embedding <=> :'qvec'::vector
LIMIT 5;
COMMIT;

\echo ''
\echo '======================================================================'
\echo '4. 격리 확인 — 결과에 프로젝트 3 이 섞이지 않는가'
\echo '======================================================================'
\echo '  "대금 지급" 은 프로젝트 1 과 3 에 모두 있다. 아래에서 3 이 나오면'
\echo '  격리가 깨진 것이다. 다만 가짜 임베더는 의미가 없으므로 여기서는'
\echo '  "조건이 실제로 걸리는가"만 본다.'

BEGIN;
SET LOCAL hnsw.iterative_scan = strict_order;
SET LOCAL hnsw.ef_search = 100;

SELECT c.project_id AS prj, c.document_id AS doc, c.seq,
       round((1 - (c.embedding <=> :'qvec'::vector))::numeric, 4) AS 유사도,
       left(replace(c.text, E'\n', ' '), 45) AS 앞부분
FROM document_chunks c
WHERE c.project_id IN (1, 2)
  AND c.embedding_model = 'fake-hash-v1'
ORDER BY c.embedding <=> :'qvec'::vector
LIMIT 10;
COMMIT;

\echo ''
\echo '조건 없이 뽑으면 프로젝트 3 도 나온다 (조건이 일하고 있음을 대조로 확인)'
SELECT c.project_id AS prj, count(*) AS 청크 FROM document_chunks c GROUP BY 1 ORDER BY 1;

\echo ''
\echo '======================================================================'
\echo '읽는 방법'
\echo '======================================================================'
\echo '  1번과 2번은 실측에서 계획이 같았다 (둘 다 ix_chunk_vec 스캔 + Filter).'
\echo '  3번(조인)에서는 조건이 document_chunks 스캔 노드 밖에 붙는다.'
\echo '    Rows Removed by Join Filter 로 나타난다. 그것이 0014 를 넣은 이유다.'
\echo '  project_id 가 Index Cond 로 나오는 일은 없다 - HNSW 에는 벡터만 색인된다.'
\echo ''
\echo '  행이 적어 계획이 무의미해 보이면 도구/seed_bulk_chunks.sql 로'
\echo '  합성 청크를 넣고 다시 돌린다.'
