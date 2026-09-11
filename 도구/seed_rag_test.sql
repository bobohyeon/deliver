-- =============================================================================
-- 이 파일의 책임: 의미 검색(RAG-04)을 검증할 최소 자료를 넣는다.
--   문서 업로드는 pdf·docx·hwpx·png·jpg 만 받고 OCR 이 무거우므로, 청킹·임베딩·
--   검색만 검증하기 위해 documents 와 extracted_texts 를 직접 넣는다.
--
--   검증하려는 것 세 가지
--     1. 프로젝트별 검색  — project_ids: [A] 로 A 문서만 나오는가
--     2. 전체 검색        — project_ids: null 로 A·B 문서가 함께 나오는가
--     3. 격리            — 내가 멤버가 아닌 C 문서는 절대 나오지 않는가
--                          (RAG-04 판정 기준: "내가 멤버가 아닌 프로젝트는 안 나온다")
--
--   그래서 프로젝트를 3개 만든다. A·B 는 기존 사용자가 멤버이고, C 는 다른
--   사용자만 멤버다. C 에도 "대금 지급" 내용을 넣어, 대금 관련 질의에 C 가
--   섞이면 격리가 깨진 것을 바로 알 수 있게 한다.
--
-- 재실행 안전: 맨 앞에서 [TEST] 로 시작하는 것을 지우고 다시 넣는다.
--   documents 는 projects 삭제 시 CASCADE 로 함께 지워지고,
--   extracted_texts · document_chunks 도 documents 에 CASCADE 로 걸려 있다.
--
-- 실행 방법 (PowerShell)
--   docker compose cp C:\dev\deliver\도구\seed_rag_test.sql db:/tmp/seed.sql
--   docker compose exec db psql -U postgres -d tasqra -f /tmp/seed.sql
--
--   docker compose cp 을 쓰는 이유: 파이프로 넘기면 한글이 인코딩에서 깨진다.
-- =============================================================================

BEGIN;

-- ── 정리 ────────────────────────────────────────────────────────────────────
-- projects 를 지우면 documents -> extracted_texts · document_chunks 까지
-- CASCADE 로 함께 지워진다.
DELETE FROM projects WHERE name LIKE '[TEST]%';
DELETE FROM users WHERE login_id = 'test_other';

-- ── 격리 검증용 두 번째 사용자 ──────────────────────────────────────────────
-- 로그인할 일이 없으므로 password_hash 는 자리표시자다. 실제 해시가 아니라서
-- 이 계정으로는 로그인되지 않는다 (pwdlib 이 형식을 인식하지 못한다).
INSERT INTO users (login_id, email, password_hash, name, is_active)
VALUES ('test_other', 'test_other@example.invalid',
        'placeholder-not-a-valid-hash', '남의 계정', true);

-- ── 프로젝트 3개 ────────────────────────────────────────────────────────────
INSERT INTO projects (name, description, owner_id, status)
VALUES
  ('[TEST] 기초과학연구원 연구비 정산 용역', '검색 테스트 A',
   (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1), 'ACTIVE'),
  ('[TEST] 중앙보훈병원 통합경영정보시스템 유지관리', '검색 테스트 B',
   (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1), 'ACTIVE'),
  ('[TEST] 남의 프로젝트 - 나오면 안 된다', '격리 검증 C',
   (SELECT id FROM users WHERE login_id = 'test_other'), 'ACTIVE');

-- ── 멤버십 ──────────────────────────────────────────────────────────────────
-- A · B 는 기존 사용자가 OWNER. C 는 test_other 만 멤버 -> 기존 사용자에게
-- C 는 보이지 않아야 한다.
INSERT INTO project_members (project_id, user_id, role)
SELECT p.id, p.owner_id, 'OWNER'
FROM projects p
WHERE p.name LIKE '[TEST]%';

