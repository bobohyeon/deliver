# API 계약서 v2 — DocFlow

> **이 문서에 3명이 동의한 뒤에 코드를 짠다.** 합의 후 변경 시 팀 전체에 공유 →
> 프론트·백 동시 수정.
>
> v1 은 `참고/API_계약서.md` 에 그대로 남긴다. 미니 프로젝트 6개 엔드포인트가
> 어떻게 확장됐는지 대조용이다.

**Base URL** `/api` · **인증** JWT Bearer (`/api/auth/*` 제외 전부 필수)
**필드명** snake_case (v1 합의 유지) · **응답** `application/json` (다운로드 제외)

기능 ID 는 `관리/기능명세서.md`, 스키마는 `관리/DocFlow_DB.dbml` 을 따른다.

---

## 0. 합의 방식 — v1 과 같다

```
1) 이 Markdown 으로 합의          ← 지금 (사람이 읽는 계약)
2) Pydantic 스키마로 확정          ← 8/12 (기계가 강제하는 계약)
3) FastAPI /docs 가 살아있는 문서   ← 이후 계속
```

**Pydantic 스키마가 곧 계약서다.** 미니 프로젝트에서 이 방식으로 세 명이 페이크
구현체를 놓고 병렬 작업했고, 본프로젝트도 같이 간다.

> **Spring 비교** — Pydantic 스키마는 DTO + `@Valid` 가 합쳐진 것이고,
> `/docs` 는 Springdoc OpenAPI 가 자동 생성하는 Swagger UI 에 해당한다.

---

## 1. v1 에서 무엇이 바뀌었나

| | v1 | v2 |
|---|---|---|
| 엔드포인트 | 6개 | **50개** |
| 인증 | 없음 | **JWT** |
| 스코프 | 없음 | **`project_id` 필수** |
| 업로드 응답 | `201` + 추출 완료 | **`202`** + 큐 적재 (`DOC-06`) |
| 분석기 | 2개 (`summary` `category`) | **4개** (+ `extract` `amount`) |
| 제안 승인 | 없음 | **4종 통합 API** |
| 산출물 | txt 다운로드 | **주간보고 · 결정대장 · 회의안건 생성** |

### 하위 호환을 버린다

v1 의 `/api/documents` (프로젝트 없는 업로드·목록)는 **유지하지 않는다.**
`project_id` 가 NOT NULL 이 되므로 스코프 없는 경로가 성립하지 않는다. 기존
데이터는 마이그레이션용 기본 프로젝트로 옮긴다.

**단, `/api/ocr-compare`(미니 프로젝트 OCR 엔진 비교)는 남긴다.** 개발·측정용이고
인증 뒤로 숨겨 관리자 전용으로 격리한다.

---

## 2. 공통 규약

### 인증

```
Authorization: Bearer <access_token>
```

**모든 프로젝트 스코프 API 에 `get_current_user` 의존성을 붙인다** (`AUTH-05`).
라우터마다 손으로 검사하면 누락되므로 의존성 주입으로 강제한다.

### 스코프 강제 (`PRJ-08`)

**경로에 `project_id` 가 없는 엔드포인트도 스코프를 검사한다.**
`GET /api/documents/{document_id}` 는 그 문서가 내가 멤버인 프로젝트에 속하는지
**리포지토리 계층에서** 확인하고, 아니면 `403` 이 아니라 **`404`** 를 낸다.

> `403` 을 주면 "그 id 의 문서가 존재한다" 는 정보가 새어 나간다.

### 페이징 — v1 형식 유지

| 파라미터 | 기본 | 설명 |
|---|---|---|
| `page` | 1 | 1부터 |
| `size` | 20 | 최대 100 |

```json
{ "items": [], "page": 1, "size": 20, "total": 37, "total_pages": 2 }
```

### 권한

`OWNER` / `EDITOR` / `VIEWER`. 쓰기는 `EDITOR` 이상, 멤버·프로젝트 관리는 `OWNER`.
**`VIEWER` 의 금액 조회 여부는 미결** (`AMT-11`).

---

## 3. 엔드포인트 목록

### A. 인증 — 담당 세현

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 1 | POST | `/api/auth/register` | 회원가입 | `AUTH-01` | P0 |
| 2 | POST | `/api/auth/login` | 로그인 | `AUTH-02` | P0 |
| 3 | POST | `/api/auth/refresh` | 토큰 갱신 | `AUTH-04` | P0 |
| 4 | POST | `/api/auth/logout` | 로그아웃 | `AUTH-04` | P0 |
| 5 | GET | `/api/auth/me` | 내 정보 | `AUTH-03` | P0 |

