-- =============================================================================
-- 과거 단가 선례 화면(SRH-002-3) 확인용 시드
--
-- 무엇을 확인하려는 것인가
--   기존 seed_amount_test.sql 은 과거 사업이 **한 건**이라 선례가 1건만 나온다.
--   그러면 최저·중앙값·최고가 모두 같은 값이어서 요약 네 칸이 제 역할을 하는지,
--   단가 숫자가 세로로 정렬되는지 확인할 수 없다. 선례를 여럿으로 만든다.
--
-- 기대 결과 (현재 프로젝트 = [TEST] 기초과학연구원, 검색어 = 특급기술자)
--
--   | 프로젝트            | 단가       | decision  | 결과에 |
--   |---------------------|-----------|-----------|--------|
--   | 선례C 지방재정       | 9,200,000 | APPROVED  | 나온다 |
--   | (기존) 중앙보훈      | 8,800,000 | APPROVED  | 나온다 |
--   | 선례B 국립박물관     | 7,500,000 | EDITED    | 나온다 |
--   | 선례A 도로공사       | 6,900,000 | APPROVED  | 나온다 |
--   | 선례D 우체국         | 12,000,000| PENDING   | 안 나온다 |
--   | 선례D 우체국         | 11,000,000| REJECTED  | 안 나온다 |
--   | (기존) 남의 프로젝트 | 99,000,000| APPROVED  | 안 나온다 (격리) |
--
--   선례 4건 · 최저 6,900,000 · 최고 9,200,000
--   중앙값 = (7,500,000 + 8,800,000) / 2 = **8,150,000**
--
--   중앙값이 8,150,000 인 것이 이 시드의 요점이다. **목록에 없는 값**이므로
--   화면이 값을 고른 것이 아니라 계산한 결과임이 증명된다. 그리고 4건(짝수)이라
--   median() 의 나눗셈 분기를 지난다 — Decimal 나눗셈이 어긋나면 여기서 드러난다.
--
-- 다른 검색어로 확인할 것
--   '라이선스'  -> 1건. (1식 단가) 450,000 · 12식 기준 5,400,000
--                    인월 항목이 없으므로 **인월 설명이 뜨지 않아야** 한다
--   '임차료'    -> 1건. (1월 단가) 1,200,000 · 2.5월 기준 3,000,000
--                    수량이 2.5 다 — 소수 수량이 2.5 로 나오는지 본다
--   '제경비'    -> 0건. 단가가 NULL 이라 선례가 될 수 없다
--                    "단가 선례를 찾지 못했습니다" 안내가 떠야 한다
--
-- 재실행 안전
--   이 파일이 넣은 것만 지운다. 프로젝트 이름을 '[TEST] 선례' 로 시작하게 해서
--   seed_rag_test.sql 의 '[TEST] 기초과학%' · '[TEST] 중앙보훈%' ·
--   '[TEST] 남의%' 와 seed_amount_test.sql 의 자료를 건드리지 않는다.
--
-- 선행
--   seed_rag_test.sql -> seed_amount_test.sql -> 이 파일 순서로 넣는다.
--   앞의 둘이 사용자와 기존 프로젝트를 만든다.
--
-- 실행 방법 (PowerShell)
--   docker compose cp C:\dev\deliver\도구\seed_precedent_test.sql db:/tmp/seed_prec.sql
--   docker compose exec db psql -U postgres -d tasqra -f /tmp/seed_prec.sql
--
--   파이프로 넘기면 한글이 깨진다. cp 로 넣고 -f 로 읽어야 한다.
--   DB 사용자는 postgres 다 (tasqra 는 DB 이름).
-- =============================================================================

BEGIN;

-- ── 정리 ────────────────────────────────────────────────────────────────────
-- 프로젝트를 지우면 documents -> analyses -> amount_items 까지 CASCADE 로
-- 함께 지워진다. '[TEST] 선례' 로 시작하는 것만 지운다.
DELETE FROM projects WHERE name LIKE '[TEST] 선례%';


