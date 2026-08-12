# API 계약 초안 — 검색·근거 `RAG`

```
문서번호   DOCFLOW-API-RAG-01 (초안)
작성일자   2026. 8. 11.
작성자     김보현
상태       초안 — 3인 합의 전
합칠 곳    관리/API_계약서_v2.md  3절 엔드포인트 목록
근거       관리/RAG_임베딩모델_선정_결과서.md (모델·차원 확정)
```

> **`API_계약서_v2.md` 에 검색 엔드포인트가 없다.** `RAG-04`·`RAG-08` 이 P1 인데
> 대응 경로가 비어 있고 `VIS-06` 통합 검색만 있다. `0010` 직후 구현 대상이라
> 프런트와 맞출 계약이 필요해 초안을 만들었다.

**규약은 `API_계약서_v2.md` 2절을 그대로 따른다.**
Base URL `/api` · JWT Bearer · snake_case · 페이징 `page`/`size` · 스코프 위반은 `404`.

---

## 이 문서에 나오는 기능 ID

**ID 를 찾아보지 않아도 되게 표로 둔다.** 명세서 작업명과 쉬운 말을 함께 적었다.

| ID | 명세서 작업명 | 쉬운 말 | 담당 |
|---|---|---|---|
| `RAG-01` | 텍스트 정규화 · 청킹 | **문서를 조각으로 자르기** | 보현 |
| `RAG-02` | 임베딩 생성 · 저장 | **조각을 숫자로 바꿔 저장하기** | 보현 |
| `RAG-03` | 벡터 인덱스 구축 (pgvector) | 숫자로 빨리 찾게 색인 만들기 | 보현 |
| `RAG-04` | 의미 검색 | **뜻으로 찾기** (글자가 안 겹쳐도) | 보현 |
| `RAG-05` | 하이브리드 검색 | **글자로 찾기 + 뜻으로 찾기 합치기** | 보현 |
| `RAG-06` | 검색 결과 재순위 | 찾은 것을 다시 줄 세우기 | 보현 |
| `RAG-07` | 프롬프트 컨텍스트 조립 | **긴 문서에서 AI 에 넣을 조각 고르기** | 보현 |
| `RAG-08` | 근거 스니펫 연결 | **결과마다 출처와 원문 인용 붙이기** | 보현 |
| `RAG-09` | 검수 확정 시 재임베딩 | **OCR 을 고치면 숫자도 다시 만들기** | 보현 |
| `RAG-10` | 검색 품질 측정 | **검색이 잘 되는지 점수로 재기** | 보현 |
| `RAG-12` | 유사 사업 단가 선례 검색 | **과거 사업에서 비슷한 단가 찾기** | 보현 |
| `REV-17` | 텍스트 재조립 | **OCR 박스를 고치면 본문을 다시 합치기** | 재정 |
| `PRJ-08` | 프로젝트 스코프 강제 | **다른 프로젝트 자료가 안 보이게 막기** | 재정 |
| `SYS-02` | Celery + Redis | **오래 걸리는 일을 뒤에서 돌리는 작업 큐** | 재정 |
| `VIS-06` | 통합 검색 (PostgreSQL FTS) | 검색 화면과 글자 검색 | 보현 |
| `VIS-07` | 검색 화면의 의미 검색 표시 | **찾은 것이 글자로 걸렸나 뜻으로 걸렸나 구분해 보여주기** | 보현 |
| `AMT-13` | 단가 · 원가구분 컬럼 추가 | **단가와 부가세 구분을 DB 에 넣기** | 보현 |
| `AMT-17` | 계산식 · 산출 근거 표시 | 금액마다 계산식과 출처 보여주기 | 보현 |
| `DOC-06` | 비동기 큐 처리 | **업로드하면 바로 응답하고 뒤에서 처리** | 재정 |
| `PRJ-07` | 권한 3종 | OWNER · EDITOR · VIEWER | 재정 |
| `PRJ-09` | 조직 계층 | 프로젝트 위에 조직을 두기 (P3) | 재정 |
| `REV-07` | 검수 완료 처리 | **OCR 검수를 끝냈다고 표시하기** | 재정 |
| `SYS-03` | 에러코드 체계 | 오류 응답 형식과 코드 목록 | 보현 |
| `RAG-11` | 질의응답 챗봇 | 문서에 대해 질문하면 근거와 함께 답하기 (P3) | 보현 |
| `ANL-16` | 구조화 출력 검증 · 재시도 | **AI 가 형식을 어기면 잡아내고 다시 시키기** | 보현 |
| `ANL-17` | 평가셋 기반 정확도 측정 자동화 | **모델을 바꿔도 같은 자로 재기** | 보현 |

