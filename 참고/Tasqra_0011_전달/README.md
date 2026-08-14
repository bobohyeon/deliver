# Tasqra 리비전 0011 전달 — 벡터 DB(document_chunks) · 커밋 대기

```
작성      2026-08-14
대상 레포  ParkSehyeon1009/Tasqra  (팀 레포 · 에이전트는 직접 커밋하지 않는다)
기준 커밋  9d9d72c  Merge pull request #14 from ParkSehyeon1009/dashboard-improvement
상태      커밋 대기. 사용자가 직접 올린다
```

**이 폴더가 있는 이유** — 8월 13일에 쓴 같은 작업이 **전량 소실됐다.** 브랜치가
로컬 전용이었고 그 로컬이 에이전트 샌드박스였다. 세션이 끝나면서 함께 사라졌다.
팀 레포는 에이전트가 푸시할 수 없으므로 **개인 레포에 사본을 남겨 소실을 막는다.**

## ID 와 작업명

| ID | 작업명 |
|---|---|
| `RAG-01` | 문서를 조각으로 자르기 (청킹) |
| `RAG-02` | 임베딩 생성·저장 |
| `REV-17` | OCR 수정 후 텍스트 재조립 |

## 파일

| 이 폴더 | Tasqra 경로 | 신규/수정 |
|---|---|---|
| `0011-document-chunks.patch` | (전체 변경) | **이것 하나만 적용하면 된다** |
| `20260814_0011_document_chunks.py` | `backend/migrations/versions/` | 신규 |
| `chunk.py` | `backend/app/models/chunk.py` | 신규 |

패치에 들어 있는 수정 4개 — `backend/app/models/__init__.py`(엔티티 등록) ·
`backend/app/models/document.py`(`Document.chunks` 관계) ·
`backend/requirements.txt`(`pgvector==0.4.1`) ·
`docker-compose.yml`(**팀 공유 파일** · DB 이미지 교체).

## 적용 방법 — 패치 하나로

```powershell
cd C:\dev\Tasqra
git checkout main
git pull
git checkout -b feat/rag-document-chunks

git apply --check ..\deliver\참고\Tasqra_0011_전달\0011-document-chunks.patch
git apply ..\deliver\참고\Tasqra_0011_전달\0011-document-chunks.patch
git status
```

`--check` 가 조용히 통과하면 그대로 적용된다.
**`9d9d72c` 기준으로 깨끗하게 적용되는 것을 확인했다** (별도 클론에 실제로 적용해 봤다).

패치가 안 맞으면 신규 2개는 그냥 복사하고 수정 4개는 손으로 넣는다.

## 커밋

```powershell
git add backend/migrations/versions/20260814_0011_document_chunks.py backend/app/models/chunk.py backend/app/models/__init__.py backend/app/models/document.py backend/requirements.txt
git commit -m "feat: document_chunks 테이블 추가 (리비전 0011) - RAG 벡터 검색용"

git add docker-compose.yml
git commit -m "chore: DB 이미지를 pgvector/pgvector:pg16 으로 교체

pgvector 확장이 필요하다. postgres:16-alpine 에서는
CREATE EXTENSION vector 가 실패한다.
alpine -> debian 계열이라 기존 볼륨은 붙지 않는다."

git push -u origin feat/rag-document-chunks
```

**`docker-compose.yml` 을 커밋 분리한 이유** — 팀 공유 파일이라 다른 팀원의
컨테이너에 영향이 간다. 되돌릴 때 이 커밋만 revert 하면 된다.

## 검증 — 이 단계가 유일한 미검증 지점이다

**에이전트 샌드박스에 Docker 가 없고 네트워크가 막혀 `pip install` 도 안 된다.**
그래서 **문법(`py_compile`)과 리비전 사슬까지만 확인했다.** 아래는 로컬에서 해야 한다.

```powershell
docker compose down -v
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec db psql -U postgres -d tasqra -c "\d document_chunks"
docker compose exec db psql -U postgres -d tasqra -c "\di document_chunks*"
```

**`down -v` 로 개발 데이터가 지워진다.** DB 이미지가 alpine -> debian 이라
기존 볼륨이 붙지 않으므로 `-v` 가 필요하다. **팀에 공지 완료 상태다.**

기대 결과

