# PR 본문 — 산출물 생성 대상 미리보기 (복사해 붙이는 용도)

**⚠ 이 PR 은 ORM 모델 PR 이 먼저 머지돼야 합니다.** `Decision`·`ScheduleItem`
모델이 없으면 import 가 깨집니다.

**제목**

```
feat: 산출물 생성 대상 미리보기 DLV-001-2 - GET /api/projects/{id}/deliverables/preview
```

**아래 선 밑을 전부 복사해서 PR 본문에 붙입니다.**

---

## 무엇

산출물에 담길 내용이 몇 건인지 **AI 를 부르기 전에** 세어 돌려줍니다.

```
GET /api/projects/{project_id}/deliverables/preview?kind=WEEKLY_REPORT
    &period_from=2026-08-14&period_to=2026-08-20
```

```json
{
  "kind": "WEEKLY_REPORT",
  "period_from": "2026-08-14", "period_to": "2026-08-20",
  "counts": {
    "documents": 12, "decisions": 5, "schedule_items": 3, "amount_items": 2,
    "pending_suggestions": 4,
    "completed_tasks": null
  },
  "can_generate": true, "blocked_reason": null,
  "needs_period": true,
  "uncountable": ["completed_tasks"]
}
```

경로는 팀 API v2「예정」시트 19행에 정해져 있던 것을 그대로 씁니다.

## 왜

완료 판정이 *"**LLM 호출 전에** 건수가 보이고 대상이 없으면 생성이 방지된다"* 입니다.
빈 보고서를 만들고 나서야 비어 있음을 아는 것과, 만들기 전에 아는 것의 차이입니다.
LLM 호출은 되돌릴 수 없는 비용입니다.

## 이 PR 의 핵심 판단 — **종류마다 세는 대상이 다릅니다**

한 함수로 통일하려다 멈췄습니다. 통일하면 뜻이 틀립니다.

| `kind` | 기간 | 담기는 것 |
|---|---|---|
| `WEEKLY_REPORT` | **필수** | 기간 안의 문서·결정·일정·금액 |
| `DECISION_LOG` | 무시 | 결정 **전부** (확정·미결·뒤집힘) |
| `MEETING_AGENDA` | 무시 | **미결 결정만** (`status='PENDING'`) |
| `PROJECT_STATUS` | 무시 | 현재 상태 전부 |

- **결정사항 대장에 기간을 걸면** "지난주에 정한 것만" 이 되어 대장이 아니게 됩니다
- **회의 안건에 확정된 결정을 넣으면** 이미 끝난 것을 또 논의하게 됩니다.
  리비전 `0007` 주석이 근거입니다 — *"status='PENDING' 인 항목이 그대로 다음 회의
  안건이 된다."*
- **기간을 쓰지 않는 유형은 날짜가 와도 무시합니다.** 화면이 날짜를 남겨둔 채
  유형만 바꿔도 결과가 유형의 뜻대로 나오게 하려는 것입니다

`WEEKLY_REPORT` 만 기간이 필수인 것은 **DB CHECK(`ck_deliverable_period_required`)와
같은 판단**입니다. 두 곳이 갈리지 않게 `PERIOD_REQUIRED_KINDS` 한 곳에 뒀습니다.

## 짚어 둔 것 넷

### ① `completed_tasks: null` 은 "0건" 이 아니라 "아직 셀 수 없다" 입니다

`tasks` 테이블이 없습니다(`TSK-001-1` 미구현). 마이그레이션 어디에도
`create_table("tasks")` 가 없습니다.

**0 으로 두면 사용자가 "이번 주에 완료한 일이 없다" 로 잘못 읽습니다.** 그래서
`null` 로 두고 `uncountable: ["completed_tasks"]` 로 이유를 함께 보냅니다. 대시보드의
`open_tasks = null` 과 같은 규칙입니다.

> `decisions`·`schedule_items` 와 혼동하지 않도록 리포지토리 머리말에 적어 뒀습니다.
> 그 둘은 리비전 `0007` 로 있고 이름도 "결정사항"·"일정" 이라 태스크가 아닙니다.