---

## 0. 먼저 정해야 하는 쟁점 셋

### 쟁점 1 — `RAG-04` 와 `RAG-12` 의 스코프가 반대다

기능명세서 완료 판정을 나란히 놓으면 드러난다.

| ID | 완료 판정 기준 | 스코프 |
|---|---|---|
| `RAG-04` 의미 검색 | 관련 문서가 나온다. **다른 프로젝트 문서는 나오지 않는다** | 프로젝트 안 |
| `RAG-12` 유사 사업 단가 선례 | **과거 사업 문서에서** 같은 항목의 단가를 찾아 출처와 함께 | **프로젝트를 넘어야 한다** |

**`RAG-12` 는 과거 사업을 봐야 하므로 프로젝트 경계를 넘는다.**
그런데 `PRJ-08` 이 스코프를 강제하고, 리포지토리 계층에서 `project_id` 를 필수
인자로 받는 것이 코드 관례다.

세 가지 안이 있다.

| 안 | 범위 | 평가 |
|---|---|---|
| A | 같은 프로젝트의 과거 문서만 | 안전하지만 **선례 검색의 뜻이 사라진다.** 한 프로젝트에 과거 사업이 없다 |
| **B** | **내가 멤버인 프로젝트 전체** | **권한 위반이 아니다.** 출처에 프로젝트명을 반드시 표시한다 |
| C | 조직 단위 | `PRJ-09` 조직 계층이 P3 이라 지금 없다 |

**B 를 제안한다.** 근거는 `PRJ-07` 권한 정의가 "프로젝트 멤버만 해당 프로젝트
데이터에 접근" 이므로, 내가 멤버인 프로젝트들을 한 번에 보는 것은 그 안이다.
다만 **엔드포인트를 분리해 실수로 넘나들지 않게 한다** (2절 · 4절 경로가 다르다).

### 쟁점 2 — 결과 단위를 청크로 할지 문서로 할지

`RAG-08` 완료 판정이 "검색 결과마다 출처 문서와 **원문 인용**이 함께 나온다" 다.
**문서 단위로 뭉치면 인용이 사라진다.** 그래서 **청크 단위로 반환**한다.

같은 문서의 청크가 여러 개 걸릴 수 있으므로 `per_document` 로 조절한다.
기존 `documents?q=` 검색이 서브쿼리로 행 중복을 피하는 관례와 어긋나지 않게,
**경로를 분리해 문서 목록 API 는 건드리지 않는다.**

### 쟁점 3 — 정렬 기준이 기존과 다르다

기존 문서 목록은 `created_at DESC` 고정이다(`document_repository.py`).
**검색은 유사도 내림차순이어야 한다.** 계약에 명시해 프런트가 혼동하지 않게 한다.

---

## 1. 엔드포인트 목록

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| R1 | `GET` | `/api/projects/{project_id}/search` | **통합 검색** (키워드 · 의미 · 하이브리드) | `VIS-06`·`RAG-04`·`RAG-05`·`RAG-08` | P1 |
| R2 | `GET` | `/api/amount-precedents` | **유사 사업 단가 선례** (프로젝트 넘음) | `RAG-12` | P2 |
| R3 | `POST` | `/api/projects/{project_id}/documents/{document_id}/reindex` | 재임베딩 (수동) | `RAG-02`·`RAG-09` | P1 |
| R4 | `GET` | `/api/projects/{project_id}/documents/{document_id}/chunks` | 청크·임베딩 상태 조회 | `RAG-01`·`RAG-02` | P2 |
| R5 | `POST` | `/api/admin/search-eval` | 검색 품질 측정 | `RAG-10` | P2 |

**R1 하나에 `mode` 를 둔다.** `RAG-05` 가 키워드와 벡터를 결합하는 것이므로
따로 만들면 나중에 합칠 때 계약이 둘로 갈린다.