### B. 프로젝트 — 담당 세현

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 6 | GET | `/api/projects` | 내 프로젝트 목록 | `PRJ-02` | P0 |
| 7 | POST | `/api/projects` | 생성 | `PRJ-01` | P0 |
| 8 | GET | `/api/projects/{pid}` | 상세 | `PRJ-03` | P0 |
| 9 | PATCH | `/api/projects/{pid}` | 수정 · 보관 | `PRJ-03`·`PRJ-04` | P0 |
| 10 | DELETE | `/api/projects/{pid}` | 삭제 | `PRJ-05` | P0 |
| 11 | GET | `/api/projects/{pid}/members` | 멤버 목록 | `PRJ-06` | P0 |
| 12 | POST | `/api/projects/{pid}/members` | 초대 | `PRJ-06` | P0 |
| 13 | PATCH | `/api/projects/{pid}/members/{uid}` | 역할 변경 | `PRJ-07` | P0 |
| 14 | DELETE | `/api/projects/{pid}/members/{uid}` | 제거 | `PRJ-07` | P0 |

### C. 문서 — 담당 재정 (`16`·`19` 보현)

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 15 | POST | `/api/projects/{pid}/documents` | **업로드 → 202** | `DOC-01`·`DOC-06` | P0 |
| 16 | GET | `/api/projects/{pid}/documents` | 목록 · 검색 · 필터 | `DOC-08` | P0 |
| 17 | GET | `/api/documents/{did}` | 상세 | `DOC-09` | P0 |
| 18 | GET | `/api/documents/{did}/status` | **진행 상태 폴링** | `DOC-07` | P0 |
| 19 | PATCH | `/api/documents/{did}` | 문서 유형 수정 | `DOC-16` | P1 |
| 20 | GET | `/api/documents/{did}/file` | 원본 다운로드 | `DOC-10` | P0 |
| 21 | DELETE | `/api/documents/{did}` | 삭제 | `DOC-11` | P0 |
| 22 | POST | `/api/documents/{did}/analyze` | 분석 실행 · 재분석 | `ANL-*`·`DOC-12` | P0 |

### D. OCR 검수 — 담당 재정

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 23 | GET | `/api/documents/{did}/pages` | 페이지 이미지 · 좌표 기준 크기 | `REV-01` | P1 |
| 24 | GET | `/api/documents/{did}/ocr-elements` | 박스 목록 (`page`·`max_confidence` 필터) | `REV-02`·`REV-06` | P1 |
| 25 | PATCH | `/api/ocr-elements/{eid}` | **텍스트·좌표 수정 (version 필요)** | `REV-05`·`REV-16` | P1 |
| 26 | POST | `/api/documents/{did}/review/complete` | 검수 완료 → 분석 1회 | `REV-07` | P1 |
| 27 | POST | `/api/documents/{did}/ocr-elements` | 박스 생성 | `REV-09` | P2 |
| 28 | DELETE | `/api/ocr-elements/{eid}` | 논리 삭제 | `REV-09` | P2 |
| 29 | POST | `/api/documents/{did}/re-ocr` | 선택 영역 재OCR | `REV-11` | P2 |
| 30 | PATCH | `/api/documents/{did}/reading-order` | 읽기 순서 · 단락 | `REV-12`·`REV-13` | P2 |

### E. 일괄 처리 — 담당 재정

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 31 | POST | `/api/projects/{pid}/batch-jobs` | 일괄 등록 | `BAT-01` | P1 |
| 32 | GET | `/api/batch-jobs/{jid}` | 전체 진행률 | `BAT-02` | P1 |
| 33 | GET | `/api/batch-jobs/{jid}/items` | 파일별 상태 | `BAT-02` | P1 |
| 34 | POST | `/api/batch-jobs/{jid}/retry` | 실패 재시도 | `BAT-04` | P2 |

### F. 제안 승인 — 담당 보현 (승인 후 태스크 생성은 세현)

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 35 | GET | `/api/documents/{did}/suggestions` | **제안 4종 조회** | `ANL-03`·`ANL-14`·`ANL-15`·`AMT-01` | P1 |
| 36 | PATCH | `/api/suggestions/{kind}/{sid}` | **승인 · 수정 · 거부** | `TSK-03`·`TSK-07`·`AMT-02` | P1 |
| 37 | POST | `/api/documents/{did}/suggestions/approve` | 일괄 승인 | `TSK-08` | P1 |

### G. 태스크 — 담당 세현

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 38 | GET | `/api/projects/{pid}/tasks` | 보드 (필터) | `TSK-02`·`TSK-05` | P1 |
| 39 | POST | `/api/projects/{pid}/tasks` | 직접 생성 | `TSK-01` | P1 |
| 40 | PATCH | `/api/tasks/{tid}` | 수정 · 상태 변경 | `TSK-01`·`TSK-06` | P1 |
| 41 | DELETE | `/api/tasks/{tid}` | 삭제 | `TSK-01` | P1 |

