# OCR 검수에 단락 경계 지정 + 일괄 저장 엔드포인트 제안

```
작성      2026-08-14  김보현
대상      최재정님 (OCR 검수 담당)
기준 커밋  ParkSehyeon1009/Tasqra  22ed45d (origin/main)
목적      청킹(RAG-01)이 쓸 입력을 검수 화면에서 만들 수 있게 한다
```

**확인 범위** — 프론트(`OcrReviewPage.jsx` · CSS 3개) · 라우터 · 스키마 · 서비스 ·
리포지토리 · 테스트 · 추출기 4종. `origin/main` 기준이고 미푸시 작업은 없다
(원격 브랜치 `main` · `feat/local-llm` · `feat/rag-document-chunks` 뿐).

## ID 와 작업명

| ID | 작업명 |
|---|---|
| `RAG-01` | 텍스트 정규화 · 청킹 (문서를 조각으로 자르기) |
| `RAG-02` | 임베딩 생성 · 저장 |
| `RAG-09` | 검수 확정 시 재임베딩 |
| `REV-07` | 검수 완료 처리 |
| `REV-12` | 단락 지정 · 병합 · 분리 |
| `REV-13` | 읽기 순서 변경 |
| `REV-14` | 표 행 · 열 수동 보정 |
| `REV-16` | 동시 수정 충돌 방지 |
| `REV-17` | 텍스트 재조립 |
| `REV-18` | 분석 결과 오래됨 표시 |

---

## 1. 왜 이 제안을 하는가

`RAG-01` 의 판정 기준이 이렇게 적혀 있다.

> `ocr_elements` 의 `element_type` 으로 단락을 묶고 토큰 수 기준으로 자른다.
> 표는 행 단위로 유지된다

**그런데 `element_type` 은 지금 항상 `"TEXT_LINE"` 이다.** 다른 값을 넣는 코드가
0건이다 (`models/document.py:123` 의 기본값, `0006` 마이그레이션의 `server_default`
외에 대입이 없다). 그래서 **판정 기준대로 구현할 수 없다.**

`ocr_groups` 는 리비전 `0007` 이 미뤄뒀고, 그때 근거가
*"`0006` 은 `element_type` 컬럼으로 같은 목적을 달성하고 있으므로"* 였는데
**실제로는 채워지지 않아 그 전제가 성립하지 않는다.**

---

## 2. 종류와 경계는 다른 문제다

| 개념 | 물음 | 표현 |
|---|---|---|
| **종류** | 이 박스가 **무엇인가** | `element_type` (분류) |
| **경계** | 어느 박스들이 **한 단락인가** | 분류로는 표현 못 한다 |

`element_type` 은 분류 컬럼이라 "이 3줄이 한 단락"을 담을 수 없다. 억지로 하려면
`B-PARA`/`I-PARA` 같은 편법이 필요하다. **두 개를 따로 둬야 한다.**

---

## 3. 제안 1 — `element_type` 을 5종으로 고정

**청킹 동작이 달라지는 것만** 둔다. 값을 늘리면 검수 부담만 커진다.

| 값 | 뜻 | 청킹에서 하는 일 | 자동 판정 |
|---|---|---|---|
| `TEXT_LINE` | 본문 줄 (기본값) | 목표 길이까지 이어 붙인다 | 기본값 |
| `HEADING` | 제목 · 조항 제목 | **앞에서 끊고** 다음 조각 앞머리에 붙인다 | 가능 — `제N조` `1.` `가.` `■` 패턴 |
| `TABLE_ROW` | 표의 한 행 | 표로 묶어 행 단위로 자른다 | 가능 — 이미 행 단위로 만들어진다 |
| `TABLE_HEADER` | 표의 머리행 | **조각마다 복제한다** | 가능 — `cell.row == 0` |
| `HEADER_FOOTER` | 머리글 · 바닥글 · 페이지번호 | **청킹에서 버린다** | 가능 — 여러 페이지 같은 `y` 에 같은 텍스트 |

`LIST_ITEM` · `CAPTION` 은 청킹 동작이 `TEXT_LINE` 과 같아서 지금 넣지 않는다.
이 레포는 `String` + `CHECK` 규칙이라 나중에 값을 늘려도 `ALTER TYPE` 이 필요 없다.

