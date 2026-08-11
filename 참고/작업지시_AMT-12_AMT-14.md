# 작업 지시 — `AMT-12` 스키마 검증 · `AMT-14` 비용 산출 엔진

**Claude Code 에 아래 프롬프트를 그대로 붙여넣는다.**

| | |
|---|---|
| 대상 레포 | `ParkSehyeon1009/Tasqra` |
| 기준 | `main` (리비전 `0007`, 에러코드 52종) |
| 범위 | **DB 변경 없음.** 순수 파이썬 + 단위테스트만 |
| 이유 | 리비전 `0008` 은 다른 사람 작업이 없을 때 따로 올린다 |

---

## 프롬프트

````
Tasqra 프로젝트에서 금액 추출 결과의 검증(AMT-12)과 비용 산출 엔진(AMT-14)을
구현한다. 이번 작업에서 DB 스키마는 절대 건드리지 않는다. 마이그레이션 파일을
만들거나 고치지 않는다. SQLAlchemy 모델도 수정하지 않는다.
순수 파이썬 모듈과 단위테스트만 추가한다.

## 0. 준비

git checkout main
git pull origin main
git checkout -b feat/amount-schema-and-calc

작업 단위마다 커밋한다. 아래 5단계 각각을 별도 커밋으로 만든다.

## 1. 도메인 값 추가 — backend/app/models/enums.py

기존 Enum 은 하나도 수정하거나 삭제하지 않는다. 아래를 파일 끝에 추가한다.

class DocumentType(str, Enum):
    RFP = "RFP"                          # 제안요청서 · 입찰공고
    PROPOSAL = "PROPOSAL"                # 제안서 · 기술제안서
    COST_SHEET = "COST_SHEET"            # 산출내역서 · 견적서 · 원가계산서
    CONTRACT = "CONTRACT"                # 계약서 · 과업지시서 · 착수신고서
    CONTRACT_CHANGE = "CONTRACT_CHANGE"  # 변경계약서 · 과업변경합의서
    REPORT = "REPORT"                    # 착수 · 주간 · 월간 · 완료보고서 · 검사조서
    MEETING_NOTES = "MEETING_NOTES"      # 회의록
    BILLING = "BILLING"                  # 대가지급청구서 · 세금계산서
    ETC = "ETC"

class AmountCategory(str, Enum):
    DIRECT_LABOR = "DIRECT_LABOR"   # 직접인건비
    EXPENSE = "EXPENSE"             # 직접경비
    OVERHEAD = "OVERHEAD"           # 제경비
    TECH_FEE = "TECH_FEE"           # 기술료
    MATERIAL = "MATERIAL"           # 재료비 · 물품비
    SUBCONTRACT = "SUBCONTRACT"     # 외주비
    VAT = "VAT"                     # 부가가치세
    OTHER = "OTHER"

class SuggestionDecision(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"

AnalyzerType 에 두 값을 추가한다. 기존 SUMMARY / CATEGORY 는 그대로 둔다.
    EXTRACT = "extract"
    AMOUNT = "amount"

파일 상단 주석 중 다음 문장이 지금 사실과 다르다. 도메인을 공공 SI·용역으로
좁히면서 문서 유형을 9종으로 확정했고 CHECK 제약을 넣기로 했다. 그 문장만
현재 결정에 맞게 고친다. 다른 문장은 건드리지 않는다.
  "document_type(문서 종류: general 등)은 본프로젝트에서 값이 계속 늘어날 수
   있어 이 파일에 Enum으로 두지 않고 ... 자유 문자열 컬럼으로만 둔다"
→ 문서 유형은 9종으로 확정했으므로 Enum 으로 두고, DB 에는 여전히 String
   컬럼 + CHECK 제약으로 반영한다는 내용으로 바꾼다.

커밋: "feat: 문서 유형 9종·금액 원가구분·제안 결정 Enum 추가"

## 2. 금액 추출 응답 스키마 — backend/app/schemas/amount.py (신규)

AI 가 반환한 금액 추출 결과를 받는 Pydantic 모델이다. 여기서 검증에 실패하면
호출부가 ErrorCode.AI_INVALID_RESPONSE 로 BusinessError 를 던진다.

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from app.models.enums import AmountCategory, DocumentType

class AmountItemOut(BaseModel):
    item_name: str = Field(min_length=1, max_length=300)
    category: AmountCategory | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: int | None = Field(default=None, ge=0)
    amount: int = Field(ge=0)
    period_from: date | None = None
    period_to: date | None = None
    source_quote: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=1000)