-- ── 프로젝트 4개 ────────────────────────────────────────────────────────────
-- 주 사용자가 OWNER 다. 선례는 "내가 멤버인 다른 프로젝트" 에서 찾으므로
-- 멤버가 아니면 범위에 들어오지 않는다.
--
-- test_other(남의 계정)는 seed_rag_test.sql 이 만든다. 여기서는 쓰지 않는다 —
-- 격리 검증은 그 파일의 '[TEST] 남의 프로젝트' 가 이미 하고 있다.
INSERT INTO projects (name, description, owner_id, status)
VALUES
  ('[TEST] 선례A 도로공사 정보화전략계획', '단가 선례 — 최저값',
   (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1), 'ACTIVE'),
  ('[TEST] 선례B 국립박물관 소장품관리시스템', '단가 선례 — EDITED 도 선례에 든다',
   (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1), 'ACTIVE'),
  ('[TEST] 선례C 지방재정 통합포털 고도화', '단가 선례 — 최고값',
   (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1), 'ACTIVE'),
  ('[TEST] 선례D 우체국 물류정보 (승인 전·거절)', '결과에 나오지 않아야 하는 것',
   (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1), 'ACTIVE');

INSERT INTO project_members (project_id, user_id, role)
SELECT p.id, p.owner_id, 'OWNER'
FROM projects p
WHERE p.name LIKE '[TEST] 선례%';


-- ── 문서 4개 ────────────────────────────────────────────────────────────────
-- storage_path 에 실제 파일이 없으므로 다운로드는 되지 않는다. 선례 조회는
-- 파일을 읽지 않고 amount_items 만 보므로 문제되지 않는다.
INSERT INTO documents (
  project_id, filename, storage_path, file_type, file_size,
  status, review_status, extraction_strategy, document_type
)
VALUES
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 선례A%'),
   '[TEST] 선례A_산출내역서.pdf', '/app/uploads/test-prec-a.pdf', 'pdf', 8192,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', 'COST_SHEET'),
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 선례B%'),
   '[TEST] 선례B_산출내역서.pdf', '/app/uploads/test-prec-b.pdf', 'pdf', 8192,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', 'COST_SHEET'),
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 선례C%'),
   '[TEST] 선례C_산출내역서.pdf', '/app/uploads/test-prec-c.pdf', 'pdf', 8192,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', 'COST_SHEET'),
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 선례D%'),
   '[TEST] 선례D_산출내역서.pdf', '/app/uploads/test-prec-d.pdf', 'pdf', 8192,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', 'COST_SHEET');


-- ── 분석 ────────────────────────────────────────────────────────────────────
-- amount_items.analysis_id 가 NOT NULL 이라 문서마다 분석 행이 하나 필요하다.
-- provider·model_name 에 seed 를 적어 두면 실제 분석과 구별된다.
INSERT INTO analyses (document_id, analyzer_type, result_json, provider, model_name,
                      prompt_version, source_text_revision)
SELECT d.id, 'amount',
       '{"seeded": true, "note": "seed_precedent_test.sql 이 넣은 자료"}'::jsonb,
       'seed', 'seed', 'seed-v1', 1
FROM documents d
WHERE d.filename LIKE '[TEST] 선례%_산출내역서.pdf';


-- ── 금액 항목 ───────────────────────────────────────────────────────────────
-- decided_at 을 채운다. 승인·거절된 항목은 누가 언제 판단했는지가 남아야
-- 하고(AMT-001-2), 비워 두면 "승인됐는데 판단 시각이 없다" 는 모순이 된다.
-- PENDING 만 NULL 이다.
INSERT INTO amount_items (
  document_id, analysis_id, item_name, category, quantity, unit, unit_price,
  amount, currency, source_quote, confidence, reason, decision,
  decided_by, decided_at, source_text_revision
)
SELECT a.document_id, a.id, v.item_name, v.category, v.quantity, v.unit,
       v.unit_price, v.amount, 'KRW', v.source_quote, 0.95, v.reason, v.decision,
       CASE WHEN v.decision = 'PENDING' THEN NULL
            ELSE (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1)
       END,
       CASE WHEN v.decision = 'PENDING' THEN NULL ELSE now() END,
       1
