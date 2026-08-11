# Tasqra 스키마·에러코드 전달 — 반영 완료

**이 폴더의 파일은 2026-08-11 에 Tasqra `main` 에 반영됐다.** 더 이상 전달할
것이 없고, 기록으로만 남긴다.

## 반영 결과

| 보낸 파일 | Tasqra 경로 | 커밋 |
|---|---|---|
| `20260811_0006_schema_expand.py` | `backend/migrations/versions/` | `cdd6b35` |
| `error_codes.py` | `backend/app/core/error_codes.py` | `6cfe638` |

두 브랜치로 나눠 올리고 `main` 에 머지했다 (`1493d21`).

| 확인 항목 | 결과 |
|---|---|
| `alembic current` | **`20260811_0006 (head)`** |
| `len(ErrorCode)` | **51** (기존 26 + 추가 25) |
| 마이그레이션 파일 | 6개, 체인 단일 |

## 만들어진 테이블 8개

```
document_pages          ocr_groups      ocr_elements    ocr_element_revisions
amount_items            decisions       schedule_items  deliverables
```

기존 테이블은 건드리지 않았다(`add_column` 0건). `20260811_0005` 로
`downgrade` 하면 정확히 이전 상태로 돌아간다.

## 리비전 번호를 세 번 옮긴 기록

같은 작업인데 번호를 세 번 바꿨다. 왜 그랬는지 남겨둔다.

| 시점 | 번호 | 옮긴 이유 |
|---|---|---|
| 처음 | `20260810_0003` | — |
| 1차 | `20260810_0004` | `0003` 이 `project_invitations` 에 쓰였다 (PR #2) |
| 2차 | `20260811_0006` | `0004`·`0005` 가 `refresh_tokens`·`invitation_canceled` 에 쓰였다 (PR #4) |

**교훈** — 리비전 번호를 파일명에 넣는 방식은 남이 먼저 머지하면 따라가야 한다.
다만 `down_revision` 이 명시적이라 체인이 어긋나면 즉시 드러난다. 실제로 이
과정에서 두 번 다 머지 전에 발견했다.

**git 은 이 충돌을 잡아주지 않는다.** 서로 다른 새 파일이라 깨끗하게 머지되고,
`alembic upgrade head` 를 돌릴 때 `Multiple head revisions are present` 로
터진다. 컨테이너 기동 명령이 그 명령이라 앱이 아예 뜨지 않는다. 그래서
**마이그레이션을 만들면 다른 브랜치의 `versions/` 를 먼저 확인해야 한다.**

## 겪은 함정 두 개

**하나 — `migrations` 폴더는 마운트가 아니다.**

```dockerfile
COPY ./migrations ./migrations     # 이미지에 굽는다
```

`docker-compose.yml` 은 `backend/app` 과 `backend/uploads` 만 마운트한다.
그래서 마이그레이션 파일을 넣고 재시작만 하면 **에러 없이 조용히 반영되지
않는다.** 빌드 로그의 `COPY ./migrations` 가 `CACHED` 로 나오는 것이 신호다.

```bash
docker compose up -d --build api    # --build 필수
```

`migrations` 도 마운트하면 이 함정이 없어진다. 팀 합의가 필요한 변경이라
지금은 넣지 않았다.

```yaml
    volumes:
      - ./backend/app:/app/app
      - ./backend/migrations:/app/migrations    # 넣으면 --build 불필요
      - ./backend/uploads:/app/uploads
```

**둘 — 지운 리비전이 DB 에 남으면 기동이 실패한다.**

파일을 지웠는데 `alembic_version` 에 그 리비전이 적혀 있으면 이렇게 된다.

```
FAILED: Can't locate revision identified by '20260810_0004'
```

번호를 옮길 때는 **파일만 바꾸는 게 아니라 DB 도 맞춰야 한다.** 그 리비전이
만든 테이블이 이미 있으므로 버전만 고쳐도 다음 적용이 실패한다. 개발 중이라면
초기화가 가장 확실하다.

```bash
docker compose down -v && docker compose up -d --build
```

## 넣지 않은 것

| | 이유 | 누가 |
|---|---|---|
| `batch_jobs` · `batch_items` | 일괄 업로드는 다른 담당. 설계도 그쪽 것이므로 본인 리비전으로 넣는 편이 낫다 | 최재정 |
| `tasks` · `activity_logs` | 같은 파일을 동시에 고치는 것을 피했다 | 박세현 |
| `action_items` | 제안 4종을 대칭으로 둘지 합의 대기 | 전원 |
| `documents.batch_item_id` | 안 쓰는 FK 컬럼을 가장 바쁜 테이블에 미리 붙이지 않는다 | — |

에러코드도 같은 기준으로 뺐다. **테이블이 없는데 에러코드만 있으면 그게
애매한 것이다.**

## 하지 않은 것 하나

`exceptions.py` 는 손대지 않았다. 미니 프로젝트에서 `business_error_handler`
에 로그가 없던 문제(ISS-046)를 고치려 했는데, PR #4 에서 이미
`logger.warning` 이 추가됐다.

## 파일 목록

| 파일 | 상태 |
|---|---|
| `20260811_0006_schema_expand.py` | 반영 완료 |
| `error_codes.py` | 반영 완료. 교체용 완성본(51종) |
| `에러코드_추가분.md` | 25종의 근거. 왜 그 코드를 뒀는지 |