### H. 산출물 — 담당 보현

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 42 | GET | `/api/projects/{pid}/deliverables/preview` | **생성 대상 미리보기** | `DLV-03` | P1 |
| 43 | POST | `/api/projects/{pid}/deliverables` | **생성** | `DLV-04`~`DLV-07` | P1 |
| 44 | GET | `/api/projects/{pid}/deliverables` | 생성 이력 | `DLV-09` | P1 |
| 45 | GET | `/api/deliverables/{delid}/file` | 다운로드 | `DLV-09` | P1 |
| 46 | DELETE | `/api/deliverables/{delid}` | 삭제 | `DLV-09` | P2 |

### I. 가시성 — 담당 공통

| # | Method | Path | 설명 | 기능 | 우선 |
|---|---|---|---|---|---|
| 47 | GET | `/api/projects/{pid}/dashboard` | 지표 카드 · 유형 분포 | `VIS-01`·`VIS-02` | P2 |
| 48 | GET | `/api/projects/{pid}/search` | 통합 검색 | `VIS-06` | P2 |
| 49 | GET | `/api/projects/{pid}/activities` | 활동 타임라인 | `VIS-09` | P2 |
| 50 | GET | `/api/projects/{pid}/amount-summary` | 금액 현황 | `AMT-08` | P2 |

**P0 21개 · P1 19개 · P2 10개 = 50개.** 미니 프로젝트 6개에서 늘었지만 **절반이 단순 CRUD** 다.

---

## 4. 상세 명세 — 새로 생긴 것 위주

### ① POST `/api/projects/{pid}/documents` — 업로드

**v1 과 가장 크게 달라진 지점이다. `201` → `202`.**

**Request** `multipart/form-data`

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `file` | File | O | 최대 **20MB**, `.pdf` `.docx` `.hwpx` `.png` `.jpg` |
| `processing_mode` | string | — | `NORMAL`(기본) · `REVIEW` |
| `document_type` | string | — | 7종 중 하나. **생략하면 자동 판별** |

**Response `202 Accepted`**

```json
{
  "id": 42,
  "filename": "용역계약서_최종.pdf",
  "file_type": "pdf",
  "status": "PENDING",
  "processing_mode": "NORMAL",
  "document_type": null,
  "document_type_source": null,
  "created_at": "2026-08-17T10:04:11+09:00"
}
```

**`202` 로 바꾼 이유** — 미니 프로젝트는 업로드 요청 스레드에서 OCR 을 직접
돌렸다. 24페이지 스캔 PDF 면 요청 하나가 수 분을 잡는다. 큐에 넣고 즉시 반환한다.

**`document_type` 이 `null` 이면 "아직 모름"** 이다. 분류 분석기가 채우면
`document_type_source` 가 `AI` 가 된다. 사람이 골랐으면 `USER` 다.

**에러** `415` 미지원 형식 · `413` 20MB 초과 · `403` `VIEWER` 는 업로드 불가

---

### ② GET `/api/documents/{did}/status` — 진행 상태 폴링

**분석기가 늘어도 화면을 안 고치게 만드는 게 핵심이다** (`ANL-05`).

```json
{
  "id": 42,
  "status": "ANALYZING",
  "review_status": "NOT_REQUIRED",
  "ocr_revision": 1,
  "steps": [
    { "key": "upload",  "label": "업로드",     "state": "DONE" },
    { "key": "extract", "label": "텍스트 추출", "state": "DONE",
      "meta": { "extract_method": "OCR", "avg_confidence": 0.94 } },
    { "key": "analyze", "label": "분석",       "state": "RUNNING",
      "done": 3, "total": 4,
      "detail": [
        { "analyzer_type": "summary",  "state": "DONE" },
        { "analyzer_type": "category", "state": "DONE" },
        { "analyzer_type": "extract",  "state": "DONE" },
        { "analyzer_type": "amount",   "state": "RUNNING" }
      ] },
    { "key": "done",    "label": "완료",       "state": "PENDING" }
  ]
}
```

**`steps` 를 서버가 만들어 내려준다.** 프론트는 배열을 그리기만 한다.

| 규칙 | |
|---|---|
| `steps` 길이는 **고정 4개** | 업로드 · 추출 · 분석 · 완료 |
| 분석기 수는 `done` / `total` 로 표현 | 분석기가 5개가 돼도 화면 코드 불변 |
| `detail` 은 접힌 상세용 | 없어도 화면이 성립한다 |

**목업이 `④ 액션 아이템 추출` 로 분석기 이름을 단계에 박아둔 문제가 여기서
해소된다.**