class AmountExtractionOut(BaseModel):
    document_type: DocumentType
    currency: str = Field(default="KRW", pattern=r"^[A-Z]{3}$")
    stated_total: int | None = Field(default=None, ge=0)
    items: list[AmountItemOut]
    notes: str | None = None

검증 규칙을 validator 로 추가한다.
  - period_from 과 period_to 가 둘 다 있으면 from <= to 여야 한다.
    어기면 ValueError.
  - amount 는 int 다. 소수점이 들어오면 Pydantic 이 거른다.

amount 를 int 로 둔 이유를 주석으로 남긴다. 원 단위 정수라 소수가 필요 없고,
부동소수점을 쓰면 합계에 오차가 생긴다. quantity 만 Decimal 이다(1.5인월).

커밋: "feat: 금액 추출 응답 스키마 추가 (AMT-12)"

## 3. 입력 정규화 — backend/app/services/amount_normalizer.py (신규)

모델이 문자열로 준 숫자를 정수로 바꾸는 함수들이다. 스키마 검증 전에 돌린다.

def normalize_number(raw: str | int | float | None) -> int | None
  "9,500,000원" / "9500000" / " 9,500,000 " / 9500000 -> 9500000
  쉼표 · 공백 · 원 · KRW · 통화기호를 제거한다.
  빈 문자열 · None · "-" 는 None 을 반환한다.
  숫자로 바꿀 수 없으면 None 을 반환한다(예외를 던지지 않는다).
  음수는 None 으로 처리한다(금액에 음수를 허용하지 않는다).

def normalize_quantity(raw) -> Decimal | None
  "3" -> Decimal("3"), "1.5" -> Decimal("1.5"), "3인월" -> Decimal("3")
  단위 문자가 섞여 있으면 숫자 부분만 취한다.

def normalize_payload(raw: dict) -> dict
  items 배열의 각 항목에서 amount / unit_price 에 normalize_number 를,
  quantity 에 normalize_quantity 를 적용한다.
  stated_total 에도 normalize_number 를 적용한다.
  원본 dict 를 변경하지 않고 새 dict 를 반환한다.

커밋: "feat: 금액 값 정규화 함수 추가 (AMT-12)"

## 4. 비용 산출 엔진 — backend/app/services/amount_calculator.py (신규)

핵심 원칙을 파일 주석 맨 위에 적는다.
  이 모듈은 순수 함수만 담는다. DB · 네트워크 · AI 를 부르지 않는다.
  같은 입력에 항상 같은 결과를 낸다. 그래서 단위테스트로 100% 검증된다.
  LLM 은 문서에서 값을 뽑을 뿐이고 계산은 여기서만 한다.

from dataclasses import dataclass

@dataclass(frozen=True)
class TotalCheck:
    item_total: int          # 부가세를 제외한 항목 합계
    vat_total: int           # 부가세 항목 합계
    stated_total: int | None # 문서에 적힌 합계
    difference: int | None   # item_total - stated_total. stated_total 이 None 이면 None
    matches: bool            # 차이가 0 인가. stated_total 이 None 이면 False

def sum_items(items) -> int
  category 가 VAT 인 항목을 제외한 amount 의 합.
  부가세를 포함하면 이중으로 더해진다. 이게 합계가 틀리는 가장 흔한 원인이다.

def sum_vat(items) -> int
  category 가 VAT 인 항목의 amount 합.

def check_total(extraction) -> TotalCheck
  AMT-03 합계 대조. 항목 합계와 문서에 적힌 합계를 비교한다.
  stated_total 이 None 이면 matches=False, difference=None 로 둔다.
  "대조할 수 없음" 과 "불일치" 는 다른 상태다.

def verify_line(item) -> bool | None
  quantity 와 unit_price 가 둘 다 있을 때만 quantity * unit_price == amount
  인지 검사한다. 하나라도 없으면 None(검사 불가).
  Decimal 로 계산하고 결과를 정수로 반올림해 비교한다.
  중요 — 불일치하면 amount 를 고치지 않는다. 문서가 틀렸다는 사실을
  그대로 보고한다. 고치면 오류가 숨는다.

def aggregate_by_category(items) -> dict[str, int]
  원가 구분별 합계. VAT 도 별도 키로 포함한다.

def aggregate_project(extractions) -> dict
  AMT-06 프로젝트 금액 집계. 여러 문서의 결과를 합친다.
  통화가 섞여 있으면 ValueError 를 던진다(CURRENCY_MISMATCH 로 변환할 것).
  반환: {"currency", "item_total", "vat_total", "by_category", "document_count"}

