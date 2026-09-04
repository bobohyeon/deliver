# 리비전 0014 실행계획 실측 (2026-08-18)

## 이 문서에 나오는 기능 ID

| ID | 작업명 | 담당 |
|---|---|---|
| `RAG-04` (=`SRH-001`) | 의미 검색 — 글자가 겹치지 않는 질의로 관련 문서를 찾는다 | 보현 |
| `RAG-12` (=`SRH-002-3`) | 유사 사업 단가 선례 검색 — 과거 사업 문서에서 단가를 찾는다 | 보현 |
| 리비전 `0014` | `document_chunks.project_id` 역정규화 | 보현 (머지됨) |

---

## 결론 세 줄

1. **`=` 와 `IN` 의 실행계획이 같다.** 전체 검색에 별도 대책이 필요 없다
2. **리비전 0014 는 옳았다.** 다만 **내가 설명한 근거가 틀렸다** — 아래에서 정정한다
3. `iterative_scan` 이 선택도에 비례해 후보를 더 꺼내오는 것을 실측으로 확인했다

---

## 측정 조건

| | |
|---|---|
| 청크 | **6,016개** (합성 6,000 + 실제 16) |
| 프로젝트별 | 1 → 2,010 · 2 → 2,004 · 3 → 2,002 |
| 인덱스 | `ix_chunk_vec` (HNSW · `vector_cosine_ops`) |
| 설정 | `hnsw.iterative_scan = strict_order` · `hnsw.ef_search = 100` |
| pgvector | 0.8.6 |
| 임베딩 | `fake-hash-v1` (해시 기반 결정적 단위벡터) |

합성 벡터는 난수다. 검색 **품질**이 아니라 **실행계획**을 보려는 것이었다.
측정 후 `cleanup_bulk_chunks.sql` 로 전부 지웠다 (지운 뒤 실제 청크 16개 확인).

---

## 측정 결과

### 단일 프로젝트 — `project_id = 1` (약 1/3 선택도)

```
Limit (rows=5) (actual time=3.290..3.328 rows=5)
  -> Nested Loop
       -> Index Scan using ix_chunk_vec on document_chunks (actual rows=5)
            Order By: (embedding <=> '[...1024차원...]'::vector)
            Filter: ((project_id = 1) AND (embedding_model = 'fake-hash-v1'))
            Rows Removed by Filter: 12
       -> Index Scan using documents_pkey on documents
            Index Cond: (id = document_chunks.document_id)
Execution Time: 3.462 ms
```

### 여러 프로젝트 — `project_id IN (1, 2)` (약 2/3 선택도)

```
Limit (rows=5) (actual time=4.490..4.530 rows=5)
  -> Nested Loop
       -> Index Scan using ix_chunk_vec on document_chunks (actual rows=5)
            Order By: (embedding <=> '[...1024차원...]'::vector)
            Filter: ((project_id = ANY ('{1,2}'::bigint[])) AND (embedding_model = 'fake-hash-v1'))
            Rows Removed by Filter: 3
       -> Index Scan using documents_pkey on documents
            Index Cond: (id = document_chunks.document_id)
Execution Time: 4.565 ms
```

### 대조군 — `documents` 를 조인해서 필터 (0014 없이 했을 경우)

```
-> Index Scan using ix_chunk_model on document_chunks c   (rows=16)
     Index Cond: ((c.embedding_model)::text = 'fake-hash-v1')      <- project_id 가 없다
-> Index Scan using ix_doc_type on documents d            (rows=2, loops=16)
     Index Cond: (d.project_id = 1)                                 <- 여기서 걸린다
Join Filter: (c.document_id = d.id)
Rows Removed by Join Filter: 16                                     <- 꺼낸 뒤 버린다
```

---

## 비교표

| | `=` (1/3) | `IN` (2/3) |
|---|---|---|
| 사용 인덱스 | `ix_chunk_vec` (HNSW) | **같음** |
| 정렬 | `Order By: embedding <=> ...` | **같음** |
| 조건 위치 | 스캔 노드의 `Filter` | **같음** |
| 버린 행 | **12** | **3** |
| 실행 시간 | 3.46 ms | 4.57 ms |

**버린 행 수가 선택도에 반비례한다.** 프로젝트 1만 보면 후보 3개 중 1개만 살아남으니
5개를 얻으려 17개를 꺼냈고(12개 버림), 1+2 를 보면 3개 중 2개가 살아남으니 8개만
꺼냈다(3개 버림). `iterative_scan` 이 부족분을 감지해 더 훑고 있다는 뜻이다.

---

## 내가 틀렸던 것 — 판단 기준 정정

앞서 이렇게 적었고, 그것을 코드 주석·SQL·테스트에 넣었다.

> `Index Cond: (project_id = 1)` 이면 조건이 인덱스 안에서 걸러진다 (좋다)
> `Filter: (project_id = 1)` 이면 꺼낸 뒤 걸러낸다 (나쁘다)

**이 기준은 HNSW 에서 성립하지 않는다.**

