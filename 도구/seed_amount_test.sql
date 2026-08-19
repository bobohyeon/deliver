-- =============================================================================
-- 이 파일의 책임: 금액 항목(amount_items)과 과거 사업 산출내역서를 넣는다.
--   두 가지를 검증하려는 자료다.
--
--   1. 과거 유사 사업 단가 선례 검색(SRH-002-3)
--      같은 항목명(특급기술자·고급기술자·중급기술자)이 현재 사업과 과거 사업에
--      다른 단가로 들어 있다. "특급기술자 단가" 로 검색하면 두 프로젝트가 나오고
--      단가를 비교할 수 있어야 한다.
--
--   2. AmountItem 모델과 리비전 0015 가 실제로 동작하는가
--      unit_price · category 를 처음 쓰는 자료다. 제약이 값을 거부하는지,
--      모델로 조회가 되는지, 수량x단가 검산(AMT-002-1)이 불일치를 잡는지 본다.
--
-- 다른 파일과의 관계: 도구/seed_rag_test.sql 이 먼저 실행되어 있어야 한다.
--   그 파일이 만든 프로젝트 3개와 문서 4개를 전제로 한다.
--     [TEST] 기초과학연구원 ...   = 현재 사업 (내 멤버십)
--     [TEST] 중앙보훈병원 ...     = 과거 사업 (내 멤버십)  <- 여기에 문서를 더한다
--     [TEST] 남의 프로젝트 ...    = 격리 검증용
--
-- 일부러 심어 둔 오류 하나
--   과거 산출내역서의 중급기술자가 6인월 x 5,400,000 = 32,400,000 이어야 하는데
--   문서에는 32,000,000 으로 적혀 있다. amount_calculator.verify_line() 이
--   400,000 차이를 잡아야 한다. 문서 합계는 32,000,000 기준으로 맞춰 뒀으므로
--   check_total() 은 통과한다 -- 두 검사를 따로 확인할 수 있다.
--
-- 재실행 안전: 맨 앞에서 이 파일이 넣은 것만 지운다. seed_rag_test.sql 의
--   자료는 건드리지 않는다.
--
-- 실행 방법 (PowerShell)
--   docker compose cp C:\dev\deliver\도구\seed_amount_test.sql db:/tmp/seed_amount.sql
--   docker compose exec db psql -U postgres -d tasqra -f /tmp/seed_amount.sql
--
--   파이프로 넘기면 한글이 깨진다. cp 로 넣고 -f 로 읽어야 한다.
-- =============================================================================

BEGIN;

-- ── 정리 ────────────────────────────────────────────────────────────────────
-- 과거 산출내역서 문서를 지우면 extracted_texts · analyses · amount_items ·
-- document_chunks 가 CASCADE 로 함께 지워진다.
DELETE FROM documents WHERE filename = '[TEST] 과거_산출내역서.pdf';

-- 현재 산출내역서에 붙였던 금액 분석만 지운다. 문서 자체는 남긴다.
DELETE FROM analyses
WHERE analyzer_type = 'amount'
  AND document_id IN (SELECT id FROM documents WHERE filename LIKE '[TEST]%');


-- ── 과거 사업 산출내역서 문서 ────────────────────────────────────────────────
INSERT INTO documents (
  project_id, filename, storage_path, file_type, file_size,
  status, review_status, extraction_strategy, document_type
)
VALUES
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 중앙보훈%'),
   '[TEST] 과거_산출내역서.pdf', '/app/uploads/test-cost-past.pdf', 'pdf', 8192,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', NULL);


-- ── 과거 사업 본문 ──────────────────────────────────────────────────────────
-- 항목명은 현재 사업과 같게 두고 단가만 다르게 했다. 그래야 "같은 항목의 과거
-- 단가" 검색이 성립한다. 제목을 여러 개 두어 청킹이 조각을 나눈다.
INSERT INTO extracted_texts (document_id, content, text_char_count, ocr_char_count,
                             extract_method, text_version, is_confirmed)
SELECT d.id, $txt$통합경영정보시스템 유지관리 용역 산출내역서

1. 직접인건비
특급기술자	3인월	8,800,000	26,400,000
고급기술자	5인월	6,900,000	34,500,000
중급기술자	6인월	5,400,000	32,000,000
직접인건비 합계			92,900,000

2. 제경비
제경비는 직접인건비의 110퍼센트로 산정한다.
제경비			102,190,000

3. 기술료
기술료는 직접인건비와 제경비 합계의 20퍼센트로 산정한다.
기술료			39,018,000

4. 합계
공급가액			234,108,000
부가가치세			23,410,800
총액			257,518,800

5. 산출 근거
전년도 유지관리 용역의 단가를 기준으로 물가상승률을 반영하여 산정하였다.
인건비 단가는 한국소프트웨어산업협회 공표 노임단가를 적용한다.$txt$,
       700, 0, 'TEXT', 1, true
FROM documents d WHERE d.filename = '[TEST] 과거_산출내역서.pdf';