`state` — `PENDING` · `RUNNING` · `DONE` · `FAILED` · `NEEDS_REVIEW`

**폴링 주기 2초** 를 권한다. `BAT-06` SSE 는 P2 이므로 MVP 는 폴링이다.

---

### ③ POST `/api/documents/{did}/analyze` — 분석 실행

**Request**

```json
{ "analyzer_types": null, "force": false }
```

| 필드 | 설명 |
|---|---|
| `analyzer_types` | `null` 이면 **기본 4개 전부**. 개발·부분 재분석용으로만 지정 |
| `force` | `true` 면 최신 `ocr_revision` 기준으로 다시 돌린다 (`DOC-12`) |

**Response `200 OK`**

```json
{
  "document_id": 42,
  "source_text_revision": 3,
  "analyses": [
    { "id": 101, "analyzer_type": "summary",
      "result": { "summary": "이 계약은 ..." },
      "provider": "openai", "model_name": "gpt-4o-mini",
      "prompt_version": "v1", "tokens_in": 2791, "tokens_out": 125,
      "latency_ms": 3210, "created_at": "..." },
    { "id": 102, "analyzer_type": "category",
      "result": { "category": "CONTRACT", "reason": "당사자와 계약금액 조항이 있어 계약서로 판단" },
      "...": "..." },
    { "id": 103, "analyzer_type": "extract",
      "result": { "action_items": 3, "decisions": 2, "schedule_items": 1 },
      "...": "..." },
    { "id": 104, "analyzer_type": "amount",
      "result": { "amount_items": 2 },
      "...": "..." }
  ]
}
```

**`result` 는 `analyzer_type` 마다 구조가 다르다** (`dict[str, Any]`). v1 의 핵심
결정을 그대로 유지한다 — **분석기를 추가해도 응답 스펙이 바뀌지 않는다.**

**`extract` · `amount` 의 `result` 에는 개수만 담고 항목은 테이블에 넣는다.**
항목은 `#35 GET /suggestions` 로 따로 조회한다. 승인·거부 상태를 항목 단위로
관리해야 하고 태스크가 참조해야 하기 때문이다.

**분석기 4개는 `asyncio.gather` 로 동시 실행된다.** 문서 유형으로 고르지 않는다 —
회의록·보고서에도 금액이 나오므로 유형으로 껐다 켜면 놓친다.

**에러** `404` 문서 없음 · `409` `NOT_EXTRACTED_YET` · `502` `AI_PROVIDER_ERROR`
· `504` `AI_TIMEOUT`

---

### ④ GET `/api/documents/{did}/suggestions` — 제안 4종 조회

**Query** `decision` = `PENDING`(기본) · `ALL`

```json
{
  "document_id": 42,
  "source_text_revision": 3,
  "is_stale": false,
  "action_items": [
    { "id": 11, "title": "하도급 계약 조항 검토",
      "assignee_hint": null, "due_date": null,
      "confidence": 0.78,
      "reason": "하도급 대금 조항에 재검토 문구가 있어 검토 과제로 판단",
      "decision": "PENDING" }
  ],
  "decisions": [
    { "id": 21, "title": "검수 절차를 단계별로 둔다",
      "content": "전체 일정 6개월에 단계별 검수를 넣는다",
      "status": "DECIDED", "decided_on": "2026-08-08",
      "confidence": 0.91, "reason": "참석자 합의 문구가 명시됨",
      "decision": "PENDING" }
  ],
  "schedule_items": [
    { "id": 31, "title": "API 명세 확정", "kind": "DEADLINE",
      "starts_on": null, "ends_on": "2026-08-15",
      "confidence": 0.88, "reason": "다음 주 금요일까지로 기한이 명시됨",
      "decision": "PENDING" }
  ],
  "amount_items": [
    { "id": 41, "item_name": "하도급 대금",
      "quantity": 1, "unit": null, "amount": 72000000, "currency": "KRW",
      "confidence": 0.93,
      "reason": "'하도급 대금은 총 ○원으로 한다' 문장에서 총액으로 명시된 값",
      "decision": "PENDING" },
    { "id": 42, "item_name": "감리 용역비",
      "quantity": 6, "unit": "개월", "amount": null, "currency": "KRW",
      "confidence": 0.71,
      "reason": "기간만 적혀 있고 금액이 문서에 없어 비워 둠",
      "decision": "PENDING" }
  ],
  "amount_check": {
    "items_total": 72000000,
    "document_total": 79200000,
    "diff": 7200000,
    "note": "부가세 누락 가능"
  }
}
```

**`amount_check` 가 이 API 의 핵심이다** (`AMT-03`). 항목 합계를 **Python 이
재계산**해 문서에 적힌 합계와 대조한다. **AI 가 뽑은 게 맞는지 검증할 수 있는
유일한 지점**이다.