### `HEADER_FOOTER` 의 이득이 가장 크다 — 실측 21.1%

머리글·바닥글은 페이지마다 반복된다. **24페이지 문서면 같은 문구가 24번
벡터화되어 검색 노이즈가 된다.** 지금은 사람이 `is_excluded` 로 하나씩
빼야 한다.

**추측이 아니다. 상용 파서의 실측 분포로 확인했다.**

KoViDoRe v2 Cybersecurity 벤치마크(한국인터넷진흥원 보고서 17건 · 1,150페이지)의
`elements` 컬럼은 상용 문서 파서가 뽑은 분류를 담고 있다. 표본 분포는 이렇다.

| 분류 | 개수 | 비율 | 우리 `element_type` 대응 |
|---|---|---|---|
| `paragraph` | 1,723 | 52.7% | `TEXT_LINE` |
| **`footer`** | **424** | **13.0%** | **`HEADER_FOOTER`** |
| `heading1` | 349 | 10.7% | `HEADING` |
| **`header`** | **265** | **8.1%** | **`HEADER_FOOTER`** |
| `figure` | 194 | 5.9% | (없음 — 텍스트로 불가) |
| `list` | 107 | 3.3% | `TEXT_LINE` 로 처리 |
| `table` | 92 | 2.8% | `TABLE_ROW` · `TABLE_HEADER` |
| `chart` | 58 | 1.8% | (없음 — 텍스트로 불가) |
| `caption` | 35 | 1.1% | `TEXT_LINE` 로 처리 |
| `footnote` | 22 | 0.7% | `TEXT_LINE` 로 처리 |
| `index` | 3 | 0.1% | `TEXT_LINE` 로 처리 |

> **`header` + `footer` = 689 개 = 전체의 21.1%.**
> **다섯 개 중 하나가 반복 상용구다.** 이것을 빼지 않으면 임베딩과 검색 결과가
> 그만큼 오염된다.

### 이 분포가 알려주는 것 세 개 더

| | 발견 | 우리 설계에 주는 뜻 |
|---|---|---|
| 1 | **파서의 단위가 `paragraph` 다** (줄이 아니다) | 우리 `ocr_elements` 는 **줄 단위**다. 남들은 파싱 단계에서 이미 문단으로 묶는데 우리는 줄만 갖고 있다. **`REV-12` 단락 지정이 필요한 이유가 이것이다** |
| 2 | `heading1` 로 **번호가 붙어 있다** = 제목에 계층이 있다 | 우리는 `HEADING` 하나로 둔다. 청킹 동작이 "앞에서 끊는다" 하나뿐이라 지금은 계층이 불필요하다. 나중에 필요해지면 늘린다 |
| 3 | **`chart` 를 `figure` 와 분리해서 인식한다** (합 7.7%) | 이 7.7% 가 **텍스트 파이프라인이 원리적으로 못 다루는 구간**이다. 비전 모델 검토 시 규모 감이 된다 |

**우리가 5종에서 뺀 것들(`list` · `caption` · `footnote` · `index`)은 다 합쳐
5.2% 다.** 빈도가 낮아 지금 넣지 않는 판단이 합리적이라는 것을 뒷받침한다.

출처 — `whybe-choi/kovidore-v2-cybersecurity-beir` (라이선스 `No Restriction`,
제공 한국인터넷진흥원). 표본은 각 parquet 샤드의 첫 row group 이다.

### 네 개가 자동으로 채워진다 — 사람은 고치기만 한다

`TABLE_HEADER` 는 특히 아깝다. `ocr_extractor._build_table_rows` 가
`rows.setdefault((cell.table_id, cell.row), ...)` 로 **표 번호와 행 번호를 이미
알고 있는데** `LayoutElement` 로 바꾸는 순간 버린다.

```
제안   LayoutElement 에 table_id · table_row 를 실어 보낸다
효과   머리행이 추측 없이 정해진다. REV-14(표 보정, P3) 의 기반도 된다
```

이 프로젝트에 이미 같은 패턴이 있다 — `document_type_source` 의
`USER` / `AI` / `USER_CORRECTED`. 사람이 고친 비율이 곧 정확도가 된다.

---

## 4. 제안 2 — 단락 경계는 `group_id` 가 아니라 **플래그**로

