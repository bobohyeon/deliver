-- =============================================================================
-- 이 파일의 책임: 기존 금액 화면 검증 시드의 analyses.result_json에 누락된
--   items 배열을 현재 연결 행 수만큼 한 번만 보강한다. 금액 행은 수정·삭제하지 않는다.
-- 다른 파일과의 관계: seed_amount_test.sql·seed_precedent_test.sql의 과거 실행분을
--   복구한다. Tasqra의 유효 스냅샷 쿼리는 원래 추출 건수와 저장 건수를 비교한다.
-- Spring 비교: 운영 엔티티 변경 migration이 아니라 특정 테스트 fixture의 누락값을
--   보정하는 재실행 가능한 데이터 정리 스크립트다.
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- seed SQL의 출처 표식이 모두 맞고 items 키가 아직 없는 분석만 대상으로 삼는다.
-- analysis id나 프로젝트 이름으로 고르지 않아 재실행 순서와 사용자 DB id에 의존하지
-- 않는다. 현재 연결된 행 수를 원래 시드 건수로 기록하며 금액 행 자체는 건드리지 않는다.
WITH seed_counts AS (
    SELECT a.id AS analysis_id, COUNT(ai.id)::integer AS item_count
    FROM analyses a
    JOIN amount_items ai ON ai.analysis_id = a.id
    WHERE a.analyzer_type = 'amount'
      AND a.provider = 'seed'
      AND a.model_name = 'seed'
      AND a.prompt_version = 'seed-v1'
      AND a.result_json @> '{"seeded": true}'::jsonb
      AND NOT (a.result_json ? 'items')
    GROUP BY a.id
), item_arrays AS (
    SELECT
        counts.analysis_id,
        jsonb_agg('{}'::jsonb ORDER BY generated.seq) AS items
    FROM seed_counts counts
    CROSS JOIN LATERAL generate_series(1, counts.item_count) AS generated(seq)
    GROUP BY counts.analysis_id
), repaired AS (
    UPDATE analyses a
    SET result_json = jsonb_set(a.result_json, '{items}', arrays.items, true)
    FROM item_arrays arrays
    WHERE a.id = arrays.analysis_id
    RETURNING a.id
)
SELECT COUNT(*) AS repaired_analysis_count FROM repaired;

COMMIT;

-- 기대 결과:
--   seed_amount_test.sql 3개 + seed_precedent_test.sql 4개 = 최대 7개.
-- 이미 보정했거나 새 시드 SQL로 만든 분석은 items 키가 있어 재실행해도 0개다.
SELECT
    a.id AS analysis_id,
    p.name AS project_name,
    d.filename,
    jsonb_array_length(a.result_json->'items') AS extracted_count,
    COUNT(ai.id) AS stored_count,
    COUNT(ai.id) FILTER (WHERE ai.decision = 'PENDING') AS pending_count,
    COUNT(ai.id) FILTER (
        WHERE ai.decision IN ('APPROVED', 'EDITED')
    ) AS approved_count,
    COUNT(ai.id) FILTER (WHERE ai.decision = 'REJECTED') AS rejected_count
FROM analyses a
JOIN documents d ON d.id = a.document_id
JOIN projects p ON p.id = d.project_id
LEFT JOIN amount_items ai ON ai.analysis_id = a.id
WHERE a.analyzer_type = 'amount'
  AND a.provider = 'seed'
  AND a.model_name = 'seed'
  AND a.prompt_version = 'seed-v1'
  AND a.result_json @> '{"seeded": true}'::jsonb
GROUP BY a.id, p.name, d.filename
ORDER BY a.id;