| 확인 | 기대값 |
|---|---|
| `alembic current` | `20260814_0011 (head)` |
| `\d document_chunks` | 컬럼 15개 · CHECK 8개 |
| `\di document_chunks*` | 인덱스 4개 (PK · `uq_document_chunk_seq` · `ix_chunk_stale` · `ix_chunk_model` · `ix_chunk_vec`) |
| `ix_chunk_vec` | `hnsw` · `vector_cosine_ops` |

**HNSW 인덱스 생성이 가장 먼저 깨질 수 있는 지점이다.** pgvector 0.5.0 이상이
필요하다. 실패하면 `ivfflat` 으로 낮추거나 이미지 태그를 올린다.

## 스키마

```
document_chunks
  id               BigInteger    PK
  document_id      BigInteger    FK documents.id CASCADE
  seq              Integer       NOT NULL
  page_number      Integer       nullable        출처 표시용
  text             Text          NOT NULL        인용 원문
  char_count       Integer       NOT NULL
  token_count      Integer       NOT NULL
  content_start    Integer       nullable        본문 내 시작 위치
  content_end      Integer       nullable        본문 내 끝 위치
  embedding        Vector(1024)  NOT NULL
  embedding_model  String(100)   NOT NULL        모델 교체용
  embedding_dim    SmallInteger  NOT NULL        CHECK = 1024
  text_version     Integer       NOT NULL        낡음(stale) 판정
  created_at / updated_at
```

`Vector(1024)` 는 채택 모델 `dragonkue/BGE-m3-ko` 의 출력 차원이다.
대안 `KURE-v1` · `snowflake-arctic-embed-l-v2.0` 도 1024라서 **모델을 바꿔도
이 테이블은 그대로다.**

## `content_start` · `content_end` 를 넣은 이유 (결정 B)

`인수인계.md` 6절에 근거를 적었다. 요약하면 —

리비전 `0010` 이 `ocr_elements` 에 넣은 것과 **같은 좌표계**(`extracted_texts.content`
문자열 안의 위치)다. 두 구간이 겹치는지로 청크를 만든 element 를 찾고, element 의
`x` · `y` · `width` · `height` 로 **원본 페이지에 검색 근거를 네모로 표시**한다.
출처가 "3쪽" 에서 "3쪽 이 위치" 로 올라간다.

**지금 넣는 이유** — 나중에 `ALTER` 로 컬럼을 더하는 것은 쉽지만 **기존 행의 값을
채울 수 없다.** 오프셋을 알려면 재청킹을 해야 한다. 커밋 전인 지금이 가장 싸다.

### 쓸 때 지킬 것 세 가지

| | 함정 | 대응 |
|---|---|---|
| 1 | 오프셋이 `NULL` 인 element 가 실제로 있다 (같은 문자열이 여러 번 나오면 `0010` 백필이 `NULL` 을 넣는다) | 조회에 `content_start IS NOT NULL`. **하이라이트는 "되면 그린다" 이고 보장 기능이 아니다** |
| 2 | `is_in_content = false` 인 element 는 본문에 없다 | 조회에 `is_in_content = true` |
| 3 | `_replace_ocr_content` 는 `ocr_elements` 만 오프셋을 밀어준다. **청크는 안 밀어준다** | 편집 뒤 청크 오프셋은 낡는다. `text_version` 으로 감지하고 **재청킹으로 해결한다** |

3번의 재청킹 트리거는 아직 안 정해졌다. **재정님과 협의할 안건이다**
(`인수인계.md` 7절 5번). 작업 큐가 없다 — `celery` · `redis` 코드 0건을 확인했다.

## 설계에서 뺀 것

| 뺀 것 | 이유 |
|---|---|
| 인덱스 `ix_chunk_doc (document_id, seq)` | `uq_document_chunk_seq` 가 **같은 컬럼 순서의 btree 인덱스를 이미 만든다.** 완전 중복이라 쓰기 비용만 늘었다 |

## 리비전 번호

```
20260812_0010  ocr_content_ranges   재정 · 머지됨 · 현재 head
20260814_0011  document_chunks      보현 · 이 전달분
```

`origin/main` 이 PR #14 로 나아갔지만 `versions/` 의 마지막은 여전히 `0010` 이다.
**`0011` 은 아직 비어 있다. 충돌 없다.**

`20260813_0011` 이 아니라 `20260814_0011` 인 것은 소실 후 8월 14일에 다시 썼기
때문이다. 파일명 날짜 = `revision` 문자열이 이 레포의 관례다.
`down_revision` 은 `20260812_0010`.