`ix_chunk_vec` 은 `embedding` 컬럼만 색인한다. `project_id` 는 인덱스 안에 없으므로
**`Index Cond` 가 되는 것이 구조적으로 불가능하다.** pgvector 문서도 근사 인덱스에서는
필터가 인덱스 스캔 뒤에 적용된다고 명시한다
([pgEdge pgvector 문서](https://docs.pgedge.com/pgvector/v0-8-5/filtering/)).
HNSW 는 `ef_search` 개의 후보 집합을 먼저 만들고, 그 다음 `WHERE` 를 적용한다.
살아남은 행이 모자라면 재현율이 조용히 떨어진다
([관련 분석](https://varunsls.hashnode.dev/filtered-vector-search-in-pgvector-can-silently-lose-recall)).
*(라이선스 준수를 위해 내용을 재구성했습니다)*

### 올바른 기준

**`project_id` 는 항상 `Filter` 다. 중요한 것은 그 `Filter` 가 어느 노드에 붙는가다.**

| 위치 | 결과 |
|---|---|
| `Index Scan using ix_chunk_vec` 노드의 `Filter` | **좋다.** 살아남은 행이 `LIMIT` 에 못 미치면 `iterative_scan` 이 인덱스를 더 훑는다 |
| 그 위 노드의 `Join Filter` | **나쁘다.** HNSW 스캔은 자기 결과가 걸러졌다는 것을 모르므로 더 꺼내오지 않는다. 결과가 조용히 적어진다 |

대조군이 이것을 보여준다. 조인으로 걸면 `project_id` 조건이 청크 스캔 노드에
아예 없고, `Rows Removed by Join Filter: 16` 으로 **스캔 밖에서** 걸러진다.

**결론은 그대로다** — 리비전 0014 는 필요했다. 근거만 정정한다.

---

## 아직 확인하지 않은 것

**조인 방식이 실제로 결과를 적게 돌려주는 것을 직접 재지는 않았다.**
대조군 계획은 HNSW 스캔이 아니라 일반 인덱스 스캔이었다(행이 16개일 때 측정).
구조적 근거는 확인했지만, "HNSW + 조인" 조합에서 `LIMIT 10` 을 요청했을 때 실제로
10개보다 적게 나오는 것을 세어 보지는 않았다.

재려면 이렇게 하면 된다.

1. `seed_bulk_chunks.sql` 로 합성 청크를 넣는다
2. 같은 질의를 두 방식으로 돌려 **반환 행 수를 센다** (`EXPLAIN` 이 아니라 결과 개수)
   - `WHERE c.project_id = 1` (0014 방식)
   - `JOIN documents d ... WHERE d.project_id = 1` (조인 방식)
3. 프로젝트 하나가 전체의 5% 정도가 되도록 비율을 낮추면 차이가 크게 벌어진다
4. 끝나면 `cleanup_bulk_chunks.sql`

지금 방식이 옳다는 것은 확인됐으므로 급하지 않다. 다만 "조인이 왜 안 되는지"를
팀에 설명할 때 숫자가 있으면 더 분명해진다.

---

## 함께 확인된 것 — `RAG-04` 격리

같은 실행에서 `SearchService` 통합 테스트 **검사 20개가 모두 통과**했다.

| | 확인 |
|---|---|
| `project_ids = None` | 내 멤버십 `[1, 2]` 로 풀림. **프로젝트 3 결과에 없음** |
| `project_ids = [3]` | `PROJECT_NOT_FOUND` (멤버가 아니다) |
| `project_ids = [1, 3]` | 섞어도 거부 |
| `project_ids = [999999]` | 없는 id 도 거부 |
| `project_ids = []` | 스키마에서 `ValidationError` |
| 대조 | 조건 없이 세면 프로젝트 3 에 청크가 있다 → 조건이 실제로 일하고 있다 |

`RAG-04` 판정 기준 중 **"내가 멤버가 아닌 프로젝트의 문서는 나오지 않는다"** 가
실측으로 확인됐다.

판정 기준을 이렇게 읽는 이유는 `RAG-12`(=`SRH-002-3`) 와의 모순 때문이다.
기능명세서가 `RAG-04` 에 "다른 프로젝트 문서는 나오지 않는다"고 쓰고,
`RAG-12` 에 "**과거 사업 문서에서** 같은 항목의 단가를 찾아 출처와 함께 보여준다"고
쓴다. 과거 사업은 다른 프로젝트이므로 앞 문장을 문자 그대로 읽으면 두 기능이
서로를 부정한다. **"내가 멤버가 아닌 프로젝트"** 로 읽으면 둘 다 만족한다.

---

## 남은 성능 과제

`fake-hash-v1` 으로 3.5~4.6ms 다. 실제 모델로 바꾸면 **질의 임베딩 시간**이 더해진다.
BGE-M3 는 CPU 에서 질의 1건에 수백 ms 가 걸릴 수 있다. 즉 검색 지연의 대부분이
DB 가 아니라 임베딩이 될 것이다. 그때 다시 재야 한다.