FROM analyses a
JOIN documents d ON d.id = a.document_id
JOIN (VALUES
  -- ── 선례A 도로공사 — 최저 단가 ────────────────────────────────────────────
  ('[TEST] 선례A_산출내역서.pdf', '특급기술자', 'DIRECT_LABOR',
   4::numeric, '인월', 6900000::numeric, 27600000::numeric,
   '특급기술자	4인월	6,900,000	27,600,000',
   '산출내역서 1. 직접인건비 표의 첫 행', 'APPROVED'),
  -- 단위가 인월이 아닌 항목. 화면이 (1식 단가) 로 표시하는지 확인한다.
  ('[TEST] 선례A_산출내역서.pdf', '소프트웨어 라이선스', 'MATERIAL',
   12::numeric, '식', 450000::numeric, 5400000::numeric,
   '소프트웨어 라이선스	12식	450,000	5,400,000',
   '산출내역서 3. 재료비 표의 첫 행', 'APPROVED'),

  -- ── 선례B 국립박물관 — EDITED 도 선례에 든다 ──────────────────────────────
  -- APPROVED_DECISIONS = ("APPROVED", "EDITED") 이다. 사람이 값을 고쳐 확정한
  -- 것이라 오히려 신뢰도가 높다고 보고 포함한다.
  ('[TEST] 선례B_산출내역서.pdf', '특급기술자', 'DIRECT_LABOR',
   2::numeric, '인월', 7500000::numeric, 15000000::numeric,
   '특급기술자	2인월	7,500,000	15,000,000',
   'AI 가 7,300,000 으로 읽었으나 사람이 원문 대조 후 7,500,000 으로 고쳤다', 'EDITED'),
  -- 수량이 소수다. 화면이 2.5000 을 2.5 로 줄이는지 확인한다.
  ('[TEST] 선례B_산출내역서.pdf', '사무실 임차료', 'EXPENSE',
   2.5::numeric, '월', 1200000::numeric, 3000000::numeric,
   '사무실 임차료	2.5월	1,200,000	3,000,000',
   '산출내역서 2. 경비 표의 둘째 행', 'APPROVED'),

  -- ── 선례C 지방재정 — 최고 단가 ────────────────────────────────────────────
  ('[TEST] 선례C_산출내역서.pdf', '특급기술자', 'DIRECT_LABOR',
   5::numeric, '인월', 9200000::numeric, 46000000::numeric,
   '특급기술자	5인월	9,200,000	46,000,000',
   '산출내역서 1. 직접인건비 표의 첫 행', 'APPROVED'),
  -- 단가가 NULL 인 항목. 비율로 산정되어 단가가 원래 없다.
  -- 선례 조회의 unit_price IS NOT NULL 조건에 걸려 제외돼야 한다.
  ('[TEST] 선례C_산출내역서.pdf', '제경비', 'OVERHEAD',
   NULL::numeric, NULL, NULL::numeric, 50600000::numeric,
   '제경비는 직접인건비의 110퍼센트로 산정한다.',
   '비율 산정 항목이라 수량·단가가 없다', 'APPROVED'),

  -- ── 선례D 우체국 — 결과에 나오지 않아야 하는 것 둘 ────────────────────────
  -- 같은 항목이 두 번 있는 것은 재분석으로 제안이 둘 남은 상황을 흉내낸 것이다.
  -- 하나는 사람이 거절했고 하나는 아직 보지 않았다.
  --
  -- 둘 다 단가가 다른 선례보다 **높게** 두었다. 격리가 깨지면 최고 단가가
  -- 12,000,000 으로 바뀌어 요약에서 바로 보인다. 낮게 두면 최저값에만
  -- 영향을 줘서 눈에 덜 띈다.
  ('[TEST] 선례D_산출내역서.pdf', '특급기술자', 'DIRECT_LABOR',
   3::numeric, '인월', 12000000::numeric, 36000000::numeric,
   '특급기술자	3인월	12,000,000	36,000,000',
   '아직 사람이 검토하지 않은 제안이다', 'PENDING'),
  ('[TEST] 선례D_산출내역서.pdf', '특급기술자', 'DIRECT_LABOR',
   2::numeric, '인월', 11000000::numeric, 22000000::numeric,
   '특급기술자	2인월	11,000,000	22,000,000',
   '원문과 맞지 않아 사람이 거절했다', 'REJECTED')
) AS v(filename, item_name, category, quantity, unit, unit_price,
       amount, source_quote, reason, decision)
  ON v.filename = d.filename
WHERE a.analyzer_type = 'amount';


-- ── 확인 ────────────────────────────────────────────────────────────────────
-- 넣은 결과를 바로 보여 준다. 화면을 열기 전에 숫자가 맞는지 여기서 걸러낸다.

\echo ''
\echo '=== 넣은 프로젝트 ==='
SELECT name FROM projects WHERE name LIKE '[TEST] 선례%' ORDER BY name;

