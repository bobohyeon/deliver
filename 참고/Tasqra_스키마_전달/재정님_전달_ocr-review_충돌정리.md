# `ocr-review` 브랜치 충돌 정리 — 전달용

## 요약

`ocr-review` 를 지금 상태로 머지하면 **main 에 이미 들어간 것 두 가지가 되돌아갑니다.**
브랜치를 따신 시점이 PR #5·#6 머지 이전이라 생긴 일로 보입니다.

| | 되돌아가는 것 | 결과 |
|---|---|---|
| 1 | `20260811_0006_schema_expand.py` 삭제 | **테이블 5개 소멸** |
| 2 | `error_codes.py` 51종 → 28종 | **에러코드 23종 소멸** |

사라지는 테이블은 이렇습니다.

```
ocr_groups   amount_items   decisions   schedule_items   deliverables
```

`amount_items` · `decisions` · `schedule_items` · `deliverables` 는 금액·산출물
기능의 기반입니다.

그리고 **리비전 번호가 `20260811_0006` 으로 겹칩니다.** main 에 같은 번호가
이미 있습니다.

---

## 왜 git 이 안 잡아줬나

**서로 다른 새 파일이라 git 은 충돌로 보지 않습니다.** 깨끗하게 머지되고,
`alembic upgrade head` 를 돌릴 때 드러납니다. 컨테이너 기동 명령이 그 명령이라
**앱이 아예 뜨지 않습니다.**

```
Multiple head revisions are present for given argument 'head'
```

이번에도 머지 전에 발견했습니다. 앞서 두 번도 같은 방식으로 잡았습니다
(`0003` → `0004` → `0006`).

---

## 제안 — 겹치는 3개는 재정님 정의를 씁니다

`document_pages` · `ocr_elements` · `ocr_element_revisions` 를 양쪽이 **다른
컬럼으로** 정의하고 있습니다.

| | 제 정의 | **재정님 정의 (채택)** |
|---|---|---|
| 좌표 | `x1 y1 x2 y2` (두 점) | `x y width height` (점 + 크기) |
| 타입 | `Numeric` | `Float` |
| `ocr_elements` 소속 | `document_id` + `page_id` + `group_id` | `page_id` |
| 단락 묶음 | `ocr_groups` 별도 테이블 | `element_type` 컬럼 |

**재정님 정의를 정본으로 하겠습니다.** 이유가 둘입니다.

- 원래 재정님 OCR-DB 설계안에서 온 것입니다
- **화면 구현까지 되어 있습니다.** 제 것은 문서만 있고 코드가 없습니다

둘 다 0~1 비율이라 정보량은 같고 상호 변환됩니다(`width = x2 - x1`). 어느 쪽이든
동작에 차이가 없으므로 **구현이 있는 쪽으로 맞추는 것이 맞습니다.**

---

## 정리한 파일 두 개

### 1. `20260811_0007_analysis_artifacts.py`

제 `0006` 에서 **겹치는 4개 테이블을 빼고** 남은 4개만 담았습니다.

| 담긴 테이블 | 용도 |
|---|---|
| `amount_items` | 금액 항목 (항목명·수량·단위·금액·통화·원문 인용) |
| `decisions` | 결정사항 |
| `schedule_items` | 일정 |
| `deliverables` | 산출물 (주간보고서·결정사항대장·회의안건) |

| | |
|---|---|
| 리비전 | `20260811_0007` ← `20260811_0006` |
| 기존 테이블 수정 | **없음** (`add_column` 0건) |
| OCR 테이블 참조 | **없음** |

**`0006` 이 만든 테이블을 하나도 참조하지 않습니다.** `analyses` · `documents` ·
`projects` · `users` 만 씁니다. 그래서 **OCR 검수 작업과 완전히 독립적으로
적용됩니다.**

검증한 내용입니다.

```
테이블 이름 충돌      0건
인덱스 이름 충돌      0건  (인덱스 12개)
제약 이름 충돌        0건
FK 대상 존재          전부 확인
downgrade 생성 역순   확인 (4개)
add_column            0건
```

`0006` 으로 `downgrade` 하면 정확히 이전 상태로 돌아갑니다.

### 2. `error_codes.py`

main 의 51종에 재정님 2종을 얹고 **중복 1종을 뺐습니다. 52종입니다.**

| | |
|---|---|
| 추가 | `INVALID_EXTRACTION_STRATEGY` · `OCR_EDIT_CONFLICT` (재정님 것) |
| 제거 | `OCR_ELEMENT_CONFLICT` (제 것) |

**`OCR_EDIT_CONFLICT` 와 `OCR_ELEMENT_CONFLICT` 가 같은 뜻입니다.** 둘 다 낙관적
락 충돌이고 409 입니다. **재정님 이름을 남겼습니다** — 구현이 그걸 쓰고 있으니까요.