`RAG-07`(프롬프트 컨텍스트 조립)은 내부 로직이라 엔드포인트가 없다.
`RAG-03`(인덱스 구축)은 마이그레이션이다. `RAG-11`(챗봇)은 P3 으로 이번 초안 밖.

---

## 2. R1 — 통합 검색

```
GET /api/projects/{project_id}/search
```

권한 `get_project_access` (읽기 · `VIEWER` 이상)

### 요청 파라미터

| 이름 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `q` | string | (필수) | 검색어. **2자 이상** |
| `mode` | string | `hybrid` | `keyword` · `semantic` · **`hybrid`** |
| `per_document` | int | `0` | `1` 이면 문서마다 가장 잘 맞는 청크 하나만 |
| `document_type` | string | — | 9종 중 하나로 좁힌다 |
| `min_score` | float | `0` | 이 값 미만은 버린다 (`0`~`1`) |
| `page` | int | `1` | |
| `size` | int | `20` | 최대 `100` |

**`mode` 기본값을 `hybrid` 로 둔다.** 측정에서 숫자·코드번호는 벡터가 약하고
(`사업금액 578600000원` 이 10위 밖) 뜻으로 묻는 질의는 키워드가 못 찾았다.
한쪽만 쓰면 어느 쪽이든 절반을 놓친다.

### 응답 `200`

```json
{
  "items": [
    {
      "chunk_id": 812,
      "document_id": 34,
      "filename": "2026년 통합경영정보시스템 유지관리 제안요청서.pdf",
      "document_type": "RFP",
      "page_number": 7,
      "snippet": "…분야별 배정 : 기술능력배점 90점, 입찰가격배점 10점…",
      "score": 0.7912,
      "match": "BOTH"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 37,
  "total_pages": 2,
  "mode": "hybrid",
  "embedding_model": "nlpai-lab/KURE-v1",
  "embedding_dim": 1024
}
```

`items` 를 제외한 페이징 필드는 기존 `PageResponse[T]` 와 같다.

| 필드 | 왜 필요한가 |
|---|---|
| `snippet` | **`RAG-08` 완료 판정이 원문 인용을 요구한다** |
| `page_number` | 출처를 화면에서 짚어주려면 필요하다 |
| `score` | `0`~`1`. 코사인 유사도 기반. 정렬 기준 |
| **`match`** | **`SEMANTIC` · `KEYWORD` · `BOTH`.** `VIS-07` 이 "키워드 일치와 의미 일치가 구분되어 보인다" 를 요구한다 |
| `embedding_model` · `embedding_dim` | **`RAG-02` 완료 판정이 "어느 모델·차원으로 만든 것인지 기록된다" 다.** 모델 교체 시 디버깅에 쓴다 |

**정렬은 `score` 내림차순.** 기존 문서 목록의 `created_at DESC` 와 다르다.

### `mode` 별 동작

| `mode` | 키워드 | 벡터 | `match` 값 |
|---|---|---|---|
| `keyword` | 공백 제거 후 `ILIKE` (기존 방식) | 안 씀 | `KEYWORD` |
| `semantic` | 안 씀 | `pgvector` 코사인 | `SEMANTIC` |
| `hybrid` | 둘 다 | 둘 다 | 걸린 쪽에 따라 셋 중 하나 |

**키워드 쪽은 새로 만들지 않는다.** `RAG-05` 비고가 `VIS-06` FTS 와 결합하라고
지정하는데, **현재 코드는 FTS 가 아니라 `regexp_replace` + `ILIKE` 다**
(`document_repository.py` 확인). `VIS-06` 이 FTS 로 바뀔 때 이 엔드포인트의
`keyword` 경로만 갈아끼우고 계약은 그대로 둔다.

### 오류

| 상황 | 코드 | HTTP |
|---|---|---|
| `q` 가 2자 미만 | `VALIDATION_ERROR` | `422` |
| 내가 멤버가 아닌 프로젝트 | `PROJECT_NOT_FOUND` | `404` |
| 이 프로젝트에 임베딩된 청크가 없다 | **`EMBEDDING_NOT_READY`** | `409` |
| 저장된 벡터의 모델·차원이 설정과 다르다 | **`EMBEDDING_MODEL_MISMATCH`** | `409` |
| 임베딩 모델 적재 실패 | `AI_MODEL_NOT_LOADED` (기존) | `503` |

