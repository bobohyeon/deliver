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