기존 코드의 이름·메시지·상태코드가 한 글자도 바뀌지 않은 것을 대조로 확인했고,
Enum 을 실제로 생성해 멤버 52개와 이름=code 일치를 확인했습니다.

---

## 적용 순서

```
1. ocr-review 에서 main 을 rebase 또는 merge
2. 20260811_0006_schema_expand.py 삭제는 그대로 두기 (제 것을 빼는 게 맞습니다)
3. 재정님 0006 은 번호 그대로 20260811_0006 유지
4. error_codes.py 를 이 폴더의 파일로 교체 (52종)
5. ocr-review 머지
6. 제가 0007 을 별도 PR 로 올립니다
```

**4번이 중요합니다.** 지금 `ocr-review` 의 `error_codes.py` 는 26종 기준으로
작업된 것이라, 그대로 머지하면 제 25종이 지워집니다. 교체본을 쓰시면 됩니다.

6번을 따로 두는 이유는 **`0007` 이 `0006` 을 전제**하기 때문입니다. 순서가
뒤바뀌면 `down_revision` 이 없는 리비전이 됩니다.

---

## 확인 후 적용

```powershell
docker compose up -d --build api
docker compose exec -T api alembic current
```

`ocr-review` 머지 후에는 `20260811_0006`, `0007` 까지 올린 뒤에는
`20260811_0007` 이 나와야 합니다.

```powershell
docker compose exec -T api python -c "from app.core.error_codes import ErrorCode; print(len(ErrorCode))"
```

**52** 가 나와야 합니다.

`migrations` 폴더는 마운트가 아니라 Dockerfile 의 `COPY` 로 들어갑니다.
**`--build` 없이는 에러도 없이 조용히 반영되지 않습니다.** 빌드 로그의
`COPY ./migrations` 가 `CACHED` 로 나오면 반영이 안 된 것입니다.

---

## 협의할 것 세 개

### 1. `ocr_groups` — 단락 묶음 테이블

이번 `0007` 에서 **뺐습니다.** 남기려면 `ocr_elements` 에 `group_id` 가 필요해서
재정님 테이블을 고쳐야 하기 때문입니다.

`element_type` 컬럼으로 같은 목적을 달성하고 계시니 그대로 가도 됩니다. 다만
**RAG 청킹에서 단락 단위를 재사용하려면** 묶음을 조회할 수단이 있는 게 좋습니다.
`element_type` 만으로도 연속된 같은 유형을 묶을 수 있으니, 우선 그렇게 하고
부족하면 그때 테이블을 두는 것을 제안합니다.

### 2. `amount_items.unit_price` 추가

재정님이 정리해 주신 문서(4·5절)의 재계산 구조는 `수량 × 단가 = 금액` 을
전제합니다. 지금 `amount_items` 에는 **`unit_price` 가 없습니다.**

```
item_name  quantity  unit  amount  currency  period_from  period_to  source_quote
```

단가가 없으면 **"철근 1톤 × 900,000 → 950,000, 변경 +50,000"** 같은 재계산이
안 됩니다. 넣는 게 맞다고 보는데, 이번 리비전에는 **의도적으로 안 넣었습니다.**
충돌 정리와 새 설계를 한 리비전에 섞으면 검토가 어려워지기 때문입니다.

### 3. 문서 유형 7종 재검토

도메인을 **공공 SI · 용역**으로 좁히기로 했는데, 현재 7종에 그 도메인의 핵심
문서가 없습니다.

```
현재: CONTRACT · CONTRACT_CHANGE · MEETING_NOTES · REPORT · NOTICE · MANUAL · ETC
```

특히 **`산출내역서`** 가 없습니다. 금액 항목이 표로 정리된 문서라 금액 기능의
주 입력인데 지금은 `ETC` 로만 들어갑니다. `입찰공고` · `과업지시서` ·
`검사조서` 도 마찬가지입니다.

`String + CHECK` 방식이라 값 추가는 CHECK 제약만 바꾸면 됩니다. `ALTER TYPE` 이
필요 없습니다. 이 방식을 택한 이유가 이런 상황이었습니다.

---

## 앞으로 이 일을 줄이는 방법

세 번 연속 리비전 번호가 겹쳤습니다. 원인이 하나입니다.

> **마이그레이션을 만들 때 다른 브랜치의 `versions/` 를 보지 않는다.**

브랜치를 따기 전에 이 한 줄이면 확인됩니다.

```powershell
git fetch --all
git branch -r | ForEach-Object { git ls-tree -r --name-only $_.Trim() 2>$null | Select-String "migrations/versions" }
```

`migrations` 를 볼륨 마운트에 추가하는 것도 함께 제안합니다. `--build` 를
빠뜨려 생기는 혼란이 없어집니다.

```yaml
    volumes:
      - ./backend/app:/app/app
      - ./backend/migrations:/app/migrations    # 이 줄
      - ./backend/uploads:/app/uploads
```