\echo ''
\echo '=== 화면에 나올 선례 (조회 조건 네 개를 모두 적용) ==='
--
-- 조건 네 개를 서비스와 똑같이 적용한다. 처음에는 멤버십 조건을 빼고 썼는데,
-- 그러면 내가 멤버가 아닌 '[TEST] 남의 프로젝트' 의 99,000,000 이 목록에 나온다.
-- 그것을 보고 "격리가 깨졌다" 고 읽게 되는데 **사실이 아니다** — 격리는
-- amount_items 가 아니라 services/amount_precedent_service._resolve_scope() 가
-- project_members 를 보고 하는 일이다.
--
-- 확인 쿼리가 검증하지 못하는 것을 검증한다고 말하면 안 된다. 그래서 여기서
-- 멤버십과 현재 프로젝트 제외까지 그대로 흉내낸다.
SELECT p.name AS 프로젝트, ai.unit_price AS 단가, ai.quantity AS 수량,
       ai.unit AS 단위, ai.decision AS 상태
FROM amount_items ai
JOIN documents d ON d.id = ai.document_id
JOIN projects p ON p.id = d.project_id
-- (1) 내가 멤버인 프로젝트만
JOIN project_members pm ON pm.project_id = p.id
 AND pm.user_id = (SELECT id FROM users WHERE login_id <> 'test_other'
                   ORDER BY id LIMIT 1)
WHERE ai.item_name = '특급기술자'
  -- (2) 현재 프로젝트는 뺀다 (선례는 '다른' 사업에서 찾는다)
  AND p.name NOT LIKE '[TEST] 기초과학%'
  -- (3) 승인된 것만
  AND ai.decision IN ('APPROVED', 'EDITED')
  -- (4) 단가가 있는 것만
  AND ai.unit_price IS NOT NULL
ORDER BY ai.unit_price DESC;

\echo ''
\echo '=== 기대: 4건 · 최저 6,900,000 · 최고 9,200,000 · 중앙값 8,150,000 ==='
\echo '    중앙값은 (7,500,000 + 8,800,000) / 2 이고 목록에 없는 값이다.'
\echo '    화면에 8,150,000 이 뜨면 값을 고른 것이 아니라 계산한 것이다.'
\echo ''
\echo '    이 쿼리는 서비스의 조회 조건을 흉내낸 것이다. 실제 격리는 코드가'
\echo '    하므로, 위 목록이 맞아도 화면을 열어 확인해야 한다.'
\echo ''
\echo '=== 나오지 않아야 하는 항목과 그 이유 ==='
-- 위 쿼리에서 빠진 것들을 이유와 함께 모아 본다. 멤버가 아닌 프로젝트까지
-- 포함해서, 무엇이 왜 제외되는지 한 곳에서 보이게 한다.
SELECT p.name AS 프로젝트, ai.item_name AS 항목, ai.unit_price AS 단가,
       ai.decision AS 상태,
       CASE
         WHEN NOT EXISTS (
           SELECT 1 FROM project_members pm
           WHERE pm.project_id = p.id
             AND pm.user_id = (SELECT id FROM users WHERE login_id <> 'test_other'
                               ORDER BY id LIMIT 1)
         ) THEN '내가 멤버가 아님'
         WHEN p.name LIKE '[TEST] 기초과학%' THEN '현재 프로젝트'
         WHEN ai.unit_price IS NULL THEN '단가 없음 (비율 산정 항목)'
         WHEN ai.decision NOT IN ('APPROVED','EDITED') THEN '승인 안 됨'
         ELSE '?'
       END AS 제외이유
FROM amount_items ai
JOIN documents d ON d.id = ai.document_id
JOIN projects p ON p.id = d.project_id
WHERE p.name LIKE '[TEST]%'
  AND (
    ai.unit_price IS NULL
    OR ai.decision NOT IN ('APPROVED','EDITED')
    OR p.name LIKE '[TEST] 기초과학%'
    OR NOT EXISTS (
      SELECT 1 FROM project_members pm
      WHERE pm.project_id = p.id
        AND pm.user_id = (SELECT id FROM users WHERE login_id <> 'test_other'
                          ORDER BY id LIMIT 1)
    )
  )
  AND ai.item_name = '특급기술자'
ORDER BY 제외이유, p.name;

COMMIT;