-- ── 문서 ────────────────────────────────────────────────────────────────────
-- file_size 는 본문 길이로 대충 채운다. storage_path 는 실제 파일이 없으므로
-- 다운로드는 되지 않는다 (청킹·검색에는 쓰이지 않는다).
INSERT INTO documents (
  project_id, filename, storage_path, file_type, file_size,
  status, review_status, extraction_strategy, document_type
)
VALUES
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 기초과학%'),
   '[TEST] 입찰공고.pdf', '/app/uploads/test-notice.pdf', 'pdf', 10240,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', NULL),
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 기초과학%'),
   '[TEST] 산출내역서.pdf', '/app/uploads/test-cost.pdf', 'pdf', 8192,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', NULL),
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 중앙보훈%'),
   '[TEST] 착수회의록.pdf', '/app/uploads/test-minutes.pdf', 'pdf', 6144,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', NULL),
  ((SELECT id FROM projects WHERE name LIKE '[TEST] 남의%'),
   '[TEST] 남의공고.pdf', '/app/uploads/test-other.pdf', 'pdf', 7168,
   'COMPLETED', 'NOT_REQUIRED', 'TEXT_ONLY', NULL);

-- ── 본문 ────────────────────────────────────────────────────────────────────
-- 달러 인용($txt$)을 쓰면 따옴표를 escape 하지 않아도 된다.
-- 제목이 여러 개 들어가 있어 청킹이 여러 조각으로 나눈다.

INSERT INTO extracted_texts (document_id, content, text_char_count, ocr_char_count,
                             extract_method, text_version, is_confirmed)
SELECT d.id, $txt$제 1 장 총칙

1. 목적
이 공고는 연구비 정산 용역의 입찰 참가 자격과 절차를 정한다. 입찰에 참가하려는
자는 다음 각 호의 요건을 모두 갖추어야 한다.

2. 입찰 참가 자격
가. 국가를 당사자로 하는 계약에 관한 법률 시행령 제12조의 요건을 갖춘 자
나. 회계법인 또는 세무법인으로 등록을 마친 자
다. 최근 3년간 유사 용역 실적이 있는 자

제 2 장 계약 및 대금

3. 계약 기간
계약 체결일부터 12개월로 한다. 다만 발주기관이 필요하다고 인정하는 경우
계약 기간을 연장할 수 있다.

4. 대금 지급
준공 검사 완료 후 30일 이내에 지급한다. 선금은 계약 금액의 70퍼센트 범위에서
지급할 수 있으며, 이 경우 선금 지급 보증서를 제출하여야 한다.

5. 지체상금
계약상대자가 준공 기한을 지키지 못한 경우 지체 일수마다 계약 금액의
1천분의 1을 지체상금으로 낸다.

제 3 장 평가

6. 협상에 의한 계약
기술능력평가 80퍼센트, 입찰가격평가 20퍼센트로 한다. 제안서는 정량제안서와
정성제안서를 함께 제출한다.

7. 공동수급
공동수급체 구성은 허용하지 않는다. 단독으로 이행할 수 있는 자만 참가한다.$txt$,
       1200, 0, 'TEXT', 1, true
FROM documents d WHERE d.filename = '[TEST] 입찰공고.pdf';

INSERT INTO extracted_texts (document_id, content, text_char_count, ocr_char_count,
                             extract_method, text_version, is_confirmed)
SELECT d.id, $txt$정보시스템 구축 용역 산출내역서

1. 직접인건비
특급기술자	3인월	9,500,000	28,500,000
고급기술자	6인월	7,200,000	43,200,000
중급기술자	4인월	5,800,000	23,200,000
직접인건비 합계			94,900,000

2. 제경비
제경비는 직접인건비의 110퍼센트로 산정한다.
제경비			104,390,000

3. 기술료
기술료는 직접인건비와 제경비 합계의 20퍼센트로 산정한다.
기술료			39,858,000

4. 합계
공급가액			239,148,000
부가가치세			23,914,800
총액			263,062,800