**`EMBEDDING_MODEL_MISMATCH` 가 중요하다.** 모델을 바꾸면 기존 벡터를 쓸 수 없다.
그때 조용히 엉뚱한 결과를 주지 않고 **명시적으로 실패해야 한다.**
`RAG-09` 가 막으려는 것과 같은 문제다 — 낡은 벡터로 검색되지 않아야 한다.

`mode=keyword` 는 벡터를 쓰지 않으므로 위 두 `409` 를 내지 않는다.
**임베딩이 아직 없어도 키워드 검색은 된다.**

---

## 3. R3 — 재임베딩 (수동)

```
POST /api/projects/{project_id}/documents/{document_id}/reindex
```

권한 `get_project_editor_access` (`EDITOR` 이상)

`RAG-09` 는 검수 확정(`REV-07`) 시 **자동으로** 돈다. 이 엔드포인트는
**모델을 교체했거나 청킹 규칙을 바꿨을 때** 쓰는 수동 경로다.

### 요청

```json
{ "force": false }
```

| 필드 | 기본 | 설명 |
|---|---|---|
| `force` | `false` | `false` 면 `text_version` 이 그대로일 때 건너뛴다 |

**`extracted_texts.text_version` 을 stale 판정 키로 쓴다.**
코드를 확인한 결과 이 컬럼이 이미 있고 텍스트가 갱신될 때 올라간다.
`document_chunks` 에 만들 때의 `text_version` 을 함께 저장하면
**낡은 벡터를 값 비교 하나로 찾아낼 수 있다.**

### 응답 `202`

```json
{
  "document_id": 34,
  "status": "QUEUED",
  "chunk_count": 0,
  "text_version": 3,
  "embedding_model": "nlpai-lab/KURE-v1"
}
```

**`202` 로 두는 이유** — 임베딩이 오래 걸린다.
다만 **현재 코드에 Worker 가 없다** (`SYS-02` 미착수 · `celery`·`redis` 매치 0건).
그래서 실제 동작은 둘 중 하나가 된다.

| `SYS-02` 상태 | 동작 | 응답 |
|---|---|---|
| 없음 (지금) | 요청 안에서 동기 처리 | `200` + `status: "DONE"` · `chunk_count` 채움 |
| 있음 | 큐에 넣고 즉시 반환 | `202` + `status: "QUEUED"` |

**계약은 `202`/`QUEUED` 로 적어두고, 지금은 `200`/`DONE` 으로 낸다.**
`SYS-02` 가 들어오면 응답만 바뀌고 프런트 코드는 `status` 만 보면 된다.
업로드(`DOC-06`)가 이미 같은 문제를 안고 있으므로 **함께 옮기는 것이 맞다.**

멱등성 — 같은 문서를 두 번 재색인해도 청크가 중복되지 않아야 한다
(`DEVELOPMENT_GUIDE` 4.2). 기존 청크를 지우고 다시 넣는다.

---

## 4. R2 — 유사 사업 단가 선례 (`RAG-12`)

```
GET /api/amount-precedents
```

**경로에 `project_id` 가 없다.** 쟁점 1 의 B 안이며, 이것이 유일한 예외다.
**내가 멤버인 프로젝트 전체**를 찾는다.

권한 `get_current_user` (프로젝트 스코프 대신 사용자 스코프)

### 요청 파라미터

| 이름 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `item_name` | string | (필수) | 항목명. 예 `특급기술자` |
| `exclude_project_id` | int | — | 현재 프로젝트를 결과에서 뺀다 |
| `limit` | int | `5` | 최대 `20` |

### 응답 `200`

```json
{
  "items": [
    {
      "amount_item_id": 991,
      "item_name": "특급기술자",
      "unit_price": 9500000,
      "quantity": 3,
      "unit": "인월",
      "category": "DIRECT_LABOR",
      "amount": 28500000,
      "project_id": 7,
      "project_name": "○○기관 정보화 통합유지관리",
      "document_id": 120,
      "filename": "산출내역서.xlsx",
      "snippet": "특급기술자 3인월 9,500,000 28,500,000",
      "score": 0.8321,
      "contracted_on": "2025-07-23"
    }
  ],
  "total": 4,
  "embedding_model": "nlpai-lab/KURE-v1"
}
```

