# Tasqra 리비전 0014 전달 — document_chunks.project_id

```
작성      2026-08-14  김보현
대상 레포  ParkSehyeon1009/Tasqra  (팀 레포 · 에이전트는 직접 커밋하지 않는다)
기준 커밋  c3246e6  Merge pull request #19 from ParkSehyeon1009/document-upload-strategy
상태      커밋 대기
```

## 무엇

`document_chunks` 에 `project_id` 를 추가한다. **컬럼 하나 + 인덱스 하나.**

| 파일 | 상태 |
|---|---|
| `backend/migrations/versions/20260814_0014_document_chunk_project.py` | 신규 |
| `backend/app/models/chunk.py` | 수정 (+13줄) |

## 왜 — `iterative_scan` 이 작동하려면 같은 테이블의 조건이어야 한다

`SRH-001` 완료 판정이 *"다른 프로젝트 문서는 제외된다"* 이고
`RAG-001-2` 가 *"프로젝트 범위 인덱스가 유지된다"* 다.

`project_id` 가 없으면 이렇게 된다.

```sql
SELECT c.* FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.project_id = 5              -- 다른 테이블의 조건
ORDER BY c.embedding <=> $1 LIMIT 10;
```

**pgvector 의 HNSW 는 거리 순으로 후보를 `ef_search` 개(기본 40)만 꺼내고 그
다음에 조건을 검사한다.** 프로젝트가 전체 청크의 5% 면 40개 중 2개만 살아남아
결과가 부족해진다. **에러가 아니라 "결과가 적게 나오는" 방식으로 실패**하므로
발견이 늦다.

`pgvector 0.8.6` 이 설치돼 있어 `hnsw.iterative_scan` 을 쓸 수 있다(0.8.0+).
조건을 통과하는 행이 충분해질 때까지 인덱스를 계속 훑어준다.

**그런데 그것은 "스캔 중인 테이블에서 평가할 수 있는 조건" 에만 적용된다.**
조인 조건은 해당되지 않는다. 그래서 `project_id` 를 같은 테이블에 둔다.

```sql
SET LOCAL hnsw.iterative_scan = strict_order;
SELECT * FROM document_chunks
WHERE project_id = :project_id       -- 같은 테이블의 조건
ORDER BY embedding <=> :query LIMIT :k;
```

**즉 `project_id` 는 `iterative_scan` 의 전제다.** 택일이 아니다.

> **미확인** — 이 계획 차이는 실제 데이터로 `EXPLAIN ANALYZE` 를 찍어야 확정된다.
> 지금 청크가 0행이라 확인하지 못했다. 다만 컬럼을 두는 쪽이 어느 해석에서도
> 손해가 없다.

## 역정규화 위험

`project_id` 가 `documents` 와 중복된다. **문서를 다른 프로젝트로 옮기는 기능이
기능명세서에 없어서** 사실상 불변값이고 위험이 낮다.

**만약 이동 기능이 생기면** `documents.project_id` 를 바꿀 때
`document_chunks.project_id` 도 같이 갱신해야 한다. 모델 주석에 남겨 뒀다.

## 컬럼 추가를 3단계로 하는 이유

`NOT NULL` 을 한 번에 걸면 **기존 행이 있는 개발자의 DB 에서 실패한다.**

```
1. nullable 로 추가
2. documents 에서 UPDATE 로 채운다
3. SET NOT NULL + FK + 인덱스
```

지금은 `down -v` 로 비워서 0행이지만, 다른 팀원이 데이터를 갖고 있으면 필요하다.

## 인덱스를 하나만 추가하는 이유

```
ix_chunk_project (project_id, document_id)
```

프로젝트가 아주 작을 때는 HNSW 를 훑는 것보다 **그 프로젝트의 청크만 읽어
정확한 거리를 계산하는 편이 빠르다.** 계획 선택지를 준다.

`0011` 에서 `ix_chunk_doc (document_id, seq)` 를 `uq_document_chunk_seq` 와
완전 중복이라 뺀 전례가 있다. **불필요한 인덱스는 쓰기 비용만 늘린다.**
기존 인덱스 중 `project_id` 로 시작하는 것이 없으므로 이것은 중복이 아니다.

## FK 이름

```
document_chunks_project_id_fkey
```

이 레포는 FK 를 전부 인라인 `sa.ForeignKey(...)` 로 선언해서 PostgreSQL 기본
규칙(`{테이블}_{컬럼}_fkey`)으로 이름이 붙어 있다. `\d` 출력이 고르도록 같은
규칙을 따랐다.

## 적용