-- ── 금액 분석 행 (analyses) ─────────────────────────────────────────────────
-- amount_items.analysis_id 가 not null 이라 먼저 있어야 한다. 실제로는 LLM
-- 추출(AMT-001-1)이 만들지만 아직 미구현이라 시드로 넣는다.
-- provider·model_name 에 seed 를 적어 두면 나중에 실제 분석과 구별된다.
INSERT INTO analyses (document_id, analyzer_type, result_json, provider, model_name,
                      prompt_version, source_text_revision)
SELECT d.id, 'amount',
       '{"seeded": true, "note": "seed_amount_test.sql 이 넣은 자료"}'::jsonb,
       'seed', 'seed', 'seed-v1', 1
FROM documents d
WHERE d.filename IN ('[TEST] 산출내역서.pdf', '[TEST] 과거_산출내역서.pdf');


-- ── 금액 항목 — 현재 사업 ───────────────────────────────────────────────────
-- 인건비 항목은 수량·단가가 있고, 제경비·기술료·부가세는 비율로 산정되어
-- 수량·단가가 NULL 이다. 그것이 unit_price 를 nullable 로 둔 이유다.
INSERT INTO amount_items (
  document_id, analysis_id, item_name, category, quantity, unit, unit_price,
  amount, currency, source_quote, confidence, reason, decision, source_text_revision
)
SELECT a.document_id, a.id, v.item_name, v.category, v.quantity, v.unit,
       v.unit_price, v.amount, 'KRW', v.source_quote, 0.95, v.reason,
       'PENDING', 1
FROM analyses a
JOIN documents d ON d.id = a.document_id
CROSS JOIN (VALUES
  ('특급기술자', 'DIRECT_LABOR', 3::numeric, '인월', 9500000::numeric, 28500000::numeric,
   '특급기술자	3인월	9,500,000	28,500,000', '산출내역서 1. 직접인건비 표의 첫 행'),
  ('고급기술자', 'DIRECT_LABOR', 6::numeric, '인월', 7200000::numeric, 43200000::numeric,
   '고급기술자	6인월	7,200,000	43,200,000', '산출내역서 1. 직접인건비 표의 둘째 행'),
  ('중급기술자', 'DIRECT_LABOR', 4::numeric, '인월', 5800000::numeric, 23200000::numeric,
   '중급기술자	4인월	5,800,000	23,200,000', '산출내역서 1. 직접인건비 표의 셋째 행'),
  ('제경비', 'OVERHEAD', NULL::numeric, NULL, NULL::numeric, 104390000::numeric,
   '제경비는 직접인건비의 110퍼센트로 산정한다.', '비율 산정 항목이라 수량·단가가 없다'),
  ('기술료', 'TECH_FEE', NULL::numeric, NULL, NULL::numeric, 39858000::numeric,
   '기술료는 직접인건비와 제경비 합계의 20퍼센트로 산정한다.', '비율 산정 항목'),
  ('부가가치세', 'VAT', NULL::numeric, NULL, NULL::numeric, 23914800::numeric,
   '부가가치세			23,914,800', '항목 합계에서 제외해야 하는 항목')
) AS v(item_name, category, quantity, unit, unit_price, amount, source_quote, reason)
WHERE a.analyzer_type = 'amount' AND d.filename = '[TEST] 산출내역서.pdf';


-- ── 금액 항목 — 과거 사업 ───────────────────────────────────────────────────
-- 중급기술자에 일부러 불일치를 심었다. 6 x 5,400,000 = 32,400,000 인데 문서에는
-- 32,000,000 으로 적혀 있다. verify_line() 이 400,000 차이를 잡아야 한다.
INSERT INTO amount_items (
  document_id, analysis_id, item_name, category, quantity, unit, unit_price,
  amount, currency, source_quote, confidence, reason, decision, source_text_revision
)
SELECT a.document_id, a.id, v.item_name, v.category, v.quantity, v.unit,
       v.unit_price, v.amount, 'KRW', v.source_quote, 0.92, v.reason,
       -- 과거 사업은 이미 끝난 사업이라 사람이 검토를 마친 상태로 둔다.
       -- 단가 선례(SRH-002-3)는 승인된 것만 쓴다 — AMT-001-2 의
       -- "승인 전에는 어디에도 반영되지 않고" 를 지키려는 것이다.
       -- 현재 사업(위 블록)은 PENDING 이라 선례에 나오지 않아야 한다.
       'APPROVED', 1