```
ocr_elements.is_paragraph_start   BOOLEAN NOT NULL DEFAULT false
```

단락의 **첫 줄에만** `true`. 단락은 "한 `true` 부터 다음 `true` 전까지"로 유도된다.

### `REV-12` 가 하려는 게 정확히 병합·분리다

| 동작 | 경계 플래그 | `group_id` |
|---|---|---|
| 단락 **분리** | 그 줄 하나 `true` — **1행 UPDATE** | 뒤따르는 **모든 그룹 번호를 재부여** |
| 단락 **병합** | 그 줄 하나 `false` — **1행 UPDATE** | 뒤 그룹 번호 전부 밀린다 |
| 새 테이블 | 필요 없음 | `ocr_groups` 신설 + `0006` 테이블 수정 |
| `REV-16` 충돌 | 1행이라 충돌 범위가 좁다 | 재부여 범위 전체가 충돌 대상 |

**`ocr_groups` 를 안 만들어도 `0007` 이 미뤄둔 숙제가 해결된다.**

> Spring 비교 — `group_id` 는 단락을 `@Entity` 로 만들고 `@ManyToOne` 을 거는
> 방식이고, 플래그는 순서가 보장된 목록에 **구분자만 표시**하는 방식이다.
> 단락 자체에 속성(제목·요약 등)을 달 계획이 없으면 엔티티로 승격할 이유가 없다.

### 지켜야 할 규칙 네 개

| | 규칙 | 이유 |
|---|---|---|
| 1 | **단락 경계는 페이지 안에서만 지정한다** | `content` 가 페이지를 `"\n\n"` 로 잇는다(`pdf_extractor.py:73`). 페이지 경계는 이미 단락 경계다. 화면도 한 페이지만 렌더링한다 |
| 2 | `TABLE_ROW` 사이에는 경계를 두지 않는다 | 표 전체가 한 덩어리다. 행 사이에서 끊으면 항목과 금액이 분리된다 |
| 3 | `HEADING` 은 **항상** 단락 시작이다 | 별도 지정이 필요 없다. 자동으로 `true` |
| 4 | **경계 변경도 `review_status` 를 `IN_PROGRESS` 로 되돌리고 `ocr_revision` 을 올린다** | 아래 설명 |

### 4번이 중요하다 — 우리 쪽 재임베딩 판정과 연결된다

**단락 경계를 바꾸면 본문 텍스트는 안 바뀌는데 청킹 결과는 바뀐다.**
`document_chunks.text_version` 은 `extracted_texts.text_version` 을 보고 낡음을
판정하므로, 텍스트가 그대로면 **경계만 바뀐 것을 감지하지 못한다.**

새 컬럼을 만들 필요는 없다. **텍스트 편집과 똑같이 처리하면 된다** —
`review_status` 가 `IN_PROGRESS` 로 돌아가고 재확정(`REV-07`)이 필요해지면,
그때 `RAG-09` 가 다시 돌아 청크가 새로 만들어진다. `update_ocr_element` 가
이미 그렇게 동작한다(`document_service.py:186-194`).

---

## 5. 제안 3 — 일괄 저장 엔드포인트

**성능 문제가 아니라 재임베딩 판정이 오염되는 문제다.**

### 지금 구조

```javascript
// OcrReviewPage.jsx  updateMutation
for (const change of changes) {
  await updateOcrElement(...)      // 한 건씩 PATCH. 실패하면 중단하고 부분 저장 반환
}
```

| 문제 | 근거 | 결과 |
|---|---|---|
| **`text_version` 폭증** | `document_service.py:182` — 편집 1건마다 `+1` | 10개 저장 = **+10**. 한 번의 논리적 저장이 stale 신호 10번 |
| **`ocr_revision` 폭증** | `document_service.py:185` | `REV-18` 오래됨 표시 전파도 같은 문제 |
| **O(N×M) 순회** | `_replace_ocr_content` 가 편집마다 `_ordered_ocr_elements` 전체를 돈다 | 24페이지 문서에서 낭비가 크다 |
| **부분 성공 잔존** | 프론트 `for` 루프가 실패 시 중단 | 일부만 저장된 상태가 남는다 |
| 요청 수 | 편집 N개 = PATCH N번 | 단락 경계를 일괄 지정하면 더 심하다 |

### 제안하는 형태

