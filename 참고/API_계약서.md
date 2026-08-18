# API 계약서 v1 — PDF Brief AI

> D1(7/31) 15:00–16:00 합의용 초안. **이 문서에 3명이 동의한 뒤에 코드를 짠다.**
> 합의 후에는 변경 시 팀 전체에 공유 → 프론트/백 동시 수정.

**Base URL**: `/api`
**공통**: 인증 없음 / 응답 `Content-Type: application/json` (다운로드 제외)

---

## 0. 스키마를 어떤 형식으로 합의하나

3단계로 진행하면 어긋남이 없어:

```
1) 이 Markdown 표로 합의        ← 지금 (사람이 읽는 계약)
2) Pydantic 스키마 코드로 확정   ← D1 저녁 (기계가 강제하는 계약)
3) FastAPI가 자동 생성하는 /docs ← 이후 계속 (살아있는 문서)
```

**Pydantic 스키마가 곧 계약서야.** Spring의 DTO + `@Valid`가 합쳐진 것이고,
FastAPI는 이걸로 요청 검증 + 응답 직렬화 + **Swagger 문서 자동 생성**까지 해줌.
→ `http://localhost:8000/docs` 에서 프론트 담당이 직접 눌러보며 개발 가능. **별도 API 문서 관리 불필요.**

---

## 1. 엔드포인트 목록

| # | Method | Path | 설명 | 담당 |
|---|---|---|---|---|
| 1 | POST | `/api/documents` | 파일 업로드 + 텍스트 추출 | A |
| 2 | POST | `/api/documents/{id}/analyze` | LLM 요약·분류 실행 | B |
| 3 | GET | `/api/documents` | 목록 + 검색 + 페이징 | C |
| 4 | GET | `/api/documents/{id}` | 상세 (원문 + 분석결과) | C |
| 5 | GET | `/api/documents/{id}/download` | 결과 파일 다운로드 | C |
| 6 | DELETE | `/api/documents/{id}` | 삭제 (선택) | C |

---

## 2. 상세 명세

### ① POST /api/documents — 업로드

**Request** `multipart/form-data`

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `file` | File | ✅ | 최대 10MB, `.pdf` `.docx` `.hwpx` `.png` `.jpg` |
| `document_type` | string | ❌ | 기본값 `"general"` |

**Response `201 Created`**

```json
{
  "id": 1,
  "filename": "보고서.pdf",
  "file_type": "pdf",
  "document_type": "general",
  "status": "EXTRACTED",
  "page_count": 12,
  "extract_method": "TEXT_LAYER",
  "char_count": 8423,
  "created_at": "2026-07-31T15:20:11"
}
```

- `extract_method`: `TEXT_LAYER` | `OCR` | `DOCX` | `HWPX` ← **추출 경로 분기 결과. 발표 자료로도 씀**
- `status`: `EXTRACTED` (성공) | `FAILED`

**에러**: `400` 확장자 미지원 / `413` 용량 초과 / `422` 추출 실패(빈 텍스트)

---

### ② POST /api/documents/{id}/analyze — 분석

**Request**

```json
{
  "analyzer_types": ["summary", "category"]
}
```

- 생략 시 기본값 `["summary", "category"]`

**Response `200 OK`**

```json
{
  "document_id": 1,
  "analyses": [
    {
      "id": 10,
      "analyzer_type": "summary",
      "result": {
        "summary": "이 문서는 ...",
        "key_points": ["...", "...", "..."]
      },
      "provider": "openai",
      "model_name": "gpt-4o-mini",
      "tokens_in": 3200,
      "tokens_out": 280,
      "latency_ms": 4120,
      "created_at": "2026-07-31T15:22:03"
    },
    {
      "id": 11,
      "analyzer_type": "category",
      "result": {
        "category": "기술문서",
        "keywords": ["OCR", "요약", "FastAPI"],
        "confidence": 0.87
      },
      "provider": "openai",
      "model_name": "gpt-4o-mini",
      "tokens_in": 3200,
      "tokens_out": 90,
      "latency_ms": 1850,
      "created_at": "2026-07-31T15:22:05"
    }
  ]
}
```

**⚠️ 중요**: `result`는 `analyzer_type`에 따라 구조가 다름 (`Dict[str, Any]`).
→ **분석기를 추가해도 응답 형태를 바꾸지 않아도 되는 구조.** 확장성의 핵심.