FROM analyses a
JOIN documents d ON d.id = a.document_id
CROSS JOIN (VALUES
  ('특급기술자', 'DIRECT_LABOR', 3::numeric, '인월', 8800000::numeric, 26400000::numeric,
   '특급기술자	3인월	8,800,000	26,400,000', '과거 사업 직접인건비 첫 행'),
  ('고급기술자', 'DIRECT_LABOR', 5::numeric, '인월', 6900000::numeric, 34500000::numeric,
   '고급기술자	5인월	6,900,000	34,500,000', '과거 사업 직접인건비 둘째 행'),
  ('중급기술자', 'DIRECT_LABOR', 6::numeric, '인월', 5400000::numeric, 32000000::numeric,
   '중급기술자	6인월	5,400,000	32,000,000', '문서에 적힌 금액을 그대로 담았다. 수량x단가와 400,000 차이가 있다'),
  ('제경비', 'OVERHEAD', NULL::numeric, NULL, NULL::numeric, 102190000::numeric,
   '제경비는 직접인건비의 110퍼센트로 산정한다.', '비율 산정 항목'),
  ('기술료', 'TECH_FEE', NULL::numeric, NULL, NULL::numeric, 39018000::numeric,
   '기술료는 직접인건비와 제경비 합계의 20퍼센트로 산정한다.', '비율 산정 항목'),
  ('부가가치세', 'VAT', NULL::numeric, NULL, NULL::numeric, 23410800::numeric,
   '부가가치세			23,410,800', '항목 합계에서 제외해야 하는 항목')
) AS v(item_name, category, quantity, unit, unit_price, amount, source_quote, reason)
WHERE a.analyzer_type = 'amount' AND d.filename = '[TEST] 과거_산출내역서.pdf';

-- ── 금액 항목 — 남의 프로젝트 (격리 검증용) ─────────────────────────────────
-- 내가 멤버가 아닌 프로젝트다. 단가 선례(SRH-002-3)에 **절대 나오면 안 된다.**
-- 항목명을 같게 두고 단가를 터무니없는 값(99,000,000)으로 넣어, 격리가 깨지면
-- 결과에서 즉시 눈에 띄게 한다. seed_rag_test.sql 이 "대금 지급" 내용을 남의
-- 프로젝트에도 넣어 둔 것과 같은 방식이다.
--
-- decision 을 APPROVED 로 두는 것이 중요하다. PENDING 이면 승인 필터에서
-- 걸려서 격리를 검증하지 못한다 -- 격리 때문에 빠진 것인지 승인 때문에 빠진
-- 것인지 구별할 수 없기 때문이다.
INSERT INTO analyses (document_id, analyzer_type, result_json, provider, model_name,
                      prompt_version, source_text_revision)
SELECT d.id, 'amount',
       '{"seeded": true, "note": "격리 검증용 - 결과에 나오면 안 된다"}'::jsonb,
       'seed', 'seed', 'seed-v1', 1
FROM documents d WHERE d.filename = '[TEST] 남의공고.pdf';

INSERT INTO amount_items (
  document_id, analysis_id, item_name, category, quantity, unit, unit_price,
  amount, currency, source_quote, confidence, reason, decision, source_text_revision
)
SELECT a.document_id, a.id, '특급기술자', 'DIRECT_LABOR', 1, '인월',
       99000000, 99000000, 'KRW', '격리가 깨지면 이 값이 보인다', 0.99,
       '남의 프로젝트 자료. 단가 선례에 나오면 격리가 깨진 것이다.',
       'APPROVED', 1
FROM analyses a
JOIN documents d ON d.id = a.document_id
WHERE a.analyzer_type = 'amount' AND d.filename = '[TEST] 남의공고.pdf';

COMMIT;


-- ── 확인 ────────────────────────────────────────────────────────────────────
\echo ''
\echo '=== 1. 넣은 금액 항목 ==='
SELECT p.name AS 프로젝트, d.filename AS 문서, ai.item_name AS 항목,
       ai.category AS 원가구분, ai.quantity AS 수량, ai.unit_price AS 단가,
       ai.amount AS 금액
FROM amount_items ai
JOIN documents d ON d.id = ai.document_id
JOIN projects p ON p.id = d.project_id
ORDER BY p.name, d.filename, ai.id;

\echo ''
\echo '=== 2. 수량x단가 검산 — 중급기술자(과거)에서 400,000 차이가 나야 한다 ==='
SELECT d.filename AS 문서, ai.item_name AS 항목,
       ai.quantity * ai.unit_price AS 계산값, ai.amount AS 문서값,
       ai.quantity * ai.unit_price - ai.amount AS 차이,
       CASE WHEN ai.quantity IS NULL OR ai.unit_price IS NULL THEN '검산불가(비율산정)'
            WHEN ai.quantity * ai.unit_price = ai.amount THEN '일치'
            ELSE '불일치' END AS 판정
FROM amount_items ai
JOIN documents d ON d.id = ai.document_id
ORDER BY d.filename, ai.id;

\echo ''
\echo '=== 3. 같은 항목의 프로젝트별 단가 (SRH-002-3 이 보여줄 것) ==='
SELECT ai.item_name AS 항목, p.name AS 프로젝트, ai.unit_price AS 단가
FROM amount_items ai
JOIN documents d ON d.id = ai.document_id
JOIN projects p ON p.id = d.project_id
WHERE ai.unit_price IS NOT NULL
ORDER BY ai.item_name, ai.unit_price DESC;

\echo ''
\echo '=== 4. 원가구분별 집계 (부가세 제외) ==='
SELECT p.name AS 프로젝트, ai.category AS 원가구분, sum(ai.amount) AS 합계
FROM amount_items ai
JOIN documents d ON d.id = ai.document_id
JOIN projects p ON p.id = d.project_id
WHERE ai.category <> 'VAT'
GROUP BY p.name, ai.category
ORDER BY p.name, ai.category;