```
PATCH /api/projects/{p}/documents/{d}/ocr-elements
```

```json
{
  "items": [
    { "id": 12, "version": 3, "text": "고친 텍스트" },
    { "id": 15, "version": 1, "is_excluded": true },
    { "id": 18, "version": 2, "is_paragraph_start": true },
    { "id": 21, "version": 1, "element_type": "TABLE_HEADER" }
  ]
}
```

| 규약 | 내용 |
|---|---|
| 트랜잭션 | **하나.** 하나라도 실패하면 전체 롤백 (all-or-nothing) |
| 버전 | 항목마다 `version` 필수. 하나라도 어긋나면 **409** — 기존 두 엔드포인트와 동일 |
| `text_version` | **전체에서 1회만** 증가. 실제로 본문이 바뀐 경우에만 |
| `ocr_revision` | **1회만** 증가 |
| 권한 | `get_project_editor_access` — 기존과 동일. VIEWER 는 403 |
| 상한 | `items` 개수 상한을 둔다 (예: 500). `text` 는 기존과 같이 `max_length=10000` |
| 응답 | `OcrReviewResponse` 또는 갱신된 element 목록 |

**필드를 부분 갱신(sparse update)으로 받는 것을 권한다.** 넣지 않은 필드는
건드리지 않는다. 그래야 텍스트 저장·제외·단락 지정·종류 변경을 한 엔드포인트로
처리할 수 있고, 프론트가 화면 상태를 한 번에 보낼 수 있다.

기존 단건 엔드포인트 2개는 **그대로 두는 것을 권한다.** 이미 프론트가 쓰고 있고
제외 토글처럼 즉시 반영이 자연스러운 조작이 있다.

---

## 6. UI 제안 — 우측 텍스트 목록의 줄 사이

**좌측(원본 이미지)이 아니라 우측(텍스트 목록)을 권한다.**

| | 좌측에서 지정 | **우측에서 지정** |
|---|---|---|
| 조작 | 여러 박스를 감싸는 영역 드래그 | **줄 사이 구분선 클릭 한 번** |
| 구현 | 박스가 `position:absolute` 개별 `<button>` 이라 **선택 레이어를 새로 만들어야** 한다 | `elements.map()` 의 `<article>` 사이에 넣으면 된다 |
| 표 | 표 안에서는 사실상 불가능 | 표 행도 같은 목록에 있어 일관됨 |
| 우리 쪽 | 영역 → 박스 집합 → 경계로 **두 번 변환** | 클릭 지점이 **곧 `is_paragraph_start`** |

### 이미 있는 것을 쓴다

- 우측은 `ElementList` 가 `elements.map()` 으로 만든 세로 목록이고 번호도
  `{index + 1}.` 로 붙어 있다. **순서가 이미 화면에 드러난다**
- CSS `.ocr-element-list > article` 에 **`margin-bottom: 7px`** 여백이 이미 있다.
  구분선을 넣을 자리가 있다. 단 `overflow: hidden` 이라 **`<article>` 밖**에 둬야 한다
- 좌↔우 양방향 선택 연동이 이미 있다 (`selectElement` → `scrollIntoView`,
  선택 시 좌측 박스에 `selected` 클래스)

### 화면 동작 제안

```
줄 사이에 얇은 구분선 자리를 둔다
  마우스를 올리면  +  가 뜬다        누르면 단락이 나뉜다
  이미 경계가 있으면  ─  로 보인다    누르면 병합된다

단락 단위로 좌측 박스를 같은 색 테두리로 묶어 보여준다  (지정 결과를 원본에서 확인)
자동 채움을 먼저 보여주고 사람이 고친다               (빈 화면에서 다 그리는 건 부담)
```

자동 후보는 좌표에서 나온다 — **들여쓰기**(`x` 가 앞줄보다 큼)와
**줄 간격**(`y` 간격이 평소보다 넓음). 둘 다 `ocr_elements` 에 이미 있는 값이다.

### 저장 방식은 즉시 저장을 권한다

`is_excluded` 와 같은 방식이다. 구조 변경이라 텍스트 편집(`drafts` 누적)과
성격이 다르고, `useBlocker` 미저장 보호 대상에 넣지 않는 편이 단순하다.
다만 일괄 엔드포인트가 있으면 여러 경계를 모아 한 번에 보낼 수도 있다.