**`amount` 가 `null` 인 항목을 그대로 둔다.** 문서에 금액이 안 적혀 있으면
비운다 — **AI 가 추측하면 그게 환각이다.**

**`is_stale`** 이 `true` 면 OCR 을 고친 뒤 재분석을 안 한 상태다 (`REV-18`).
화면에 "분석을 다시 실행해 주세요" 를 띄운다.

---

### ⑤ PATCH `/api/suggestions/{kind}/{sid}` — 승인 · 수정 · 거부

`kind` = `action_item` · `decision` · `schedule` · `amount`

**Request**

```json
{
  "decision": "APPROVED",
  "patch": { "assignee_id": 7, "due_date": "2026-08-15" }
}
```

| `decision` | 동작 |
|---|---|
| `APPROVED` | 확정. `action_item` · `amount` 는 **태스크를 생성**한다 |
| `EDITED` | `patch` 를 적용하고 확정 |
| `REJECTED` | 거부. **다시 뜨지 않고 기록은 남는다** (`TSK-07`) |

**Response `200 OK`**

```json
{
  "kind": "action_item", "id": 11, "decision": "APPROVED",
  "created_task": { "id": 501, "title": "하도급 계약 조항 검토", "status": "TODO" }
}
```

**승인해야 태스크가 된다.** 자동 등록 금지가 컨셉 원칙이고, 목업의
`승인해야 태스크로 등록됩니다. 자동 등록되지 않습니다` 문구가 이것이다.

**`REJECTED` 를 기록하지 않으면 채택률(`ANL-10`)을 계산할 수 없다.** 거부한 제안은
태스크가 되지 않으므로 `tasks` 에 남길 수 없다.

---

### ⑥ PATCH `/api/ocr-elements/{eid}` — 박스 수정

**Request**

```json
{
  "version": 3,
  "text": "72,000,000",
  "x1": 0.12, "y1": 0.35, "x2": 0.28, "y2": 0.39
}
```

**`version` 이 필수다** (`REV-16`). DB 값과 다르면 `409 CONFLICT` 를 낸다.

**Response `200 OK`**

```json
{
  "id": 880, "version": 4,
  "text": "72,000,000", "original_text": "12,000,000",
  "source": "MANUAL", "review_status": "REVIEWED",
  "document_ocr_revision": 4,
  "stale": { "analyses": 4, "amount_items": 2, "decisions": 1, "schedule_items": 0 }
}
```

**`stale` 이 revision 전파의 결과다.** 박스 하나를 고치면 `ocr_revision` 이 오르고
파생 데이터가 오래된 것이 된다. 화면은 이 숫자로 재분석 안내를 띄운다.

**좌표는 0~1 비율이다.** 픽셀이 아니라 페이지 크기 대비 비율이라 화면 확대·축소와
무관하게 같은 위치에 그려진다.

**`text` 와 좌표 수정은 같은 트랜잭션에서 `extracted_texts.content` 재조립까지
끝낸다** (`REV-17`). 안 그러면 화면 · 검색 · 분석이 서로 다른 값을 본다.

---

### ⑦ GET `/api/projects/{pid}/deliverables/preview` — 생성 대상 미리보기

**Query** `kind` · `period_from` · `period_to`

```json
{
  "kind": "WEEKLY_REPORT",
  "period_from": "2026-08-04", "period_to": "2026-08-10",
  "counts": {
    "documents": 7,
    "documents_by_type": { "MEETING_NOTES": 3, "CONTRACT": 2, "REPORT": 2 },
    "tasks_completed": 8,
    "tasks_created": 4,
    "decisions": 3,
    "decisions_pending": 2,
    "schedule_due_soon": 2,
    "schedule_overdue": 1,
    "amount_changes": 1,
    "pending_suggestions": 5
  },
  "warnings": ["승인 대기 제안 5건이 있습니다. 승인 후 생성하면 보고서에 반영됩니다."]
}
```

**LLM 을 호출하지 않는다. DB 쿼리뿐이라 공짜다.** 세 가지를 해결한다.

| | |
|---|---|
| 빈 보고서 방지 | 기간을 잘못 잡아 `documents: 0` 인 보고서를 만드는 걸 막는다 |
| 비용 절약 | **생성 전에** 무엇이 잡히는지 보인다 |
| 승인 유도 | `pending_suggestions` 로 "먼저 승인하시죠" 를 화면이 알려준다 |

---

### ⑧ POST `/api/projects/{pid}/deliverables` — 산출물 생성

**Request**

```json
{
  "kind": "WEEKLY_REPORT",
  "format": "XLSX",
  "period_from": "2026-08-04",
  "period_to": "2026-08-10"
}
```

