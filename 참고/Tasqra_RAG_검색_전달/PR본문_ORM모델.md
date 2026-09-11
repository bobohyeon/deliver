# PR 본문 — 리비전 0007 테이블 ORM 모델 (복사해 붙이는 용도)

브랜치 `feat/suggestion-orm-models` → `main` · 커밋 1개.

**제목**

```
feat: 리비전 0007 테이블 ORM 모델 — decisions · schedule_items · deliverables
```

**아래 선 밑을 전부 복사해서 PR 본문에 붙인다.**

---

## 무엇

리비전 `0007` 이 만든 테이블 셋에 **ORM 매핑만** 더합니다.

| 모델 | 테이블 | 칼럼 |
|---|---|---|
| `Decision` | `decisions` | 17 |
| `ScheduleItem` | `schedule_items` | 16 |
| `Deliverable` | `deliverables` | 12 |

**DB 변경이 없습니다. 마이그레이션을 추가하지 않았습니다.** 테이블·인덱스·제약은
이미 `0007` 이 만들어 두었고, 이 PR 은 파이썬 클래스만 더합니다. Flyway 가 만든
테이블에 `@Entity` 를 붙이는 것과 같습니다(`ddl-auto=none`).

## 왜

**테이블은 있는데 ORM 모델이 없어서 코드가 이 테이블들을 다룰 수 없었습니다.**
`backend/app` 전체에서 `decisions` 를 읽거나 쓰는 코드가 0건이었습니다. 그래서
대시보드가 결정사항을 세지 못하고, 산출물도 만들 수 없었습니다.

이 PR 로 풀리는 P1 넷 —

| 기능 | 무엇이 필요했나 |
|---|---|
| 생성 대상 미리보기 `DLV-001-2` | 결정·기한 건수 |
| 결정사항 대장 `DLV-003-1` | `decisions` |
| 다음 회의 안건 `DLV-003-2` | `decisions` 의 `status='PENDING'` |
| 생성 이력·다운로드 `DLV-003-3` | `deliverables` |

**`완료 태스크` 는 여전히 못 셉니다** — `tasks` 테이블 자체가 없습니다
(`TSK-001-1` 미구현). 대시보드의 `open_tasks = null` 과 같은 이유입니다.

## 짚어 둔 것 셋

### ① `status` 와 `decision` 은 다른 것입니다 — 둘 다 `PENDING` 값을 가집니다

리비전 `0007` 주석이 명시한 구분입니다.

| 컬럼 | 뜻 | 값 |
|---|---|---|
| `status` | **결정 자체**의 상태 | `DECIDED` · `PENDING` · `REVERSED` |
| `decision` | **AI 제안**의 승인 여부 | `PENDING` · `APPROVED` · `EDITED` · `REJECTED` |

*"사람이 승인한 제안(`decision=APPROVED`)이지만 아직 결론이 안 난 안건
(`status=PENDING`)"* 이 성립합니다. 헷갈리지 않게 프로퍼티를 나눴습니다 —
`is_open`(안건 대상) · `is_pending_approval`(승인 대기).

**다음 회의 안건(`DLV-003-2`)이 모으는 것은 `status='PENDING'`** 입니다.
`0007` 주석: *"status='PENDING' 인 항목이 그대로 다음 회의 안건이 된다."*

### ② `schedule_items` 는 `kind` 마다 기한 컬럼이 다릅니다

| `kind` | 의미 있는 날짜 |
|---|---|
| `MILESTONE` · `MEETING` | `starts_on` (한 시점) |
| `DEADLINE` | `ends_on` |
| `PERIOD` | `starts_on` ~ `ends_on` |

DB 는 둘 다 nullable 입니다 — 문서에 없으면 NULL 이어야 하고 LLM 이 만들어 채우면
안 되기 때문입니다. 그래서 **`DEADLINE` 인데 `ends_on` 이 NULL 인 행이 있을 수
있습니다.** 화면·보고서가 매번 분기하지 않게 `due_on` 프로퍼티로 모았습니다.

### ③ `source_counts_json` 이 갱신 판정의 근거입니다

`deliverables` 는 AI 제안이 아니라 **우리가 만든 결과물**이라 승인 컬럼이 없습니다.
대신 **생성 시점의 재료 개수 스냅샷**을 들고 있습니다.

```
생성 시  {"documents": 12, "decisions": 5}
지금     {"documents": 15, "decisions": 6}
-> stale_against() -> {"documents": 3, "decisions": 1}   갱신 필요
```

**늘어난 것만 담습니다.** 줄어든 것으로 "갱신 필요" 를 띄우면 사용자가 이유를 알
수 없습니다. 파일을 다시 만들어 비교하지 않고 개수만 비교하는 것은 LLM 호출
비용 때문입니다(`DLV-003-4`).

## 검증

**테스트 219 → 237 passed** (새 테스트 18개).

가장 큰 위험은 *"칼럼 이름이 하나 틀렸다"* 나 *"CHECK 문구가 달라 Alembic 이 매번
제약을 다시 만든다"* 입니다. 둘 다 에러 없이 조용히 어긋나는 종류입니다. 그래서
**마이그레이션 파일을 읽어서 비교합니다.**

| 무엇 | 결과 |
|---|---|
| 칼럼 이름·개수 | **17/17 · 16/16 · 12/12** 일치 |
| 값 목록 6종 | `DECISION_STATUS`·`SCHEDULE_KIND`·`DELIVERABLE_KIND`·`DELIVERABLE_FORMAT`·`SUGGESTION_DECISION`(두 테이블) 이 `0007` 상수와 동일 |
| 인덱스 이름 9개 | `0007` 에 실재 |
| CHECK 이름 8개 | `0007` 에 실재 |
| 부분 인덱스 | `ix_decision_open` 의 `WHERE status='PENDING'` 확인 |
| 헬퍼 | `due_on`(kind 4종) · `stale_against`(증가만) · `is_open` vs `is_pending_approval` |

**기대값을 테스트에 손으로 적지 않았습니다.** 두 곳에 적으면 한쪽만 고쳐졌을 때
거짓으로 통과합니다. `migrations/versions/20260811_0007_analysis_artifacts.py` 를
유일한 근거로 삼습니다.

## 남은 것

- `models/amount.py` 가 같은 AI 제안 컬럼 여섯 개를 자체 정의로 갖고 있습니다.
  믹스인으로 모으면 **동작하는 코드를 함께 고쳐야 해서** 이번 범위에 넣지
  않았습니다. 값·제약이 갈리지 않는 근거는 `0007` 이 유일한 출처라는 점입니다.
- `Deliverable` 에는 `AmountItem`·`Decision` 같은 `relationship` 을 최소로만
  두었습니다. 산출물 생성 서비스를 만들 때 필요한 것을 그때 더하면 됩니다.