### 새 스타일은 `ocr-review-adjustments.css` 에 넣는다

`ocr-review.css` 는 **1줄로 압축된 파일**이라 손으로 고치기 어렵다.
`ocr-review-adjustments.css`(117줄)가 정상 포맷이고 나중에 로드된다.

---

## 7. 함께 바뀌는 범위 — DB 컬럼만이 아니다

**`OcrElementResponse` 에 `element_type` 이 아예 없다.** 지금 응답 필드는 이것뿐이다.

```
id · original_text · text · x · y · width · height
confidence · source · reading_order · version · is_excluded
```

`element_type` · `content_start` · `content_end` · `is_in_content` 는 DB 에 있지만
**노출하지 않는다.** 그래서 프론트가 종류를 알 방법이 없다.

| 계층 | 파일 | 바뀔 것 |
|---|---|---|
| 마이그레이션 | `versions/00NN_*.py` | `is_paragraph_start` · `table_id` · `table_row` 추가 · `element_type` CHECK |
| 모델 | `models/document.py` | `OcrElement` 필드 3개 |
| 추출기 | `ocr_extractor.py` · `layout.py` | `table_id` · `table_row` 를 버리지 않고 전달 · `element_type` 자동 판정 |
| 스키마 | `schemas/document.py` | `OcrElementResponse` 에 필드 노출 · 일괄 요청 스키마 |
| 라우터 | `document_router.py` | 일괄 엔드포인트 |
| 서비스 | `document_service.py` | 일괄 처리 (트랜잭션 1개 · `text_version` 1회) |
| 리포지토리 | `document_repository.py` | 일괄 조회·잠금 메서드 |
| 프론트 | `OcrReviewPage.jsx` · `api/document.js` | 구분선 UI · 일괄 저장 호출 |
| CSS | `ocr-review-adjustments.css` | 구분선 스타일 |
| 테스트 | `test_ocr_content_ranges.py` 등 | 오프셋 불변식이 깨지지 않는지 |

### 리비전 번호 주의

현재 head 는 `20260814_0011` (`document_chunks`) 이다.
`0012` 는 단가·원가구분 CHECK(`AMT-13`, 보현)로 예정돼 있다.
**`versions/` 를 먼저 확인하고 번호를 잡아야 한다** — `0010` 을 겹쳐 쓴 전례가 있다.

---

## 8. 물을 것

| | 물음 | 우리 쪽 입장 |
|---|---|---|
| 1 | **`REV-12` 단락 지정을 이번에 넣을 수 있는지** (지금 P2) | 넣어주시면 `RAG-01` 이 판정 기준대로 구현된다. 안 되면 조항 번호 패턴으로 버틴다 |
| 2 | **일괄 엔드포인트를 누가 만들지** | 우리가 만들어도 된다. 다만 `document_service` 를 건드리므로 충돌을 피하려면 조율이 필요하다 |
| 3 | **`table_id` · `table_row` 를 `LayoutElement` 에 실어줄 수 있는지** | 이미 계산되는 값이라 비용이 거의 없다 |
| 4 | `element_type` 자동 판정을 추출 시점에 넣을지, 별도 단계로 둘지 | 추출 시점이 단순하다 |
| 5 | **`REV-17` 비고의 "offset 기록은 불필요"가 지금도 유효한지** | `_replace_ocr_content` 가 `content_start`/`content_end` 에 **의존해서** 동작한다. 비고가 낡은 것으로 보인다 |

---

## 9. 확인하지 못한 것

| | 내용 |
|---|---|
| 1 | **들여쓰기·줄 간격으로 단락을 자동 판정하는 정확도.** 공고문에 넣어봐야 안다 |
| 2 | `HEADER_FOOTER` 자동 검출(여러 페이지 같은 `y` · 같은 텍스트)의 정확도 |
| 3 | **OCR 검수 텍스트로 임베딩 실측을 다시 돌렸을 때** 우리가 쓴 평균 305자 조건이 재현되는지. `RAG-10` 이 그 용도다 |
| 4 | `get_ocr_review` 가 `document.review_pages` → `page.elements` 를 지연 로딩한다. 페이지 수만큼 쿼리가 늘 수 있다 (기존 문제이고 이번 제안과 무관) |