| 필드 | 설명 |
|---|---|
| `kind` | `WEEKLY_REPORT` · `DECISION_LOG` · `MEETING_AGENDA` · `PROJECT_STATUS` |
| `format` | `XLSX` · `HTML` · `MD`. **기본값이 없다 — 반드시 지정한다** |
| `period_*` | `WEEKLY_REPORT` 만 필수. 나머지는 전체 누적이라 `null` |

**Response `201 Created`**

```json
{
  "id": 9,
  "kind": "WEEKLY_REPORT", "format": "XLSX",
  "title": "주간 보고서 2026-08-04 ~ 2026-08-10",
  "period_from": "2026-08-04", "period_to": "2026-08-10",
  "file_size": 24118,
  "source_counts": { "documents": 7, "tasks_completed": 8, "decisions": 3, "amount_changes": 1 },
  "is_stale": false,
  "generated_at": "2026-08-10T18:02:44+09:00",
  "download_url": "/api/deliverables/9/file"
}
```

**`format` 에 기본값을 두지 않는다.** 고르지 않으면 `422` 를 낸다. 사용자가
의도한 형식으로만 만들어야 나중에 "왜 md 로 나왔지" 가 없다.

**`source_counts` 가 갱신 판정의 근거다** (`DLV-10`). 목록 조회 시 현재 개수와
비교해 `is_stale` 을 계산하고 **"문서 2건이 나중에 추가됨"** 을 띄운다.

### 생성 비용 — LLM 호출 1회

```
주간 보고서
├─ 이번 주 개요        ← LLM 1회. 저장된 요약 N개를 재요약
├─ 문서 목록           ← DB 쿼리
├─ 완료 / 신규 태스크   ← DB 쿼리 (tasks.completed_at 필요)
├─ 이번 주 결정사항     ← DB 쿼리
├─ 기한 임박 · 지난     ← DB 쿼리 + 날짜 계산
└─ 금액 변동           ← DB 쿼리 + 코드 합산
```

**재요약의 입력이 원문이 아니라 저장된 요약이다.**

| 방식 | 문서 10건 입력 토큰 |
|---|---:|
| 원문을 다시 보낸다 | 약 28,000 |
| **저장된 요약만 보낸다** | **약 1,500** |

**주간 보고서 한 장이 문서 반 건 분석보다 싸다.** 그리고 개요 한 단락만 LLM 이
쓰므로 **같은 기간을 다시 누르면 같은 표가 나온다.**

---

### ⑨ GET `/api/documents/{did}` — 상세 (v1 확장)

```json
{
  "id": 42,
  "project_id": 3,
  "filename": "용역계약서_최종.pdf",
  "file_type": "pdf",
  "document_type": "CONTRACT",
  "document_type_source": "AI",
  "status": "COMPLETED",
  "review_status": "COMPLETED",
  "ocr_revision": 4,
  "page_count": 12, "char_count": 8423,
  "extract_method": "OCR", "ocr_engine": "paddle", "avg_confidence": 0.94,
  "processing_time_ms": 38210,
  "extracted_text": "전체 원문 ...",
  "analyses": [ "④와 동일 구조" ],
  "uploaded_by": { "id": 7, "name": "박세현" },
  "created_at": "..."
}
```

**v1 에서 추가된 것** — `project_id` · `document_type_source` · `review_status` ·
`ocr_revision` · `ocr_engine` · `avg_confidence` · `processing_time_ms` ·
`uploaded_by`.

---

### ⑩ GET `/api/projects/{pid}/tasks` — 보드

**Query** `status` · `assignee_id` · `is_ai_generated` · `source_kind` ·
`due_before` · `source_document_id`

```json
{
  "items": [
    {
      "id": 501, "title": "하도급 대금 합계 불일치 확인",
      "status": "TODO", "assignee_id": null, "due_date": null,
      "is_ai_generated": true,
      "source": {
        "kind": "amount",
        "document_id": 42,
        "document_filename": "용역계약서_최종.pdf",
        "reason": "항목 합계 72,000,000 과 문서 기재 79,200,000 이 다름",
        "diff_amount": 7200000
      },
      "created_at": "...", "completed_at": null
    }
  ],
  "page": 1, "size": 20, "total": 14, "total_pages": 1
}
```

**`source.kind` 로 필터가 가능해야 한다.** 금액 태스크는 보는 사람이 다르고
(회계·계약 담당) 우선순위도 다르다. `diff_amount` 를 카드에 노출해 **금액 영향
크기를 열지 않고도 알 수 있게** 한다.

**`completed_at` 이 없으면 `DLV-04` 주간 보고서를 만들 수 없다.**

