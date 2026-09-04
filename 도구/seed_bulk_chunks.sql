-- =============================================================================
-- 이 파일의 책임: 실행계획을 의미 있게 보기 위해 합성 청크를 대량으로 넣는다.
--
--   왜 필요한가: 청크가 수십 개면 PostgreSQL 은 인덱스를 쓰지 않고 전체를 훑는
--   것이 더 빠르다고 판단한다. 그 판단은 맞다. 하지만 그러면 우리가 확인하려는
--   "HNSW 인덱스 스캔에서 project_id 조건이 어떻게 처리되는가"를 볼 수 없다.
--   explain_rag_search.sql 은 enable_seqscan 을 끄고 계획 "모양"만 보는데,
--   실제 시간과 iterative_scan 의 동작까지 보려면 행이 충분히 있어야 한다.
--
--   벡터는 난수다. 의미가 없다. 검색 "품질"이 아니라 "실행계획"을 보려는 것이다.
--
-- ⚠ 시간이 걸린다
--   HNSW 인덱스는 삽입할 때마다 그래프를 갱신하므로 대량 삽입이 느리다.
--   6,000행에 CPU 에서 1~3분 정도 걸린다. 늘리려면 아래 ROWS 를 바꾼다.
--
-- ⚠ 반드시 정리한다
--   합성 청크가 남아 있으면 이후 검색 결과가 난수로 오염된다.
--   맨 아래 정리 문장을 꼭 실행한다 (seq >= 100000 인 것만 지운다).
--
-- 실행 방법 (PowerShell)
--   docker compose cp C:\dev\deliver\도구\seed_bulk_chunks.sql db:/tmp/bulk.sql
--   docker compose exec db psql -U postgres -d tasqra -f /tmp/bulk.sql
-- =============================================================================

\pset pager off
\timing on

\echo '합성 청크를 넣는다. 1~3분 걸린다.'

-- 합성 청크는 seq 100000 이상을 쓴다. 실제 청크(0부터)와 겹치지 않아
-- 나중에 이 조건만으로 정확히 지울 수 있다.
INSERT INTO document_chunks (
  document_id, project_id, seq, text, char_count, token_count,
  embedding, embedding_model, embedding_dim, text_version
)
SELECT
  -- 문서 1(프로젝트 1) · 문서 3(프로젝트 2) · 문서 4(프로젝트 3) 에 골고루 붙인다.
  -- 세 프로젝트에 나눠야 project_id 조건의 선택도를 볼 수 있다.
  CASE g % 3 WHEN 0 THEN 1 WHEN 1 THEN 3 ELSE 4 END,
  CASE g % 3 WHEN 0 THEN 1 WHEN 1 THEN 2 ELSE 3 END,
  100000 + g,
  '합성 청크 ' || g,
  10, 5,
  v.vec,
  'fake-hash-v1', 1024, 1
FROM generate_series(1, 6000) AS g
CROSS JOIN LATERAL (
  -- WHERE g IS NOT NULL 은 항상 참이지만 g 를 참조하게 만들어 이 서브쿼리를
  -- 행마다 다시 계산하게 한다. 참조가 없으면 PostgreSQL 이 한 번만 계산해서
  -- 6,000행이 모두 같은 벡터가 되고, 그러면 인덱스가 아무 의미가 없어진다.
  SELECT (array_agg(random()::real))::vector AS vec
  FROM generate_series(1, 1024) AS s
  WHERE g IS NOT NULL
) AS v;

\timing off
\echo ''
\echo '=== 넣은 결과 ==='
SELECT project_id AS prj,
       count(*) AS 전체,
       count(*) FILTER (WHERE seq >= 100000) AS 합성,
       count(*) FILTER (WHERE seq < 100000) AS 실제
FROM document_chunks GROUP BY 1 ORDER BY 1;

\echo ''
\echo '=== 서로 다른 벡터가 들어갔는지 확인 (같으면 인덱스가 무의미하다) ==='
SELECT count(DISTINCT left(embedding::text, 40)) AS 서로다른벡터_표본,
       count(*) AS 검사한행
FROM (SELECT embedding FROM document_chunks WHERE seq >= 100000 LIMIT 200) t;

\echo ''
\echo '=== 통계 갱신 (계획이 실제 행 수를 반영하게) ==='
ANALYZE document_chunks;

\echo ''
\echo '다음: explain_rag_search.sql 을 다시 돌린다.'
\echo '     이번에는 enable_seqscan 을 끄지 않아도 인덱스를 쓸 것이다.'
\echo ''
\echo '끝나면 반드시 정리한다:'
\echo '  DELETE FROM document_chunks WHERE seq >= 100000;'
\echo '  ANALYZE document_chunks;'
