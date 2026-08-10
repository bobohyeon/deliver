-- =============================================================================
-- DocFlow 전체 스키마 — PostgreSQL 16
--
-- 이 파일의 책임: 관리/DocFlow_DB.dbml 을 실행 가능한 DDL 로 옮긴 것이다.
--   테이블 19개 · ENUM 18개 · 인덱스 · CHECK 제약 · 부분 인덱스를 모두 포함한다.
-- 다른 파일과의 관계: DBML 이 사람이 읽는 정본이고 이 파일이 기계가 실행하는
--   정본이다. 한쪽을 고치면 다른 쪽도 고친다. 기능 ID 는 관리/기능명세서.md.
-- Spring 비교: JPA 의 ddl-auto 대신 스키마를 직접 관리하는 방식이고,
--   Flyway 의 V1__init.sql 에 해당한다.
--
-- 실행 방법 — pgAdmin 이나 별도 프로그램이 필요 없다.
--   PostgreSQL 이 도커 안에 있으므로 psql 도 이미 컨테이너 안에 있다.
--
--   docker compose exec -T db psql -U postgres -d pdfbrief < DocFlow_schema.sql
--
--   (컨테이너 이름이 ocr-db 이면 docker exec -i ocr-db psql ... 도 된다)
--
-- 주의 — 아래 초기화 블록은 기본으로 꺼져 있다. 지금은 회원가입 테이블만
--   있으니 켜서 한 번에 다시 만드는 것이 깔끔하다. 단 데이터가 지워진다.
-- =============================================================================

-- ── 초기화 (필요할 때만 주석을 푼다. 모든 데이터가 지워진다) ──────────────────
-- DROP SCHEMA public CASCADE;
-- CREATE SCHEMA public;

BEGIN;


-- =============================================================================
-- ENUM 18개
-- =============================================================================

CREATE TYPE member_role          AS ENUM ('OWNER', 'EDITOR', 'VIEWER');
CREATE TYPE project_status       AS ENUM ('ACTIVE', 'ARCHIVED');

-- 추출·분석 파이프라인 상태. 검수 상태(review_status)와 분리한다 —
-- status=EXTRACTED + review_status=IN_PROGRESS 같은 상태를 표현해야 한다.
CREATE TYPE document_status      AS ENUM (
    'PENDING', 'EXTRACTING', 'EXTRACTED', 'ANALYZING', 'COMPLETED', 'FAILED');

-- 7종. 미니 프로젝트 6종에 CONTRACT_CHANGE 를 더했다.
-- 원계약은 계약금액, 변경합의서는 증감액을 뽑아 프롬프트 힌트가 달라야 한다.
CREATE TYPE document_type        AS ENUM (
    'CONTRACT', 'CONTRACT_CHANGE', 'MEETING_NOTES', 'REPORT',
    'NOTICE', 'MANUAL', 'ETC');

-- USER_CORRECTED 비율이 곧 분류 오류율이다.
-- 정답 데이터셋 없이 실사용 데이터로 분류 정확도를 잰다.
CREATE TYPE document_type_source AS ENUM ('USER', 'AI', 'USER_CORRECTED');

CREATE TYPE processing_mode      AS ENUM ('NORMAL', 'REVIEW');
CREATE TYPE review_status        AS ENUM (
    'NOT_REQUIRED', 'PENDING', 'IN_PROGRESS', 'COMPLETED');

CREATE TYPE ocr_element_source   AS ENUM ('OCR', 'TEXT_LAYER', 'MANUAL', 'RE_OCR');
CREATE TYPE ocr_review_status    AS ENUM ('UNREVIEWED', 'REVIEWED', 'REJECTED');
CREATE TYPE ocr_group_type       AS ENUM (
    'PARAGRAPH', 'HEADING', 'TABLE', 'TABLE_ROW', 'LIST', 'CAPTION', 'FOOTNOTE');