---

## 5. 에러 코드

### v1 11종 유지

| error_code | HTTP |
|---|---|
| `INVALID_FILE_TYPE` | 415 |
| `FILE_TOO_LARGE` | 413 |
| `EXTRACTION_FAILED` | 422 |
| `DOCUMENT_NOT_FOUND` | 404 |
| `NOT_EXTRACTED_YET` | 409 |
| `ANALYZER_NOT_FOUND` | 400 |
| `AI_PROVIDER_ERROR` | 502 |
| `AI_TIMEOUT` | 504 |
| `INTERNAL_ERROR` | 500 |
| `VALIDATION_ERROR` | 422 |
| `DOWNLOAD_LIMIT_EXCEEDED` | 429 |

### v2 신규

| error_code | HTTP | 상황 |
|---|---|---|
| `UNAUTHORIZED` | 401 | 토큰 없음 · 만료 |
| `EMAIL_ALREADY_EXISTS` | 409 | 가입 중복 |
| `INVALID_CREDENTIALS` | 401 | 로그인 실패 |
| `FORBIDDEN_ROLE` | 403 | 권한 부족 |
| `PROJECT_NOT_FOUND` | 404 | **타 프로젝트 접근도 이 코드** |
| `ALREADY_MEMBER` | 409 | 중복 초대 |
| `OCR_ELEMENT_CONFLICT` | 409 | **`version` 불일치** |
| `REVIEW_NOT_COMPLETED` | 409 | 검수 미완료 상태에서 확정 요청 |
| `SUGGESTION_ALREADY_DECIDED` | 409 | 이미 승인·거부됨 |
| `DELIVERABLE_EMPTY` | 422 | **해당 기간에 담을 내용이 없다** |
| `FORMAT_REQUIRED` | 422 | `format` 미지정 |
| `QUOTA_EXCEEDED` | 429 | 프로젝트 월 호출 한도 |

**응답 형식은 v1 그대로다.**

```json
{
  "error_code": "OCR_ELEMENT_CONFLICT",
  "message": "다른 사용자가 먼저 수정했습니다. 새로 불러온 뒤 다시 시도해 주세요.",
  "request_id": "a1b2c3d4"
}
```

**`SYS-09` 를 첫날 고친다.** 미니 프로젝트에서 `business_error_handler` 에 로그
호출이 없어 `404` · `409` · `413` 이 서버 로그에 남지 않았다 (`ISS-046`).

---

## 6. Pydantic 스키마 초안 (8/12 확정)

```python
# schemas/common.py
class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int
    total_pages: int


# schemas/document.py
class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    file_type: str
    status: DocumentStatus
    processing_mode: ProcessingMode
    document_type: DocumentType | None = None          # None = 자동 판별 대기
    document_type_source: DocumentTypeSource | None = None
    created_at: datetime


class StepState(str, Enum):
    PENDING = "PENDING"; RUNNING = "RUNNING"; DONE = "DONE"
    FAILED = "FAILED";   NEEDS_REVIEW = "NEEDS_REVIEW"

class Step(BaseModel):
    key: str
    label: str
    state: StepState
    done: int | None = None        # 분석 단계에서만
    total: int | None = None
    meta: dict[str, Any] | None = None
    detail: list[dict[str, Any]] | None = None

class DocumentStatusResponse(BaseModel):
    id: int
    status: DocumentStatus
    review_status: ReviewStatus
    ocr_revision: int
    steps: list[Step]              # 길이 고정 4. 분석기 수는 done/total 로


# schemas/suggestion.py — 4종 공통 필드
class SuggestionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    confidence: float | None = None
    reason: str                    # 페이지·좌표 대신 판단 근거를 담는다
    decision: SuggestionDecision

class AmountItemOut(SuggestionBase):
    item_name: str
    quantity: Decimal | None = None
    unit: str | None = None
    amount: Decimal | None = None   # 문서에 없으면 None. AI 가 채우지 않는다
    currency: str = "KRW"

class AmountCheck(BaseModel):
    items_total: Decimal
    document_total: Decimal | None = None
    diff: Decimal | None = None
    note: str | None = None

class SuggestionsResponse(BaseModel):
    document_id: int
    source_text_revision: int
    is_stale: bool
    action_items: list[ActionItemOut] = []
    decisions: list[DecisionOut] = []
    schedule_items: list[ScheduleItemOut] = []
    amount_items: list[AmountItemOut] = []
    amount_check: AmountCheck | None = None

class SuggestionPatchRequest(BaseModel):
    decision: Literal["APPROVED", "EDITED", "REJECTED"]
    patch: dict[str, Any] | None = None


# schemas/deliverable.py
class DeliverableCreateRequest(BaseModel):
    kind: DeliverableKind
    format: DeliverableFormat           # 기본값 없음 — 반드시 지정
    period_from: date | None = None
    period_to: date | None = None

    @model_validator(mode="after")
    def check_period(self):
        if self.kind == DeliverableKind.WEEKLY_REPORT and not (
                self.period_from and self.period_to):
            raise ValueError("주간 보고서는 기간이 필요합니다")
        return self
```