5. 산출 근거
소프트웨어사업 대가산정 가이드에 따라 기능점수 방식이 아닌 투입공수 방식으로
산정하였다. 인건비 단가는 한국소프트웨어산업협회 공표 노임단가를 적용한다.$txt$,
       700, 0, 'TEXT', 1, true
FROM documents d WHERE d.filename = '[TEST] 산출내역서.pdf';

INSERT INTO extracted_texts (document_id, content, text_char_count, ocr_char_count,
                             extract_method, text_version, is_confirmed)
SELECT d.id, $txt$착수 회의록

일시: 2026년 3월 5일 14시
장소: 발주기관 회의실
참석: 발주기관 정보화팀 3명, 수행사 4명

1. 논의 사항
과업 범위 중 데이터 이관 항목의 대상 시스템이 명확하지 않다는 의견이 있었다.
현행 시스템 조사 결과를 먼저 공유하고 범위를 확정하기로 하였다.

2. 결정 사항
이관 대상은 인사시스템과 회계시스템 두 곳으로 한정한다.
산출물 제출 시점을 착수 후 4주로 한다. 검사는 산출물 제출 후 2주 안에 완료한다.
주간 보고는 매주 금요일 오전에 서면으로 제출한다.

3. 미결 사항
테스트 서버 제공 시점은 발주기관 내부 협의 후 통보한다.
개인정보 처리 방침 검토는 법무 검토가 끝난 뒤 다시 논의한다.

4. 다음 회의
2026년 3월 19일 14시, 같은 장소에서 진행한다.$txt$,
       550, 0, 'TEXT', 1, true
FROM documents d WHERE d.filename = '[TEST] 착수회의록.pdf';

-- 격리 검증용. "대금 지급" 내용을 일부러 넣었다. 대금 관련 질의에 이 문서가
-- 섞여 나오면 프로젝트 격리가 깨진 것이다.
INSERT INTO extracted_texts (document_id, content, text_char_count, ocr_char_count,
                             extract_method, text_version, is_confirmed)
SELECT d.id, $txt$남의 프로젝트 공고문 — 이 문서는 검색 결과에 나오면 안 된다

1. 대금 지급
이 사업의 대금은 검사 완료 후 15일 이내에 지급한다. 선금은 지급하지 않는다.
이 문장이 검색 결과에 나타나면 프로젝트 격리가 깨진 것이다.

2. 계약 기간
계약 체결일부터 24개월로 한다.

3. 지체상금
지체 일수마다 계약 금액의 1천분의 2를 지체상금으로 낸다.$txt$,
       250, 0, 'TEXT', 1, true
FROM documents d WHERE d.filename = '[TEST] 남의공고.pdf';

COMMIT;

-- ── 확인 ────────────────────────────────────────────────────────────────────
\echo ''
\echo '=== 넣은 자료 ==='
SELECT p.id AS prj, p.name AS 프로젝트,
       (SELECT count(*) FROM project_members m WHERE m.project_id = p.id) AS 멤버,
       (SELECT count(*) FROM documents d WHERE d.project_id = p.id) AS 문서
FROM projects p WHERE p.name LIKE '[TEST]%' ORDER BY p.id;

\echo ''
\echo '=== 문서와 본문 길이 ==='
SELECT d.id AS doc, d.project_id AS prj, d.filename, length(e.content) AS 본문
FROM documents d JOIN extracted_texts e ON e.document_id = d.id
WHERE d.filename LIKE '[TEST]%' ORDER BY d.id;

\echo ''
\echo '=== 기존 사용자가 볼 수 있는 프로젝트 (C 가 없어야 한다) ==='
SELECT p.id, p.name
FROM projects p
JOIN project_members m ON m.project_id = p.id
WHERE m.user_id = (SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1)
ORDER BY p.id;

\echo ''
\echo '다음: docker compose exec worker python -c "from app.worker import build_chunks_task; ..."'