> **먼저 확인** — `document-async-processing` 이 main 에 머지됐는지 본다.
> 안 됐으면 패치 적용·커밋까지는 해도 되지만 **`alembic upgrade head` 는
> 머지 뒤에 돌린다.** 아래 "리비전 번호" 절 참고.
>
> ```powershell
> git log --oneline origin/main -3
> git ls-tree --name-only origin/main backend/migrations/versions/ | Select-Object -Last 3
> ```
> `20260814_0013_document_processing_error.py` 가 보이면 머지된 것이다.

```powershell
cd C:\dev\Tesqra\Tasqra
git checkout main
git pull
git checkout -b feat/chunk-project-scope

git apply --check "C:\dev\deliver\참고\Tasqra_0014_전달\0014-chunk-project-id.patch"
git apply "C:\dev\deliver\참고\Tasqra_0014_전달\0014-chunk-project-id.patch"
git status
```

기대 결과 — 수정 1 · 신규 1

```
 M backend/app/models/chunk.py
?? backend/migrations/versions/20260814_0014_document_chunk_project.py
```

**`c3246e6` 기준으로 깨끗하게 적용되는 것을 별도 클론에서 확인했다.**

## 커밋

```powershell
git add backend/app/models/chunk.py backend/migrations/versions/20260814_0014_document_chunk_project.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat: document_chunks 에 project_id 추가 (리비전 0014) - 프로젝트 범위 벡터 검색"
git push -u origin feat/chunk-project-scope
```

`--stat` 은 **2개 파일 · 101 insertions** 여야 한다.

## 검증

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec db psql -U postgres -d tasqra -P pager=off -c "\d document_chunks"
docker compose exec db psql -U postgres -d tasqra -P pager=off -c "\di *chunk*"
```

| 확인 | 기대값 |
|---|---|
| `alembic current` | `20260814_0014 (head)` |
| `\d document_chunks` | 컬럼 **16개** (기존 15 + `project_id`) · CHECK 8개 |
| FK | `document_chunks_project_id_fkey` -> `projects(id)` ON DELETE CASCADE |
| `\di *chunk*` | 인덱스 **6개** (기존 5 + `ix_chunk_project`) |

**컨테이너 재생성이 필요 없다.** `docker-compose.yml` 을 건드리지 않았고
`alembic upgrade head` 만으로 올라간다. 팀 공지도 필요 없다.

## 리비전 번호 — 0013 이 아니라 0014 다

```
20260814_0011  document_chunks             보현 · 머지됨
20260814_0012  ocr_element_structure       재정 · 머지됨
20260814_0013  document_processing_error   재정 · document-async-processing 브랜치
20260814_0014  document_chunk_project      보현 · 이 전달분
```

> **세 번째 리비전 번호 충돌이었다. 커밋 직전에 잡았다.**
>
> 처음에 `0013` 으로 썼는데, `document-async-processing` 브랜치가 이미
> `20260814_0013_document_processing_error.py` 를 쓰고 있었다. `revision` 과
> `down_revision` 이 **완전히 동일**해서 둘 다 머지되면 alembic 이 같은
> 식별자를 두 개 보게 되고 `upgrade head` 가 실패한다.
>
> **`origin/main` 의 `versions/` 만 보는 것으로는 부족하다.** 그 브랜치는 아직
> main 에 머지되지 않아 main 만 확인했을 때는 `0013` 이 비어 있었다.
> **머지되지 않은 원격 브랜치까지 확인해야 한다.**
>
> ```bash
> git fetch --all
> for b in $(git branch -r | grep -v HEAD); do
>   echo "--- $b"; git ls-tree --name-only $b backend/migrations/versions/ | tail -3
> done
> ```

### down_revision 을 0012 가 아니라 0013 으로 둔 이유

`0012` 로 두면 `0012` 에서 `0013`(재정)과 `0014`(우리)로 **두 갈래로 분기**한다.
alembic 은 분기를 허용하지만 **head 가 둘이 되어 `upgrade head` 가 모호해지고
별도 merge revision 을 만들어야 한다.** 그래서 재정님 `0013` 뒤에 붙였다.

### 그래서 순서 의존이 생겼다

> **`document-async-processing` 이 main 에 머지된 뒤에 이 리비전을 올려야 한다.**
>
> 먼저 올리면 `down_revision = "20260814_0013"` 이 존재하지 않아
> `alembic upgrade head` 가 `KeyError` 로 실패한다.
>
> 재정님 쪽이 `SYS-002-2`(비동기 작업 큐, P0)라 먼저 머지될 가능성이 높다.
> 만약 우리가 먼저 올려야 하는 상황이 되면 `down_revision` 을 `0012` 로 돌리고
> 재정님 쪽 번호를 `0014` 로 미루도록 조율한다.

**두 파일을 함께 놓고 사슬을 검증했다** — 리비전 14개 · head 하나
(`20260814_0014`) · 중복 없음.

```
0011 -> 0012 -> 0013(재정) -> 0014(우리)
```