**에러**: `404` 문서 없음 / `409` 아직 추출 안 됨 / `502` AI 호출 실패 / `504` 타임아웃

---

### ③ GET /api/documents — 목록 + 검색

**Query Parameters**

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `q` | string | — | 파일명 + 원문 텍스트 부분 검색 |
| `document_type` | string | — | 필터 |
| `category` | string | — | 분석된 카테고리 필터 |
| `page` | int | 1 | 1부터 |
| `size` | int | 20 | 최대 100 |

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": 1,
      "filename": "보고서.pdf",
      "document_type": "general",
      "status": "COMPLETED",
      "category": "기술문서",
      "summary_preview": "이 문서는 ...",
      "created_at": "2026-07-31T15:20:11"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 37,
  "total_pages": 2
}
```

> 목록에는 **요약 미리보기만** (100자 내). 전문은 상세에서. 응답 크기 관리용.

---

### ④ GET /api/documents/{id} — 상세

**Response `200 OK`**

```json
{
  "id": 1,
  "filename": "보고서.pdf",
  "file_type": "pdf",
  "document_type": "general",
  "status": "COMPLETED",
  "page_count": 12,
  "extract_method": "TEXT_LAYER",
  "extracted_text": "전체 원문 ...",
  "analyses": [ /* ②와 동일 구조 */ ],
  "created_at": "2026-07-31T15:20:11"
}
```

---

### ⑤ GET /api/documents/{id}/download — 다운로드

**Query**: `format` = `txt` (필수 구현) | `pdf` (여유 시)

**Response `200 OK`**
- `Content-Type`: `text/plain; charset=utf-8` 또는 `application/pdf`
- `Content-Disposition`: `attachment; filename="보고서_요약.txt"`

> 한글 파일명은 `filename*=UTF-8''...` 형식 병기 필요 (브라우저 호환)

---

## 3. 공통 에러 응답 (전 엔드포인트 동일)

```json
{
  "error_code": "DOCUMENT_NOT_FOUND",
  "message": "문서를 찾을 수 없습니다.",
  "request_id": "a1b2c3d4"
}
```

| error_code | HTTP | 상황 |
|---|---|---|
| `INVALID_FILE_TYPE` | 400 | 지원하지 않는 확장자 |
| `FILE_TOO_LARGE` | 413 | 10MB 초과 |
| `EXTRACTION_FAILED` | 422 | 텍스트 추출 실패 (빈 결과) |
| `DOCUMENT_NOT_FOUND` | 404 | 존재하지 않는 id |
| `NOT_EXTRACTED_YET` | 409 | 추출 전에 분석 요청 |
| `AI_PROVIDER_ERROR` | 502 | LLM API 실패 |
| `AI_TIMEOUT` | 504 | LLM 응답 초과 |
| `INTERNAL_ERROR` | 500 | 기타 |

- `error_code`는 **Enum으로 관리** → 프론트가 문자열로 분기
- `request_id`는 미들웨어가 발급 → 로그 추적용 (Spring의 MDC와 동일 개념)

---

## 4. status 값 (Enum)

```
PENDING     업로드 직후
EXTRACTING  추출 중
EXTRACTED   추출 완료 (분석 대기)
ANALYZING   분석 중
COMPLETED   분석 완료
FAILED      실패
```

프론트의 로딩 UI가 이 값으로 분기 → **지시서의 "로딩 상태 UI" 요구사항 충족**

---

## 5. Pydantic 스키마 (D1 저녁 작성)

```python
# schemas/document.py
from pydantic import BaseModel, Field
from typing import Any, Literal
from datetime import datetime

class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    document_type: str
    status: str
    page_count: int | None = None
    extract_method: str | None = None
    char_count: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}   # SQLAlchemy 객체 → 스키마 변환

class AnalysisResponse(BaseModel):
    id: int
    analyzer_type: str
    result: dict[str, Any]          # analyzer별로 구조가 다름
    provider: str
    model_name: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

class AnalyzeRequest(BaseModel):
    analyzer_types: list[Literal["summary", "category"]] = ["summary", "category"]

class DocumentListResponse(BaseModel):
    items: list["DocumentSummary"]
    page: int
    size: int
    total: int
    total_pages: int