CREATE TYPE ocr_edit_action      AS ENUM (
    'TEXT_EDIT', 'BOX_MOVE', 'BOX_RESIZE', 'BOX_CREATE', 'BOX_DELETE',
    'BOX_RESTORE', 'RE_OCR', 'REORDER', 'GROUP_CHANGE', 'REVIEW_COMPLETE');

CREATE TYPE batch_status         AS ENUM (
    'QUEUED', 'PROCESSING', 'REVIEW_REQUIRED', 'COMPLETED', 'FAILED');

CREATE TYPE task_status          AS ENUM ('TODO', 'DOING', 'DONE');

-- REJECTED 를 남겨야 채택률(ANL-10)을 계산할 수 있다.
CREATE TYPE suggestion_decision  AS ENUM ('PENDING', 'APPROVED', 'EDITED', 'REJECTED');

-- PENDING 인 결정이 곧 '다음 회의 안건'(DLV-06) 이 된다.
CREATE TYPE decision_status      AS ENUM ('DECIDED', 'PENDING', 'REVERSED');

CREATE TYPE schedule_kind        AS ENUM ('MILESTONE', 'DEADLINE', 'MEETING', 'PERIOD');

CREATE TYPE deliverable_kind     AS ENUM (
    'WEEKLY_REPORT', 'DECISION_LOG', 'MEETING_AGENDA', 'PROJECT_STATUS');

-- 기본값을 두지 않는다. 사용자가 매번 고른다 (DLV-08).
CREATE TYPE deliverable_format   AS ENUM ('XLSX', 'HTML', 'MD');


-- =============================================================================
-- 담당 박세현 — 계정 · 프로젝트
-- =============================================================================