모든 함수에 타입 힌트를 붙인다. 금액 계산에 float 를 쓰지 않는다.

커밋: "feat: 비용 산출 엔진 추가 (AMT-14)"

## 5. 단위테스트 — backend/tests/test_amount_calculator.py (신규)

기존 tests/ 의 방식을 따른다. pytest 만 쓴다.

반드시 넣을 케이스

  정규화
    "9,500,000원" -> 9500000
    "  9500000  " -> 9500000
    "" / None / "-" / "미정" -> None
    "3인월" -> Decimal("3")
    "1.5" -> Decimal("1.5")

  합계 대조 — 맞는 경우
    항목 28500000 + 43200000 + 25800000, VAT 9750000
    stated_total 97500000
    기대: item_total 97500000, vat_total 9750000, difference 0, matches True

  합계 대조 — 틀린 경우 (이 기능의 핵심)
    항목 10000000 + 5000000 = 15000000
    stated_total 14000000  (문서가 틀렸다)
    기대: difference 1000000, matches False
    엔진이 문서 값을 고치지 않는다는 것을 확인한다.

  합계 대조 — 대조 불가
    stated_total None
    기대: difference None, matches False
    "대조 불가" 와 "불일치" 가 구분되는지 확인한다.

  부가세 이중 계산 방지
    VAT 항목을 하나 넣고 sum_items 에 포함되지 않는 것을 확인한다.

  행 검산
    quantity 3, unit_price 9500000, amount 28500000 -> True
    quantity 3, unit_price 9500000, amount 28000000 -> False (문서 오류)
    quantity None -> None (검사 불가)

  프로젝트 집계
    같은 통화 문서 2건을 합쳐 총액이 맞는지
    통화가 다르면 ValueError

  결정성
    같은 입력으로 두 번 호출해 결과가 같은지 (AMT-06 완료 판정 기준)

실행해서 전부 통과하는 것을 확인한다.
  docker compose exec -T api python -m pytest tests/test_amount_calculator.py -v

커밋: "test: 금액 정규화·산출 엔진 단위테스트 추가"

## 6. 마무리

git push -u origin feat/amount-schema-and-calc

전체 테스트가 깨지지 않았는지도 확인한다.
  docker compose exec -T api python -m pytest -q

## 지켜야 할 규칙

파일 상단에 3단 주석을 넣는다. 기존 파일들과 같은 형식이다.
  (1) 이 파일의 책임
  (2) 다른 파일과의 관계
  (3) Spring 비교

절대 하지 말 것
  - backend/migrations/ 아래 파일을 만들거나 고치지 않는다
  - app/models/document.py 등 SQLAlchemy 모델을 고치지 않는다
  - 기존 Enum 멤버를 지우거나 이름을 바꾸지 않는다
  - error_codes.py 를 고치지 않는다 (필요한 코드가 이미 다 있다)
  - 금액 계산에 float 를 쓰지 않는다
  - 문서에 적힌 금액이 틀려 보여도 코드가 고치지 않는다
````

---

## 오후 7시 이후에 할 일 (리비전 `0008`)

위 작업이 끝나면 DB 반영만 남는다. **별도 브랜치로 한다.**

| 변경 | 내용 |
|---|---|
| `amount_items.unit_price` | `BigInteger` nullable |
| `amount_items.category` | `String(20)` nullable + CHECK 8종 |
| `documents.document_type` | CHECK 제약 9종 (**지금 제약이 아예 없다**) |

**`document_type` 은 기존 데이터가 있으면 CHECK 를 걸 때 실패한다.** 미니
프로젝트에서 `general` 같은 값이 들어가 있을 수 있으니, 리비전에서 먼저
기존 값을 `ETC` 로 정리한 뒤 제약을 건다.

---

## 왜 이 순서인가

| | |
|---|---|
| **아무도 안 기다린다** | 세현님 모델 결과가 없어도 스키마와 계산은 만들 수 있다 |
| **단위테스트로 증명된다** | 계산은 순수 함수라 DB 없이 100% 검증된다 |
| **`AMT-03` 의 뿌리다** | 합계 대조는 이 프로젝트에서 정확도를 수치로 증명할 수 있는 유일한 기능이다 |
| **리비전과 겹치지 않는다** | 마이그레이션을 안 건드리므로 다른 사람과 충돌하지 않는다 |
