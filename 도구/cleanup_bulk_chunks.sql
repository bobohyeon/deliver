-- =============================================================================
-- 이 파일의 책임: seed_bulk_chunks.sql 로 넣은 합성 청크를 지운다.
--   합성 청크의 벡터는 난수다. 남겨 두면 이후 검색 결과가 오염되고, 왜 엉뚱한
--   것이 나오는지 찾기 어려워진다. 실행계획 확인이 끝나면 바로 지운다.
--
--   seq >= 100000 인 것만 지운다. 실제 청크는 문서마다 0부터 매겨지므로
--   (chunking.py 의 seq 는 0 부터 1씩 증가) 절대 겹치지 않는다.
--
-- 실행 방법 (PowerShell)
--   docker compose cp C:\dev\deliver\도구\cleanup_bulk_chunks.sql db:/tmp/cleanup.sql
--   docker compose exec db psql -U postgres -d tasqra -f /tmp/cleanup.sql
-- =============================================================================

\pset pager off

\echo '=== 지우기 전 ==='
SELECT count(*) FILTER (WHERE seq >= 100000) AS 합성,
       count(*) FILTER (WHERE seq < 100000) AS 실제
FROM document_chunks;

DELETE FROM document_chunks WHERE seq >= 100000;

ANALYZE document_chunks;

\echo ''
\echo '=== 지운 후 ==='
SELECT project_id AS prj, document_id AS doc, count(*) AS 청크
FROM document_chunks GROUP BY 1, 2 ORDER BY 1, 2;

SELECT count(*) AS 남은_합성청크 FROM document_chunks WHERE seq >= 100000;