```

---

## 6. 합의 체크리스트 (D1 16:00까지)

- [ ] 엔드포인트 6개 경로·메서드 확정
- [ ] 필드명 확정 (**camelCase vs snake_case → snake_case로 통일** 권장)
- [ ] `analyzer_type` 값: `"summary"`, `"category"` 문자열 확정
- [ ] `status` Enum 6개 확정
- [ ] `error_code` 목록 확정
- [ ] 파일 크기 상한 확정 (10MB?)
- [ ] 분석을 **업로드와 분리**할지 합의 → 분리 권장 (실패 시 재시도 쉬움)
- [ ] 프론트에서 쓸 타입 정의를 C가 이 문서 기준으로 작성


---

# 추가 — 의미 검색 (RAG-04)

> **작성 2026-08-18 · 보현 초안 · 팀 검토 대기**
>
> 이 절은 위 1~2절(미니 프로젝트 시절 `/api/documents` 계열, 담당 A/B/C)과 경로
> 규칙이 다르다. 현재 본 프로젝트는 프로젝트 범위 경로
> `/api/projects/{project_id}/...` 를 쓴다 (`analysis_router.py` 등 기존 라우터와 동일).
>
> **재정님 · 세현님께**: 구현을 먼저 올렸습니다. 바꿔야 할 부분 있으면 말씀해 주세요.
> 프론트(`SearchView`)가 아직 안 붙었으니 지금이 고치기 가장 쉬운 시점입니다.

## 이 절에 나오는 기능 ID

| ID | 작업명 |
|---|---|
| `RAG-04` | 의미 검색 — 글자가 겹치지 않는 질의로 관련 문서를 찾는다 |
| `RAG-05` | 하이브리드 검색 (키워드 + 벡터) · P2 |
| `RAG-08` | 근거 스니펫 연결 — 결과마다 출처와 원문 인용 |
| `VIS-07` | 검색 화면의 의미 검색 표시 · P2 |

## 엔드포인트

| # | Method | Path | 설명 | 담당 |
|---|---|---|---|---|
| S1 | POST | `/api/projects/{project_id}/search` | 의미 검색 | 보현 |
| S2 | POST | `/api/projects/{project_id}/search/explain` | 실행계획 (검증용 · 임시) | 보현 |

기존 `GET /api/documents?q=` 와 **별도 엔드포인트로 둔 이유**

| | |
|---|---|
| 반환 단위가 다르다 | 그쪽은 **문서 목록**, 이쪽은 **청크 + 원문 인용** |
| 나중에 합친다 | `RAG-05` 하이브리드에서 이쪽에 키워드 점수를 더하는 방향이 맞다. 지금 억지로 한 엔드포인트에 넣으면 응답 스키마가 두 가지 모양을 가진다 |

`GET` 이 아니라 `POST` 인 이유

1. 질의가 문장이다. URL 에 넣으면 한글이 퍼센트 인코딩되어 길어진다
2. 필터가 늘어난다 (문서 유형 · 기간 · 하이브리드 가중치)
3. **검색 질의가 브라우저 이력과 접근 로그에 남지 않는다.** 조달 문서를 다루므로 "무엇을 찾고 있는지"가 사업 정보다

## S1. POST /api/projects/{project_id}/search

**권한**: 프로젝트 멤버 누구나 (`VIEWER` 포함). 읽기 전용이다.
멤버가 아니면 `404 PROJECT_NOT_FOUND` — 프로젝트 존재 자체를 숨긴다.

**Request**

| 필드 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `query` | string | 필수 | 자연어 질의. 1~1000자 |
| `limit` | int | 10 | 1~50 |
| `document_id` | int \| null | null | 특정 문서 안에서만 찾을 때 |
| `min_similarity` | float \| null | null | 이 값보다 낮은 결과는 버린다. −1.0~1.0 |

```json
{
  "query": "대금은 언제 받을 수 있나요",
  "limit": 10
}
```

**Response `200 OK`**

```json
{
  "query": "대금은 언제 받을 수 있나요",
  "embedding_model": "fake-hash-v1",
  "took_ms": 42,
  "total": 2,
  "results": [
    {
      "chunk_id": 128,
      "document_id": 3,
      "document_filename": "입찰공고.pdf",
      "seq": 4,
      "page_number": 2,
      "similarity": 0.8312,
      "snippet": "4. 대금 지급 준공 검사 완료 후 30일 이내에 지급한다. 선금은 계약 금액의 70퍼센트 범위에서…",
      "char_count": 412,
      "content_start": 279,
      "content_end": 371
    }
  ]
}
```

| 필드 | 설명 |
|---|---|
| `embedding_model` | 이 검색에 쓴 모델. **`fake-hash-v1` 이면 의미 없는 개발용 벡터다** |
| `similarity` | 코사인 유사도. 1.0 이 가장 가깝다 (pgvector `<=>` 거리를 `1 - distance` 로 변환) |
| `snippet` | 원문 인용 (`RAG-08`). 최대 220자. 청킹이 제목을 청크 맨 앞에 두므로 **앞부분이 곧 제목**이다 |
| `char_count` | 청크 전체 길이. `snippet` 이 잘렸는지 프론트가 판단한다 |
| `content_start` · `content_end` | `extracted_texts.content` 안의 구간. 원문 대조용. 모르면 `null` |

**제목을 별도 필드로 주지 않는다.** `document_chunks` 에 `heading` 컬럼이 없다.
청킹이 `Chunk.heading` 을 계산하지만 저장하지 않는다. 계층 표시
("출처: 제2장 > 4. 대금 지급")를 하려면 컬럼 추가가 필요하고 그건 마이그레이션이라
별도 안건으로 둔다. 지금은 `snippet` 앞부분이 제목 역할을 한다.

**에러**

| 코드 | 상황 |
|---|---|
| `401 UNAUTHORIZED` | 토큰 없음·만료 |
| `404 PROJECT_NOT_FOUND` | 프로젝트 없음 또는 멤버 아님 |
| `422` | `query` 빈 문자열, `limit` 범위 초과 등 (FastAPI 검증) |

## S2. POST /api/projects/{project_id}/search/explain

요청은 S1 과 같고 응답은 `{"plan": "<EXPLAIN ANALYZE 출력>"}` 이다.

**운영 기능이 아니다.** 리비전 `0014` 에서 `document_chunks.project_id` 를
역정규화한 근거가 "조건이 인덱스 스캔 단계로 내려간다"였는데, 청크가 0행이던
동안 확인할 수 없었다. 검증이 끝나면 지우거나 관리자 전용으로 옮긴다.

## 검색 조건 두 개 — 둘 다 필수다

```sql
WHERE project_id = :project_id
  AND embedding_model = :model