**`Decimal` 을 쓴다.** 금액에 `float` 를 쓰면 반올림 오차가 생기고,
`AMT-06` 의 "같은 입력이면 항상 같은 결과" 가 깨진다.

---

## 7. 이 문서를 쓰면서 발견한 것 — 제안 4종의 비대칭

**`#35 GET /suggestions` 를 설계하다 걸렸다.**

| 제안 종류 | 어디에 저장되나 |
|---|---|
| 결정사항 | `decisions` 테이블 |
| 일정 | `schedule_items` 테이블 |
| 금액 항목 | `amount_items` 테이블 |
| **액션아이템** | **`analyses.result_json` 안의 배열** |

**액션아이템만 테이블이 없다.** 착수기획서가 `tasks.source_analysis_id` 로 설계했기
때문인데, 이러면 세 가지가 걸린다.

| 문제 | |
|---|---|
| 승인·거부 상태 관리 | JSONB 배열 원소를 부분 수정해야 한다 |
| 채택률 계산 | 다른 셋은 쿼리 하나인데 액션아이템만 JSONB 순회 |
| API 비대칭 | `PATCH /suggestions/action_item/{id}` 의 `id` 가 무엇인지 애매하다 |

### 제안 — `action_items` 테이블을 추가한다

`decisions` · `schedule_items` 와 같은 모양이면 **네 종류가 대칭이 되고 API 가
하나로 통일된다.**

그러면 `tasks` 의 출처도 정리된다.

```
source_analysis_id      →  source_action_item_id   로 교체
source_amount_item_id       그대로
```

**여전히 2갈래이고 `CHECK` 제약도 그대로다.** `analyses` 를 직접 가리키는 것보다
**어느 항목에서 나왔는지가 명확**해진다.

**테이블 18개 → 19개가 된다.** 착수 전이라 지금 정하면 마이그레이션 비용이 없다.

---

## 8. 합의 체크리스트 (8/12 까지)

### 구조

- [ ] `#15` 업로드를 **`202`** 로 바꾸는 것에 동의 (`DOC-06` 전제)
- [ ] `#18` `steps` 를 **서버가 만들어 내려주고 길이는 4로 고정**
- [ ] `#3` 분석기 4개를 **유형 구분 없이 항상 다 돌린다**
- [ ] `#35`·`#36` **제안 4종 통합 API** 형태
- [ ] **`action_items` 테이블 추가** (7절) — 테이블 19개
- [ ] v1 `/api/documents` 하위 호환을 **버린다**
- [ ] `/api/ocr-compare` 는 **관리자 전용으로 격리**해 남긴다

### 필드

- [ ] snake_case 유지
- [ ] `document_type` 7종 값 확정 (`CONTRACT` `CONTRACT_CHANGE` `MEETING_NOTES` `REPORT` `NOTICE` `MANUAL` `ETC`)
- [ ] `analyzer_type` 4종 확정 (`summary` `category` `extract` `amount`)
- [ ] `deliverable_kind` 4종 · `deliverable_format` 3종 확정
- [ ] 금액은 **`Decimal`**, 화면 표시는 문자열로 내릴지 결정
- [ ] 날짜·시각에 **타임존 포함** (`+09:00`) 여부 확정
- [ ] 파일 크기 상한 **20MB** 확정

### DB (세현님)

- [ ] `tasks.completed_at` · `updated_at` 추가 **(없으면 `#43` 불가)**
- [ ] `tasks.source_action_item_id` · `source_amount_item_id` + `CHECK`
- [ ] `documents.document_type` 7종 enum 실제 사용
- [ ] `documents.document_type_source` (선택)
- [ ] `activity_logs.action_type` 값 목록 합의

### 미결

- [ ] `VIEWER` 에게 금액 노출 여부 → `#35`·`#50` 응답에 영향 (`AMT-11`)
- [ ] 산출물 파일 저장 위치 → `DOC-14` S3 · MinIO 와 같은 곳
- [ ] 폴링 주기 2초 · SSE 전환 시점

### 착수 준비

- [ ] Pydantic 스키마를 이 문서 기준으로 작성 (8/12)
- [ ] `USE_FAKE_AI` 로 **분석기 4개의 페이크 응답** 준비 → 세 명 병렬 착수
- [ ] 프론트 타입 정의를 `/docs` 기준으로 생성