CREATE TABLE users (
    id            bigserial    PRIMARY KEY,
    email         varchar(255) NOT NULL UNIQUE,
    password_hash varchar(255) NOT NULL,
    name          varchar(100) NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON COLUMN users.password_hash IS '해시만 저장. 응답에 절대 포함하지 않는다';

CREATE TABLE projects (
    id          bigserial      PRIMARY KEY,
    name        varchar(200)   NOT NULL,
    description text,
    owner_id    bigint         NOT NULL REFERENCES users(id),
    status      project_status NOT NULL DEFAULT 'ACTIVE',
    started_on  date,
    due_on      date,
    created_at  timestamptz    NOT NULL DEFAULT now(),
    updated_at  timestamptz    NOT NULL DEFAULT now()
);
COMMENT ON COLUMN projects.started_on IS '선택. 일정 산출물에서 전체 일정 대비 현재 위치';

CREATE TABLE project_members (
    id         bigserial   PRIMARY KEY,
    project_id bigint      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id    bigint      NOT NULL REFERENCES users(id),
    role       member_role NOT NULL,
    invited_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_project_member UNIQUE (project_id, user_id)
);


-- =============================================================================
-- 담당 최재정 — 일괄 처리  (documents 가 batch_items 를 참조하므로 먼저)
-- =============================================================================

CREATE TABLE batch_jobs (
    id           bigserial    PRIMARY KEY,
    project_id   bigint       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_by   bigint       REFERENCES users(id),
    status       batch_status NOT NULL DEFAULT 'QUEUED',
    total_count  int          NOT NULL DEFAULT 0,
    done_count   int          NOT NULL DEFAULT 0,
    failed_count int          NOT NULL DEFAULT 0,
    -- 배치 단위 유형 지정. NULL 이면 파일마다 자동 판별.
    -- 같은 폴더 문서는 같은 유형인 경우가 많아 분류 호출 100번을 아낀다.
    default_document_type document_type,
    created_at   timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE batch_items (
    id            bigserial    PRIMARY KEY,
    batch_job_id  bigint       NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
    filename      varchar(500) NOT NULL,
    status        batch_status NOT NULL DEFAULT 'QUEUED',
    error_message text,
    created_at    timestamptz  NOT NULL DEFAULT now()
);


-- =============================================================================
-- 담당 공통 — 문서
-- =============================================================================

CREATE TABLE documents (
    id           bigserial       PRIMARY KEY,
    -- PRJ-08 스코프 강제의 기준. 리포지토리 계층에서 조건을 강제한다.
    project_id   bigint          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    uploaded_by  bigint          REFERENCES users(id),

    filename     varchar(500)    NOT NULL,
    file_type    varchar(20)     NOT NULL,
    file_size    bigint          NOT NULL,
    storage_path varchar(1000)   NOT NULL,
    content_hash char(64),

    status       document_status NOT NULL DEFAULT 'PENDING',

    -- NULL = 자동 판별 대기. 분류 분석기 결과로 채워진다.
    -- 분석기를 껐다 켜는 용도가 아니다 — 목록 필터·프롬프트 힌트·산출물 분류.
    document_type        document_type,
    document_type_source document_type_source,

    processing_mode processing_mode NOT NULL DEFAULT 'NORMAL',
    review_status   review_status   NOT NULL DEFAULT 'NOT_REQUIRED',
    reviewed_by     bigint          REFERENCES users(id),
    reviewed_at     timestamptz,

    -- revision 전파 사슬의 시작점. 박스 하나만 고쳐도 항상 올린다.
    ocr_revision int NOT NULL DEFAULT 1,

    batch_item_id bigint REFERENCES batch_items(id) ON DELETE SET NULL,

    -- N+1 방지용 비정규화 (SYS-07). 분석 완료 시 서비스 계층에서 함께 쓴다.
    -- 트리거를 쓰지 않는다 — 애플리케이션 로그에 안 남아 디버깅이 어렵다.
    category_cache  varchar(30),
    summary_preview varchar(300),

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN documents.ocr_revision IS
    'ocr_elements 를 고치면 오른다. 하위 파생 데이터의 신선도 판정 기준';

CREATE TABLE extracted_texts (
    document_id    bigint      PRIMARY KEY
                               REFERENCES documents(id) ON DELETE CASCADE,
    -- 원천이 아니라 ocr_elements 를 reading_order 로 조립한 스냅샷이다.
    content        text        NOT NULL,
    page_count     int,
    char_count     int,
    extract_method varchar(20),

    text_version int         NOT NULL DEFAULT 1,
    is_confirmed bool        NOT NULL DEFAULT false,
    confirmed_by bigint      REFERENCES users(id),
    confirmed_at timestamptz,
    updated_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN extracted_texts.content IS
    '검색·분석용 캐시. 원천은 ocr_elements 다 (REV-17)';

CREATE TABLE analyses (
    id            bigserial    PRIMARY KEY,
    document_id   bigint       NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    -- summary / category / extract / amount. 유형 구분 없이 항상 넷 다 돌린다.
    analyzer_type varchar(30)  NOT NULL,
    -- 분석기마다 결과 모양이 달라 JSONB 로 열어 둔다.
    result_json   jsonb        NOT NULL,

    provider       varchar(30)  NOT NULL,
    model_name     varchar(100) NOT NULL,
    prompt_version varchar(20),
    tokens_in      int,
    tokens_out     int,
    latency_ms     int,

    -- 이 값이 documents.ocr_revision 보다 작으면 오래된 결과다 (REV-18).
    source_text_revision int NOT NULL,

    created_at timestamptz NOT NULL DEFAULT now()
);


-- =============================================================================
-- 담당 최재정 — OCR 검수
-- 최재정님 'OCR-DB 설계안' 을 변경 없이 채택했다.
-- =============================================================================

CREATE TABLE document_pages (
    id             bigserial     PRIMARY KEY,
    document_id    bigint        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number    int           NOT NULL,
    width          numeric(10,2) NOT NULL,
    height         numeric(10,2) NOT NULL,
    -- 좌표 기준본. 렌더링본으로 고정한다.
    -- 프런트가 보는 이미지와 달라지면 박스가 어긋난다 (REV-03).
    image_path     varchar(1000) NOT NULL,
    thumbnail_path varchar(1000),
    rotation       int           NOT NULL DEFAULT 0,
    render_scale   numeric(6,3),
    created_at     timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_doc_page UNIQUE (document_id, page_number)
);
COMMENT ON COLUMN document_pages.page_number IS '1 부터 센다. 화면 표시와 일치';

-- ocr_elements 가 group_id 로 참조하므로 먼저 만든다.
CREATE TABLE ocr_groups (
    id            bigserial      PRIMARY KEY,
    document_id   bigint         NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id       bigint         REFERENCES document_pages(id) ON DELETE CASCADE,
    group_type    ocr_group_type NOT NULL,
    reading_order int            NOT NULL,
    text_override text,
    created_by    bigint         REFERENCES users(id),
    created_at    timestamptz    NOT NULL DEFAULT now(),
    updated_at    timestamptz    NOT NULL DEFAULT now()
);

CREATE TABLE ocr_elements (
    -- 수정 후에도 유지되는 식별자. 삭제·재생성하면 참조가 끊어진다.
    id          bigserial PRIMARY KEY,
    document_id bigint    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id     bigint    NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,

    original_text varchar(2000) NOT NULL,
    text          varchar(2000) NOT NULL,
    confidence    numeric(5,4),

    -- 픽셀이 아니라 페이지 크기 대비 0~1 비율.
    -- 화면 확대·축소와 무관하게 같은 위치에 박스를 그린다.
    x1 numeric(9,6) NOT NULL,
    y1 numeric(9,6) NOT NULL,
    x2 numeric(9,6) NOT NULL,
    y2 numeric(9,6) NOT NULL,
    polygon_json jsonb,

    source          ocr_element_source NOT NULL,
    ocr_engine      varchar(30),
    engine_version  varchar(30),
    preprocess_info jsonb,

    reading_order int    NOT NULL,
    group_id      bigint REFERENCES ocr_groups(id) ON DELETE SET NULL,

    review_status ocr_review_status NOT NULL DEFAULT 'UNREVIEWED',
    -- 논리 삭제. 물리 삭제하면 이력과 참조가 사라진다.
    is_deleted    bool NOT NULL DEFAULT false,

    created_by bigint      REFERENCES users(id),
    updated_by bigint      REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- 동시 수정 충돌 방지 (REV-16). documents.ocr_revision 과 목적이 다르다 —
    -- 이건 충돌 방지, 저건 파생 데이터 신선도.
    version int NOT NULL DEFAULT 1
);
COMMENT ON COLUMN ocr_elements.original_text IS '최초 OCR 텍스트. 사용자 수정 시 바꾸지 않는다';
COMMENT ON COLUMN ocr_elements.version      IS '낙관적 락. 불일치 시 409';

CREATE TABLE ocr_element_revisions (
    id              bigserial       PRIMARY KEY,
    ocr_element_id  bigint          NOT NULL REFERENCES ocr_elements(id) ON DELETE CASCADE,
    revision_number int             NOT NULL,
    action_type     ocr_edit_action NOT NULL,
    before_json     jsonb,
    after_json      jsonb,
    edited_by       bigint          REFERENCES users(id),
    created_at      timestamptz     NOT NULL DEFAULT now()
);


-- =============================================================================
-- 담당 김보현 — 분석 산물 (제안 4종)
--
-- 공통 원칙 — LLM 은 문서에 있는 것만 뽑고, 계산과 집계는 코드가 한다.
-- 네 종류가 같은 모양이라 제안 승인 API 하나로 통일된다.
-- =============================================================================

-- ★ 합의 대기 항목 (API_계약서_v2.md 7절) ─────────────────────────────────────
-- 착수기획서는 액션아이템을 analyses.result_json 안의 배열로 두고
-- tasks.source_analysis_id 로 가리켰다. 그러면 승인·거부 상태를 JSONB 배열
-- 원소로 관리해야 하고 채택률 계산도 다른 셋과 달라진다.
-- 이 테이블을 빼려면 아래 두 곳을 함께 고친다.
--   ① 이 CREATE TABLE 블록 삭제
--   ② tasks.source_action_item_id → source_analysis_id bigint REFERENCES analyses(id)
CREATE TABLE action_items (
    id          bigserial    PRIMARY KEY,
    document_id bigint       NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    analysis_id bigint       NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,

    title          varchar(300) NOT NULL,
    description    text,
    assignee_hint  varchar(100),   -- AI 가 읽은 담당자 이름. 매칭은 사람이
    due_date       date,

    confidence numeric(5,4),
    -- 근거는 페이지·좌표가 아니라 판단 근거 서술로 표시한다 (ANL-13 폐기).
    reason     text NOT NULL,

    decision   suggestion_decision NOT NULL DEFAULT 'PENDING',
    decided_by bigint      REFERENCES users(id),
    decided_at timestamptz,

    source_text_revision int NOT NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE amount_items (
    id          bigserial PRIMARY KEY,
    document_id bigint    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    analysis_id bigint    NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,

    item_name varchar(300)  NOT NULL,
    -- 문서에 없으면 NULL 이다. LLM 이 채우지 않는다.
    quantity  numeric(18,4),
    unit      varchar(30),
    amount    numeric(18,2),
    currency  char(3)       NOT NULL DEFAULT 'KRW',

    period_from date,
    period_to   date,

    reason       text          NOT NULL,
    source_quote varchar(1000),

    confidence numeric(5,4),
    decision   suggestion_decision NOT NULL DEFAULT 'PENDING',
    decided_by bigint      REFERENCES users(id),
    decided_at timestamptz,

    -- 금액은 한 글자가 전부를 바꾸므로 전파가 필수다.
    source_text_revision int NOT NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN amount_items.amount IS '문서에 적힌 금액. 없으면 NULL — AI 가 추측하지 않는다';
COMMENT ON COLUMN amount_items.reason IS '왜 이 항목으로 봤는지. 위치 하이라이트는 범위 밖';

CREATE TABLE decisions (
    id          bigserial PRIMARY KEY,
    project_id  bigint    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id bigint    REFERENCES documents(id) ON DELETE SET NULL,
    analysis_id bigint    REFERENCES analyses(id) ON DELETE SET NULL,

    title   varchar(300) NOT NULL,
    content text,
    reason  text,

    -- PENDING 인 항목이 그대로 '다음 회의 안건'(DLV-06) 이 된다.
    -- 별도 안건 테이블을 만들지 않는 이유다.
    status decision_status NOT NULL DEFAULT 'DECIDED',
    -- 뒤집힌 결정 추적. 앞 결정을 REVERSED 로 두고 뒤 결정을 가리킨다.
    superseded_by bigint REFERENCES decisions(id) ON DELETE SET NULL,

    decided_on date,
    decided_by bigint REFERENCES users(id),

    -- status(결정 자체의 상태)와 다르다. 이건 AI 제안의 승인 여부.
    decision_state suggestion_decision NOT NULL DEFAULT 'PENDING',
    source_text_revision int NOT NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE schedule_items (
    id          bigserial PRIMARY KEY,
    project_id  bigint    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id bigint    REFERENCES documents(id) ON DELETE SET NULL,
    analysis_id bigint    REFERENCES analyses(id) ON DELETE SET NULL,

    title     varchar(300)  NOT NULL,
    kind      schedule_kind NOT NULL,
    starts_on date,
    ends_on   date,
    reason    text,

    decision suggestion_decision NOT NULL DEFAULT 'PENDING',
    source_text_revision int     NOT NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);


-- =============================================================================
-- 담당 박세현 — 태스크 · 활동
-- tasks 가 action_items · amount_items 를 참조하므로 그 뒤에 만든다.
-- =============================================================================

CREATE TABLE tasks (
    id          bigserial    PRIMARY KEY,
    project_id  bigint       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title       varchar(300) NOT NULL,
    description text,
    -- AI 가 담당자를 못 찾으면 NULL. 사람이 채운다 (TSK-06).
    assignee_id bigint       REFERENCES users(id),
    due_date    date,
    status      task_status  NOT NULL DEFAULT 'TODO',

    is_ai_generated bool NOT NULL DEFAULT false,

    -- 출처 2갈래. source_type + source_id 방식을 쓰지 않는 이유는
    -- FK 제약을 걸 수 없기 때문이다.
    source_action_item_id bigint REFERENCES action_items(id) ON DELETE SET NULL,
    source_amount_item_id bigint REFERENCES amount_items(id) ON DELETE SET NULL,

    created_by   bigint      REFERENCES users(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    -- ★ 주간 보고서(DLV-04)의 '이번 주 완료 태스크' 재료.
    --   status 만으로는 언제 완료됐는지 알 수 없다.
    completed_at timestamptz,

    -- 출처는 둘 중 최대 하나만 채워진다.
    CONSTRAINT ck_task_single_source CHECK (
        (source_action_item_id IS NOT NULL)::int
      + (source_amount_item_id IS NOT NULL)::int
      <= 1
    )
);
COMMENT ON COLUMN tasks.completed_at IS 'DLV-04 재료. 목업 보드가 이미 완료일을 표시한다';

CREATE TABLE activity_logs (
    id          bigserial   PRIMARY KEY,
    project_id  bigint      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    actor_id    bigint      REFERENCES users(id),
    -- 값 목록을 팀에서 합의해야 한다. 주간 보고서의 활동 재료.
    action_type varchar(50) NOT NULL,
    target_type varchar(50),
    target_id   bigint,
    created_at  timestamptz NOT NULL DEFAULT now()
);


-- =============================================================================
-- 담당 김보현 — 산출물
-- 이 테이블이 제품의 출력물이다. 문서를 넣으면 문서가 나온다.
-- =============================================================================

CREATE TABLE deliverables (
    id         bigserial          PRIMARY KEY,
    project_id bigint             NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind       deliverable_kind   NOT NULL,
    -- 기본값을 두지 않는다. 미지정이면 API 가 422 를 낸다 (DLV-08).
    format     deliverable_format NOT NULL,

    -- WEEKLY_REPORT 만 기간이 필요하다.
    -- DECISION_LOG · PROJECT_STATUS 는 전체 누적이라 NULL 이다.
    period_from date,
    period_to   date,

    title     varchar(300)  NOT NULL,
    file_path varchar(1000) NOT NULL,
    file_size bigint,

    -- 생성 시점 스냅샷. {"documents":7,"tasks_completed":8,...}
    -- 현재 개수와 비교해 '다시 만들기' 를 띄운다 (DLV-10).
    source_counts_json jsonb NOT NULL,

    generated_by bigint      REFERENCES users(id),
    generated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT ck_deliverable_period CHECK (
        kind <> 'WEEKLY_REPORT'
        OR (period_from IS NOT NULL AND period_to IS NOT NULL)
    )
);
COMMENT ON COLUMN deliverables.source_counts_json IS
    '갱신 필요 판정의 근거. 없으면 판정이 부정확해진다';


-- =============================================================================
-- 인덱스
-- PostgreSQL 은 FK 에 인덱스를 자동으로 만들지 않는다 (SYS-08).
-- =============================================================================

-- 협업
CREATE INDEX ix_member_user        ON project_members (user_id);
CREATE INDEX ix_project_owner      ON projects (owner_id);

-- 문서
CREATE INDEX ix_doc_list           ON documents (project_id, created_at DESC);
CREATE INDEX ix_doc_type           ON documents (project_id, document_type);
CREATE INDEX ix_doc_hash           ON documents (content_hash);
CREATE INDEX ix_doc_batch          ON documents (batch_item_id);
CREATE INDEX ix_doc_uploader       ON documents (uploaded_by);
CREATE INDEX ix_analysis_doc_type  ON analyses (document_id, analyzer_type);

-- OCR 검수
CREATE INDEX ix_ocr_order          ON ocr_elements (document_id, reading_order);
CREATE INDEX ix_ocr_page           ON ocr_elements (page_id);
CREATE INDEX ix_ocr_group          ON ocr_elements (group_id);
CREATE INDEX ix_ocr_rev            ON ocr_element_revisions (ocr_element_id, revision_number);
CREATE INDEX ix_ocr_groups_doc     ON ocr_groups (document_id);

-- 일괄
CREATE INDEX ix_batch_item         ON batch_items (batch_job_id, status);
CREATE INDEX ix_batch_job_project  ON batch_jobs (project_id);

-- 제안 4종
CREATE INDEX ix_action_doc         ON action_items (document_id);
CREATE INDEX ix_action_analysis    ON action_items (analysis_id);
CREATE INDEX ix_amount_doc         ON amount_items (document_id);
CREATE INDEX ix_amount_analysis    ON amount_items (analysis_id);
CREATE INDEX ix_decision_project   ON decisions (project_id, decided_on);
CREATE INDEX ix_decision_status    ON decisions (project_id, status);
CREATE INDEX ix_decision_doc       ON decisions (document_id);
CREATE INDEX ix_schedule_project   ON schedule_items (project_id, starts_on);
CREATE INDEX ix_schedule_due       ON schedule_items (project_id, ends_on);
CREATE INDEX ix_schedule_doc       ON schedule_items (document_id);

-- 태스크
CREATE INDEX ix_task_board         ON tasks (project_id, status);
CREATE INDEX ix_task_completed     ON tasks (project_id, completed_at);
CREATE INDEX ix_task_due           ON tasks (project_id, due_date);
CREATE INDEX ix_task_assignee      ON tasks (assignee_id);
CREATE INDEX ix_task_src_action    ON tasks (source_action_item_id);
CREATE INDEX ix_task_src_amount    ON tasks (source_amount_item_id);

-- 활동 · 산출물
CREATE INDEX ix_activity_recent    ON activity_logs (project_id, created_at DESC);
CREATE INDEX ix_deliverable_recent ON deliverables (project_id, generated_at DESC);
CREATE INDEX ix_deliverable_period ON deliverables (project_id, kind, period_from, period_to);


-- =============================================================================
-- 부분 인덱스
-- 조건에 맞는 행만 담아 인덱스를 작게 유지한다.
-- =============================================================================

-- 삭제된 박스는 화면·조립에서 제외되므로 인덱스에서도 뺀다.
CREATE INDEX ix_ocr_elements_active ON ocr_elements (document_id, reading_order)
    WHERE is_deleted = false;

-- 승인 대기만 조회하는 화면이 있다 (VIS-03 승인 대기 배너).
CREATE INDEX ix_action_pending ON action_items (document_id) WHERE decision = 'PENDING';
CREATE INDEX ix_amount_pending ON amount_items (document_id) WHERE decision = 'PENDING';
CREATE INDEX ix_decision_pending ON decisions (project_id)
    WHERE decision_state = 'PENDING';
CREATE INDEX ix_schedule_pending ON schedule_items (project_id)
    WHERE decision = 'PENDING';

-- 미결 결정이 곧 다음 회의 안건이다 (DLV-06).
CREATE INDEX ix_decision_open ON decisions (project_id, created_at)
    WHERE status = 'PENDING';


COMMIT;


-- =============================================================================
-- 확인 쿼리 — 실행 후 붙여넣어 결과를 본다
-- =============================================================================
--
-- 테이블 19개가 만들어졌나
--   SELECT count(*) FROM information_schema.tables
--    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
--
-- ENUM 18개가 만들어졌나
--   SELECT count(*) FROM pg_type t
--     JOIN pg_namespace n ON n.oid = t.typnamespace
--    WHERE t.typtype = 'e' AND n.nspname = 'public';
--
-- 인덱스 목록
--   SELECT tablename, indexname FROM pg_indexes
--    WHERE schemaname = 'public' ORDER BY tablename, indexname;
--
-- FK 인덱스가 빠진 컬럼이 있나 (SYS-08 점검)
--   SELECT c.conrelid::regclass AS tbl, a.attname AS col
--     FROM pg_constraint c
--     JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
--    WHERE c.contype = 'f'
--      AND NOT EXISTS (
--        SELECT 1 FROM pg_index i
--         WHERE i.indrelid = c.conrelid AND a.attnum = i.indkey[0])
--    ORDER BY 1, 2;
-- =============================================================================