### ② 승인 대기는 세지만 생성 가능 판정에 **더하지 않습니다**

`countable_total` 에서 `pending_suggestions` 를 제외합니다. **승인 대기만 있고
확정된 내용이 없으면 보고서는 비어 있습니다.**

대신 막을 때 그것을 알려줍니다 — 사용자가 다음에 할 일을 알게 됩니다.

```
"담을 내용이 없습니다. 승인 대기 중인 제안이 4건 있습니다 — 승인하면 담깁니다."
```

`blocked_reason` 을 서버가 문장으로 만드는 것은, 화면이 건수를 보고 스스로 판단하면
**같은 규칙이 두 곳에 생기기** 때문입니다.

### ③ `amount_items` 는 문서를 거쳐야 셉니다

`amount_items` 에 `project_id` 가 없습니다(리비전 `0007`). 금액은 항상 문서에서
나오기 때문입니다. `document_chunks` 는 `0014` 로 역정규화했지만 그건 HNSW 인덱스
때문이었고, 여기는 그런 이유가 없어 `JOIN` 합니다.

기간은 **문서의 업로드 시각**으로 봅니다. 금액 항목의 `period_from`·`period_to` 는
"그 금액이 적용되는 기간" 이라 보고서의 "이번 주 변동" 과 다른 뜻입니다.

### ④ 일정은 `kind` 마다 기한 컬럼이 달라 두 컬럼을 함께 봅니다

`MILESTONE`·`MEETING` 은 `starts_on`, `DEADLINE`·`PERIOD` 는 `ends_on` 이 기한입니다.
SQL 에서는 `due_on` 프로퍼티를 쓸 수 없으므로 **두 컬럼 중 하나라도 걸리면** 셉니다.
`PERIOD` 는 구간이라 기간과 겹치기만 해도 걸립니다 — "이 주에 진행 중인 기간" 이
보고서에 들어가야 하므로 그것이 맞습니다.

결정사항의 기간은 `decided_on` 으로 봅니다. **그 값이 NULL 인 행은 기간을 주면
빠집니다 — 일부러 그렇게 뒀습니다.** 날짜를 모르는 결정을 "이번 주 결정" 으로 넣으면
보고서가 틀립니다.

## 검증

**테스트 18개 추가.** DB 없이 리포지토리를 `MagicMock` 으로 대체합니다.

| 무엇 | 개수 |
|---|---|
| 종류마다 세는 대상이 다른가 | 4 |
| 대상이 없으면 막히는가 (완료 판정) | 4 |
| 주간 보고서만 기간을 요구하는가 | 5 |
| 셀 수 없는 것을 0 으로 만들지 않는가 | 2 |
| 승인 대기가 판정에 섞이지 않는가 | 3 |

샌드박스에 `pydantic`·`sqlalchemy` 가 없어 서비스를 실행하지는 못했습니다. 대신
**판단 로직을 AST 로 떼어내 11개 항목을 검증**하고, 리포지토리가 쓰는 컬럼 이름
11개가 모델에 실재하는지, 오류 코드 3개가 `error_codes.py` 에 실재하는지 확인했습니다.
**컬럼 이름이 하나 틀리면 에러 없이 조용히 어긋나는 종류**라 이것을 따로 봤습니다.

DI 정의 순서도 검사했습니다 — `Depends(...)` 는 기본값이라 함수를 정의하는 순간
평가되므로 `get_deliverable_repository` 가 `get_deliverable_service` 보다 위에
있어야 합니다. 위에 두면 import 시점에 `NameError` 로 앱이 뜨지 않습니다.

## 이 PR 에 없는 것

**만들기(`POST`)가 없습니다.** 완료 판정이 "LLM 호출 전에 건수가 보인다" 이므로
미리보기가 먼저 있어야 만들기가 그것을 전제로 설계됩니다. 만들기는 `DLV-002-1`
이고 별도 작업입니다.

프런트엔드 화면도 없습니다. 시안은 `deliver` 레포에 있습니다.