**`project_id` 와 `project_name` 을 반드시 싣는다.** 프로젝트를 넘는 검색이므로
사용자가 어디서 온 값인지 알아야 한다. 출처 없는 단가는 `RAG-12` 완료 판정
("출처와 함께 보여준다")을 만족하지 못한다.

`unit_price` · `category` 는 `AMT-13` 이 추가하는 컬럼이다(리비전 `0009`).
**따라서 `RAG-12` 는 `AMT-13` 이후다.**

페이징을 쓰지 않고 `limit` 만 둔다. **선례는 상위 몇 건만 보는 용도**이며
`AMT-17`(계산식·산출 근거 표시) 화면에서 참고로 띄우는 자리다.

### 오류

| 상황 | 코드 | HTTP |
|---|---|---|
| `item_name` 이 비었다 | `VALIDATION_ERROR` | `422` |
| 멤버인 프로젝트에 임베딩이 없다 | `EMBEDDING_NOT_READY` | `409` |

---

## 5. R4 — 청크·임베딩 상태 조회

```
GET /api/projects/{project_id}/documents/{document_id}/chunks
```

권한 `get_project_access`

`RAG-01`·`RAG-02` 가 제대로 돌았는지 확인하는 진단용이다.
청킹 규칙을 바꿀 때 `RAG-10` 과 함께 쓴다.

```json
{
  "document_id": 34,
  "text_version": 3,
  "embedding_model": "nlpai-lab/KURE-v1",
  "embedding_dim": 1024,
  "is_stale": false,
  "items": [
    { "chunk_id": 812, "seq": 7, "page_number": 7, "char_count": 483,
      "token_count": 251, "text": "8. 낙찰자 결정방법 …" }
  ],
  "page": 1, "size": 20, "total": 91, "total_pages": 5
}
```

`is_stale` — `document_chunks.text_version` 이 `extracted_texts.text_version`
보다 작으면 `true`. **`RAG-09` 가 놓쳤는지 화면에서 바로 보인다.**

---

## 6. R5 — 검색 품질 측정 (`RAG-10`)

```
POST /api/admin/search-eval
```

**관리자 전용으로 격리한다.** `API_계약서_v2.md` 1절이 `/api/ocr-compare` 를
"개발·측정용이고 인증 뒤로 숨겨 관리자 전용으로 격리한다" 로 처리한 것과 같은 방식이다.

평가셋과 채점 로직은 이미 만들어져 있다
(`도구/embed-test/queries.csv` · `check_queries.py` · `run_eval.py`).
**이 엔드포인트는 그것을 본구현 청킹 위에서 돌리는 자리다.**
`RAG-10` 비고가 "청킹 기준 변경의 판단 근거" 이므로 청킹을 바꿀 때마다 호출한다.

P2 이고 화면이 없어도 되므로 **상세 계약은 `RAG-01` 완성 후에 정한다.**
지금은 경로만 예약한다.

---

## 7. `document_chunks` 스키마 초안 (리비전 `0010`)

계약과 짝이므로 함께 둔다. **0001 부터의 규칙대로 ENUM 대신 `String` + CHECK.**

| 컬럼 | 타입 | 제약 | 왜 |
|---|---|---|---|
| `id` | `BigInteger` | PK | |
| `document_id` | `BigInteger` | FK `documents.id` CASCADE · index | 스코프 조인 경로 |
| `seq` | `Integer` | NOT NULL | 문서 안 순서 |
| `page_number` | `Integer` | nullable | 출처 표시용 (`RAG-08`) |
| `text` | `Text` | NOT NULL | 인용 원문 |
| `char_count` | `Integer` | NOT NULL | |
| `token_count` | `Integer` | NOT NULL | **`RAG-01` 이 토큰 수 기준으로 자른다** |
| `embedding` | `Vector(1024)` | NOT NULL | **이 문서가 정한 차원** |
| `embedding_model` | `String(100)` | NOT NULL | **`RAG-02` 완료 판정** |
| `embedding_dim` | `Integer` | NOT NULL | 같은 이유. 값 검증용 |
| `text_version` | `Integer` | NOT NULL | **stale 판정.** `extracted_texts.text_version` 복사 |
| `created_at` · `updated_at` | `DateTime(tz)` | NOT NULL | `timestamps()` 헬퍼 |

