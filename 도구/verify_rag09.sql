-- 검수 확정 후 다시 임베딩하기(RAG-09) 가 실제로 돌았는지 확인한다.
--
-- 사용법 (Tasqra 폴더에서):
--   docker compose exec -T db psql -U tasqra -d tasqra -f - < ..\..\deliver\도구\verify_rag09.sql
-- 또는 내용을 붙여넣기:
--   docker compose exec db psql -U tasqra -d tasqra
--
-- 핵심 판정 근거: 청크의 text_version 이 extracted_texts.text_version 보다
-- 작으면 본문이 수정됐는데 재청킹이 안 된 것이다.
-- (models/chunk.py 의 ix_chunk_stale 인덱스가 이 조회용이다)

\echo '=== 1. 문서별 본문 판 vs 청크 판 ==='
SELECT
    d.id                                 AS 문서id,
    left(d.filename, 28)                 AS 파일명,
    d.review_status                       AS 검수상태,
    e.text_version                        AS 본문판,
    e.char_count                          AS 본문자수,
    count(c.id)                           AS 청크수,
    min(c.text_version)                   AS 청크최소판,
    max(c.text_version)                   AS 청크최대판,
    CASE
        WHEN count(c.id) = 0                          THEN '청크없음'
        WHEN min(c.text_version) < e.text_version     THEN '낡음 <- 재청킹 안 됨'
        WHEN min(c.text_version) <> max(c.text_version) THEN '섞임 <- 중간에 끊김'
        WHEN min(c.text_version) > e.text_version     THEN '이상 <- 청크가 본문보다 새로움'
        ELSE '최신'
    END                                   AS 판정
FROM documents d
JOIN extracted_texts e ON e.document_id = d.id
LEFT JOIN document_chunks c ON c.document_id = d.id
GROUP BY d.id, d.filename, d.review_status, e.text_version, e.char_count
ORDER BY d.id;

\echo ''
\echo '=== 2. 한 문서에 모델이 섞여 있지 않은지 ==='
-- 섞여 있으면 검색이 서로 다른 벡터 공간의 거리를 비교한다. 에러 없이 틀린
-- 숫자가 나오므로 눈으로 확인해야 한다.
SELECT document_id AS 문서id, embedding_model AS 모델, text_version AS 판, count(*) AS 청크수
FROM document_chunks
GROUP BY document_id, embedding_model, text_version
HAVING count(*) > 0
ORDER BY document_id, text_version;

\echo ''
\echo '=== 3. 바꾼 글자가 청크에 들어갔는지 (marker 를 바꿔서 쓸 것) ==='
-- 검수에서 넣은 표시 문구를 여기 넣는다. 청크가 새로 만들어졌다면 나온다.
\set marker '검수확인표시'
SELECT document_id AS 문서id, seq AS 조각번호, text_version AS 판,
       left(text, 70) AS 앞부분
FROM document_chunks
WHERE text LIKE '%' || :'marker' || '%'
ORDER BY document_id, seq;

\echo ''
\echo '=== 4. 낡은 청크가 남은 문서 (stale_document_ids() 와 같은 조건) ==='
SELECT DISTINCT c.project_id AS 프로젝트id, c.document_id AS 문서id
FROM document_chunks c
JOIN extracted_texts e ON e.document_id = c.document_id
WHERE c.text_version < e.text_version
ORDER BY c.project_id, c.document_id;