ORDER BY embedding <=> :query_vector
LIMIT :limit
```

| 조건 | 없으면 |
|---|---|
| `project_id` | 다른 프로젝트 문서가 섞인다 (`RAG-04` 판정 기준 위반). 조인이 아니라 **같은 테이블 컬럼**이어야 `hnsw.iterative_scan` 이 스캔 단계에서 평가한다 — 리비전 `0014` 를 넣은 이유 |
| `embedding_model` | **에러 없이 조용히 틀린다.** 모델을 바꾸거나 가짜 임베더 청크가 섞이면 서로 다른 벡터 공간의 거리를 비교한다. 숫자는 나오지만 의미가 없다 |

세션 파라미터를 트랜잭션 범위로 설정한다.

```sql
SET LOCAL hnsw.iterative_scan = strict_order;
SET LOCAL hnsw.ef_search = 100;
```

`ef_search` 기본값 40 은 조건이 걸린 상황에서 후보가 모자란다.
`SEARCH_EF_SEARCH` 설정으로 조절한다.

## 아직 검증하지 못한 것

`RAG-04` 판정 기준은 "**글자가 하나도 겹치지 않는 질의**로 관련 문서가 나온다"다.
**기본값인 가짜 임베더(`USE_FAKE_EMBEDDING=true`)로는 이것을 검증할 수 없다** —
해시 벡터에는 의미가 없다.

| 검증 가능 | 검증 불가 |
|---|---|
| 검색이 동작한다 | **의미적으로 맞는 결과가 나오는지** |
| 다른 프로젝트 문서가 안 나온다 | |
| 실행계획이 인덱스를 탄다 | |
| 스니펫·출처가 붙는다 | |

즉 현재 `RAG-04` 는 **구조 완성 · 품질 미검증** 상태다.