인덱스

| 이름 | 대상 | 왜 |
|---|---|---|
| `ix_chunk_doc` | `(document_id, seq)` | 문서별 조회·삭제 |
| `ix_chunk_stale` | `(document_id, text_version)` | stale 판정 |
| `ix_chunk_vec` | `embedding` · **HNSW** `vector_cosine_ops` | 유사도 검색 |

`UNIQUE (document_id, seq)` 를 걸어 재색인 중복을 막는다.

**선행 조건 세 개** (결과서 11.0절)

| | 할 일 | 주의 |
|---|---|---|
| 1 | DB 이미지를 pgvector 포함본으로 교체 | **`docker-compose.yml` 은 팀 공유 파일이다** |
| 2 | `requirements.txt` 에 `pgvector` 추가 | SQLAlchemy `Vector` 타입용 |
| 3 | `0010` 첫 줄에 `CREATE EXTENSION IF NOT EXISTS vector` | 테이블보다 먼저 |

---

## 8. 에러코드 추가분

`app/core/error_codes.py` 의 `ErrorCode` 에 두 개를 추가한다.
추가 기준이 파일 주석에 "프런트가 다르게 처리해야 하는가" 로 적혀 있고,
둘 다 화면 문구가 달라야 하므로 기준을 만족한다.

| 코드 | HTTP | 사용자 문구 | 언제 |
|---|---|---|---|
| `EMBEDDING_NOT_READY` | `409` | 아직 검색 준비가 되지 않았습니다. 문서 처리가 끝나면 다시 시도해 주세요. | 청크·벡터가 없다 |
| `EMBEDDING_MODEL_MISMATCH` | `409` | 검색 색인이 오래되었습니다. 다시 색인해 주세요. | 저장된 벡터의 모델·차원이 설정과 다르다 |

재사용하는 기존 코드 — `PROJECT_NOT_FOUND`(404) · `DOCUMENT_NOT_FOUND`(404) ·
`AI_MODEL_NOT_LOADED`(503) · `VALIDATION_ERROR`(422).

---

## 9. 구현 순서와 막는 것

| | 할 일 | 막는 것 |
|---|---|---|
| 1 | DB 이미지 교체 · `pgvector` 패키지 | **팀 합의** (`.yml` 공유 파일) |
| 2 | 리비전 `0010` — 확장 · `document_chunks` | 재정 `0008` 머지 (번호 충돌) |
| 3 | `RAG-01` 청킹 | **재정 `REV-17` 완료** + `element_type` 값 집합 합의 |
| 4 | `RAG-02` 임베딩 생성·저장 | 3번 |
| 5 | **R1 `mode=keyword`** | 없음 — **지금 만들 수 있다** |
| 6 | R1 `mode=semantic` · `hybrid` | 4번 |
| 7 | R3 재색인 | 4번 |
| 8 | R2 단가 선례 | `AMT-13`(리비전 `0009`) |

**5번을 먼저 만들 수 있다.** `mode=keyword` 는 기존 `ILIKE` 검색을 청크가 아니라
`extracted_texts` 에서 하는 것이라 벡터가 없어도 된다. 계약과 화면을 먼저
맞춰두고 `semantic` 을 나중에 켜면 프런트가 두 번 고치지 않는다.

---

## 10. 합의가 필요한 것

| | 안건 | 제안 |
|---|---|---|
| 1 | `RAG-12` 가 프로젝트 경계를 넘는 것 | **B 안** — 내가 멤버인 프로젝트 전체. 출처에 프로젝트명 필수 |
| 2 | 결과 단위를 청크로 | **청크.** 문서로 뭉치면 `RAG-08` 인용이 사라진다 |
| 3 | `mode` 기본값 | **`hybrid`.** 한쪽만 쓰면 절반을 놓친다 (결과서 8.6절) |
| 4 | R3 응답을 `202` 로 적고 지금은 `200` 으로 내는 것 | `SYS-02` 이후 응답만 바뀐다 |
| 5 | `element_type` 값 집합 | **재정님과 합의 필요.** 현재 `"TEXT_LINE"` 하나만 확인됨 |
| 6 | 에러코드 2종 추가 | `SYS-03` 담당이 보현이라 바로 넣을 수 있다 |
