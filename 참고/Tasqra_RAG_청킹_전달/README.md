# RAG 청킹 · 임베딩 전달 (2026-08-14 일요일)

## 이 문서에 나오는 기능 ID

| ID | 작업명 | 담당 |
|---|---|---|
| `RAG-01` | 텍스트 정규화 · 청킹 | 보현 |
| `RAG-02` | 임베딩 생성 · 저장 | 보현 |
| `RAG-04` | 의미 검색 | 보현 |
| `RAG-09` | 검수 확정 시 재임베딩 | 보현 |
| `TSK-01` | 태스크 CRUD | **미정** |
| `TSK-03` | AI 제안 → 태스크 확정 (승인) | **미정** |
| `ANL-03` | 항목 추출 분석기 (액션아이템 · 결정 · 일정) | 세현 |

기능명세서의 ID 는 **두 자리**다 (`RAG-01`). 앞서 인수인계에 `RAG-001-1`·`TSK-002`·
`ANL-002-1` 로 적혀 있던 것은 잘못이다. 그런 ID 는 존재하지 않는다.

또한 인수인계에 `TSK` 담당이 "재정"으로 적혀 있었으나 **기능명세서 10절은 "담당 미정"**
이다. 태스크 라우터를 만들기 전에 합의가 필요하다.

---

## 무엇을 만들었나

`RAG-01` 청킹과 `RAG-02` 임베딩 생성·저장이다. **실제 임베딩 모델 없이 파이프라인
전체가 끝까지 돈다.**

| 파일 | 줄 | 역할 |
|---|---|---|
| `app/services/chunking.py` | 715 | 자르는 규칙. 순수 함수. DB · 모델 · 네트워크를 모른다 |
| `app/services/chunking_service.py` | 250 | 문서 → 청크 → 벡터 → DB 조립. `project_id` 를 채우는 곳 |
| `app/embedding/protocol.py` | 68 | 임베딩 계약 (Java interface) |
| `app/embedding/fake_client.py` | 88 | 해시 기반 결정적 1024차원 단위벡터. 메모리 0 |
| `app/embedding/local_client.py` | 95 | OpenAI 호환 `/v1/embeddings` 호출. 컨테이너 메모리 0 |
| `app/repositories/chunk_repository.py` | 87 | `document_chunks` 접근 |
| `app/core/constants.py` | 22 | `EMBEDDING_DIM` 을 ORM 의존 없이 옮김 |
| `tests/test_chunking.py` | 425 | 검사 75개 |

`app/worker.py` 에 셀러리 태스크 `chunks.build` 를 추가했고, `dependencies.py` 에
`get_embedding_client()` 를 넣었다 (`get_ai_client()` 와 같은 방식).

### 새 의존성이 없다

`requirements.txt` 를 **건드리지 않았다.** `torch` · `sentence-transformers` 를 넣지
않았고, 실제 임베딩 경로는 이미 있는 `openai` SDK 로 HTTP 를 부른다.
`docker-compose.yml` 도 건드리지 않았다.

이유는 메모리다. `api` 와 `worker` 가 **같은 Dockerfile** 을 쓰므로
`sentence-transformers` 를 넣으면 두 이미지가 함께 무거워지고, 두 컨테이너가 각각
약 2.3GB(BGE-M3 float32)를 올린다. 합계 약 4.6GB 다. 개발 노트북 가용 메모리가
4.8GB 였으므로 들어가지 않는다. `api` 는 `--reload` 라서 코드를 저장할 때마다
모델을 다시 읽는 문제도 있다.

정확도 측정은 도커 밖 `C:\dev\embed-test` 에서 계속한다. 거기에 이미
sentence-transformers 가 있고, 컨테이너에 넣을 이유가 없었다.

---

## 적용 방법 — 파일 복사 (권장)

**패치 파일(`.patch`)은 이 환경에서 쓰지 마세요.** `core.autocrlf=true` 때문에
GitHub 에서 받을 때 `LF` 가 `CRLF` 로 바뀌어 `git apply` 가 깨집니다
(`git diff header lacks filename information` 오류). 실제로 한 번 겪었습니다.
`.gitattributes` 에 `*.patch -text` 를 넣어 앞으로는 안 바뀌게 했지만,
**이미 받은 파일은 여전히 CRLF 입니다.**

파이썬 파일은 CRLF 여도 정상 동작하므로 **소스 파일을 그대로 복사하는 것이
안전합니다.** 두 방식이 바이트 단위로 같은 결과를 내는 것을 확인했습니다 (13/13 동일).

```powershell
cd C:\dev\deliver
git pull

# 1) structure.py 오탐 수정 (어제 것)
cd C:\dev\Tesqra\Tasqra
git checkout main
git pull
git checkout -b fix/structure-false-positives
robocopy "C:\dev\deliver\참고\Tasqra_RAG_청킹_전달\파일-01-structure\backend" ^
         "C:\dev\Tesqra\Tasqra\backend" /E /NFL /NDL /NJH /NJS
git status --short
git add backend/app/extractors/structure.py backend/tests/test_structure.py
git commit -m "fix: detect_heading 실측 오탐 수정 (수치 표현 · 끝 괄호)"
git push -u origin fix/structure-false-positives

# 2) 청킹 + 임베딩
git checkout main
git checkout -b feat/rag-chunking-embedding
robocopy "C:\dev\deliver\참고\Tasqra_RAG_청킹_전달\파일-02-rag\backend" ^
         "C:\dev\Tesqra\Tasqra\backend" /E /NFL /NDL /NJH /NJS
git status --short
```

`robocopy` 의 `/E` 는 하위 폴더까지 포함하고, 나머지 옵션은 출력을 줄이는 것입니다.
같은 이름의 파일은 덮어씁니다.

**커밋 전에 반드시 2단계 검증을 먼저 하세요** (아래 「검증」). 확인된 뒤에:

```powershell
git add backend/app backend/tests/test_chunking.py
git commit -m "feat: RAG-01 청킹 + RAG-02 임베딩 생성·저장 (가짜 임베더 기본값)"
git push -u origin feat/rag-chunking-embedding
```

### 기대하는 `git status --short`

패치 1 적용 후:

```
 M backend/app/extractors/structure.py
 M backend/tests/test_structure.py
```

패치 2 적용 후:

```
 M backend/app/core/config.py
 M backend/app/dependencies.py
 M backend/app/models/chunk.py
 M backend/app/worker.py
?? backend/app/core/constants.py
?? backend/app/embedding/
?? backend/app/repositories/chunk_repository.py
?? backend/app/services/chunking.py
?? backend/app/services/chunking_service.py
?? backend/tests/test_chunking.py
```

수정 4개 · 신규 9개(`embedding/` 안에 4개)다.

### 패치 파일을 꼭 써야 한다면

CRLF 를 되돌린 뒤 적용합니다.

```powershell
$src = "C:\dev\deliver\참고\Tasqra_RAG_청킹_전달\02-rag-chunking-embedding.patch"
[IO.File]::WriteAllText("C:\dev\rag.patch", ([IO.File]::ReadAllText($src) -replace "`r`n", "`n"))
cd C:\dev\Tesqra\Tasqra
git apply C:\dev\rag.patch
```

`[IO.File]::WriteAllText` 는 BOM 없는 UTF-8 로 쓰므로 `Set-Content` 보다 안전합니다.

### 검증

```powershell
cd backend
python tests\test_chunking.py        # 검사 75개 통과 · 실패 0
```

컨테이너 안에서 파이프라인까지 보려면:

```powershell
docker compose up -d --build
# 문서를 업로드한 뒤 (document_id 확인)
docker compose exec worker python -c "from app.worker import build_chunks_task; print(build_chunks_task.apply(args=[1, 1]).get())"
docker compose exec db psql -U postgres -d tasqra -P pager=off -c "SELECT seq, project_id, page_number, char_count, token_count, embedding_model FROM document_chunks ORDER BY seq LIMIT 10"
```

`USE_FAKE_EMBEDDING` 기본값이 `true` 라 모델 없이 돌아간다.

---

## 청킹 규칙

적용 순서다.

1. `HEADER_FOOTER` 는 버린다. 모든 페이지에 같은 문자열이 반복되어 "어떤 질의에도
   걸리는 노이즈"가 된다.
2. `HEADING` 에서 끊고, 그 제목을 이후 청크의 **접두어로 유지한다.** 제목이 없으면
   "3.2 대금 지급" 밑의 본문만 검색되어 무슨 항목인지 알 수 없다.
3. `is_paragraph_start` 에서 끊을 수 있으면 끊는다.
4. 같은 `table_id` 는 붙여 둔다. 넘치면 쪼개고 **`TABLE_HEADER` 를 각 조각에 반복**한다.
   표 행만 떨어져 나가면 열 이름을 잃는다.
5. 그래도 상한을 넘으면 문장 경계 → 공백 → 강제 순으로 자른다.
6. `min_tokens` 미만은 다음 청크에 붙인다. 단 **문서 끝의 짧은 조각은 버리지 않는다.**

### 재정님 호출부가 없어도 돌아간다

현재 DB 의 `element_type` 은 전부 `TEXT_LINE` 이고 `is_paragraph_start` 는 전부
`false` 다. 그래서 **구조 정보가 하나도 없어 보이면 `structure.py` 로 직접 판정한다.**
나중에 호출부가 붙어 값이 들어오면 그 값을 그대로 존중한다 (덮어쓰지 않는다).

`ocr_elements` 가 아예 없는 문서(PDF 텍스트 레이어만 있는 경우)는
`extracted_texts.content` 를 줄 단위로 쪼갠다. 두 경로 모두
`content_start` / `content_end` 를 같은 좌표계로 채운다.

---

## 고친 버그 · 내린 결정

### 1. 표를 쪼갤 때 상한을 넘었다 (테스트가 잡음)

각 조각에 `TABLE_HEADER` 를 반복해 넣으면서 그 토큰을 예산에서 빼지 않았다.
두 번째 조각부터 `max_tokens` 를 초과했다. 접두어(제목)와 표 헤더행 토큰을 모두
미리 빼도록 고쳤다.

### 2. `가.` `나.` `다.` 목록이 제목으로 잡혀 조각났다

`structure.py` 의 `detect_heading` 은 한글 항목(`_HANGUL_ITEM`)을 제목으로 본다.
조달문서에서 "가. 제출서류는 아래와 같음" 처럼 실제 제목으로 쓰이므로 **그 판정 자체는
맞다.** 그런데 청킹에서 이것을 제목 문맥으로 쓰면 이렇게 된다.

```
2. 입찰 참가 자격          <- 진짜 제목이 사라진다
가. ... 요건을 갖춘 자
나. 소프트웨어사업자 신고를 마친 자     <- 이것이 제목이 되어 버린다
```

`is_strong_heading()` 을 두어 한글 항목은 **단락 경계로만** 쓰고 제목 문맥은 상위
것을 유지하게 했다. **`structure.py` 는 고치지 않았다** — 판정은 맞고, 이건 청킹의
해석 문제다.

고친 뒤: `가`·`나`·`다` 가 `2. 입찰 참가 자격` 아래 한 청크로 모인다.

### 3. 겹침(overlap)이 제목을 청크 중간으로 밀어냈다

앞 청크 꼬리를 다음 청크 **맨 앞**에 붙여서 제목이 뒤로 밀렸다.

```
전: "개인 정보는 원문에서 이미 가려져 있다. … / ## 공고 일반 / 공고종류: …"
후: "## 공고 일반 / 개인 정보는 원문에서 이미 가려져 있다. … / 공고종류: …"
```

BGE-M3 는 **CLS 풀링**이라 앞쪽 토큰이 주제 신호로 더 크게 작용한다. 제목이 뒤로
밀리면 검색 품질이 떨어지고 결과 스니펫 첫 줄도 엉뚱해진다. 겹침을 제목 뒤에
넣도록 고쳤다.

처음 고칠 때 `prefix` 가 빈 경우(묶음이 청크 하나로 끝날 때 제목이 접두어가 아니라
본문 첫 줄에 있는 경우)를 놓쳐 한 번 더 고쳤다.

### 4. 테스트가 실패를 잡지 못했다

검사 실패를 리스트에 모으기만 해서, **pytest 로 돌리면 로직이 깨져도 초록색으로
통과**했다. `assert` 로 던지게 바꾸고, 단독 실행 시에는 테스트 함수 단위로 예외를
잡아 요약을 만들게 했다. 일부러 로직을 깨서 실제로 잡히는지 확인했다.

### 5. 요소 정렬에 동점 처리가 없었다

`(page_number, reading_order)` 로만 정렬해서, 같은 `page_number` 를 가진
`DocumentPage` 가 둘 생기면 두 페이지 요소가 섞인다. `document_pages` 에는
`page_kind` 가 `"PAGE"` 와 `"EMBEDDED_IMAGE"` 두 종류가 있다.

확인해 보니 **현재는 충돌하지 않는다** — `docx`·`hwpx` 모두
`len(review_pages) + 1` 로 문서 단위 연번을 쓴다. 그래도 `page_id` 를 동점
처리로 넣었다. 그 규칙이 바뀌면 **에러 없이 청크 내용만 조용히 달라지는** 고장이
되기 때문이다.

### 6. `EMBEDDING_DIM` 을 `core/constants.py` 로 옮겼다

가짜 임베더가 상수 하나 때문에 ORM 전체를 끌어와서, DB 드라이버 없이 단독 검증을
할 수 없었다. `models/chunk.py` 에서 이름을 다시 내보내 기존 import 는 그대로 된다.

---

## 미검증 — 확인하지 못한 것

| 항목 | 상태 |
|---|---|
| `CHARS_PER_TOKEN = 1.2` | **실측하지 않은 근사값.** 실제 토크나이저로 재서 고쳐야 한다. 과대추정이면 청크가 짧아질 뿐 오류는 없다 |
| `LocalEmbeddingClient` 실동작 | 노트북에 Ollama 가 없어 확인 못 함 (`ollama --version` 이 CommandNotFound) |
| GGUF 양자화의 검색 품질 영향 | 알려진 자료는 전부 LLM perplexity 기준이다. 임베딩 검색 수치가 아니다 |
| GGUF 풀링 방식 | BGE-M3 dense 는 CLS 풀링이다. 메타데이터가 mean 이면 **에러 없이 조용히** 품질이 떨어진다 |
| `CHKH01/BGE-m3-ko-GGUF` 출처 | 커뮤니티 저장소. 정말 `dragonkue/BGE-m3-ko` 에서 변환한 것인지 확인 못 함 |
| `iterative_scan` 실행계획 | 청크가 생긴 뒤 `EXPLAIN ANALYZE` 로 봐야 한다. 아직 안 봤다 |
| 컨테이너에서 파이프라인 E2E | 문법·단위 검증만 했다. 도커 안에서 실제 문서로 돌린 적 없다 |

`sqlalchemy` 가 샌드박스에 없어 ORM 이 걸린 파일은 **문법 검사만** 했다.
`chunking.py` 와 `fake_client.py` 는 실제로 실행해 검증했다.

---

## 실측 결과

실제 문서 3건(`도구/embed-test/corpus`)에 대해 `max_tokens=480 · overlap=48`:

| 문서 | 청크 | 토큰 평균 | 최대 | 구간 불일치 | 제목 위치 오류 | 상한 초과 |
|---|---|---|---|---|---|---|
| 산출내역서 | 3 | 134 | 189 | 0 | 0 | 0 |
| 입찰공고 | 9 | 163 | 315 | 0 | 0 | 0 |
| 회의록 | 2 | 142 | 155 | 0 | 0 | 0 |

"구간 불일치"는 `content[content_start:content_end]` 가 원래 텍스트와 다른 건수다.
0 이면 검색 근거 하이라이트 좌표가 정확하다는 뜻이다.

---

## 재정님께 보낼 메시지 (초안)

> 재정님, 두 가지 전달드립니다.
>
> **1. `structure.py` 정확도 실측**
> KISA 보고서 17건 · 11,499요소로 측정했습니다.
>
> | 함수 | 오탐률 | 재현율 | 정밀도 |
> |---|---|---|---|
> | `detect_heading` | 2.5% (117/4,681) | 22.5% (383/1,704) | 76.6% |
> | `detect_header_footer` | 2.1% | 50.0% (1,349/2,698) | 87.8% |
>
> 앞서 머리글·바닥글 비율을 **21.1% 로 말씀드렸는데 23.5% (2,698/11,499) 로 정정**합니다.
> 그때는 표본값이었습니다.
>
> `detect_heading` 오탐 117개는 대부분 실제로는 제목(`제 1 장`, `3. 글로벌 사이버 위협
> 동향`)인데 파서가 본문으로 라벨한 것이라, 정밀도는 실제로 더 높습니다.
> 실측에서 찾은 진짜 버그 2개(`5.8%` 같은 수치 표현, 끝 괄호가 물음표를 가리는 경우)는
> 별도 브랜치로 올렸습니다.
> 남은 과제는 `min_ratio` 를 0.5 → 0.2 로 낮춰 머리글·바닥글 재현율을 올리는 실험입니다.
>
> **2. 청킹·임베딩을 올렸습니다 — 한 줄만 부탁드립니다**
> `RAG-01` 청킹과 `RAG-02` 임베딩을 별도 셀러리 태스크 `chunks.build` 로 만들었습니다.
> 문서 추출 파이프라인(`ExtractionService.process_document`)은 **건드리지 않았습니다.**
> 추출이 끝난 자리에 이 한 줄만 넣어 주시면 연결됩니다.
>
> ```python
> from app.worker import build_chunks_task
> build_chunks_task.delay(project_id, document_id)
> ```
>
> `requirements.txt` 와 `docker-compose.yml` 은 건드리지 않았습니다. 임베딩 모델을
> 컨테이너에 올리지 않고, 기본값은 가짜 임베더(`USE_FAKE_EMBEDDING=true`)라
> 팀원분들 환경에 영향이 없습니다. `USE_FAKE_AI` 와 같은 방식입니다.
>
> **3. 태스크 영역을 여쭤봅니다**
> 기능명세서 10절 `TSK` 가 "담당 미정"이고, 백엔드에 `tasks` 테이블이 아직 없습니다
> (마이그레이션에 없습니다). 프론트에 `BoardView.jsx` 는 있는데 API 를 쓰지 않습니다.
> 재정님이 칸반(`TSK-02`)을 어디까지 보고 계신지 알려주시면 겹치지 않게 맞추겠습니다.
> 제가 태스크 CRUD(`TSK-01`) + 승인·거절(`TSK-03`·`TSK-07`)을 맡아도 될까요?
> 다만 승인 대상 제안을 만드는 `ANL-03`(항목 추출, 세현님)이 아직 없어서, 테이블
> 설계부터 시작하게 됩니다. 그리고 18절 미결 안건 5·6번(`tasks.completed_at` ·
> `source_amount_item_id`)이 열려 있어 그것부터 정하는 게 좋겠습니다.

---

## 다음에 할 것

1. **`RAG-04` 의미 검색 API** — `WHERE project_id = X` 가 같은 테이블 조건이 되게
   (`iterative_scan` 전제). 청크가 생겼으니 `EXPLAIN ANALYZE` 로 계획을 확인할 수 있다.
2. **`CHARS_PER_TOKEN` 실측** — `embed-test` 에서 실제 토크나이저로 문자/토큰 비를 재고
   `config.py` 기본값을 고친다.
3. **프론트 3종 + `SuggestionCard`** — `features/amounts` · `features/deliverables` ·
   `features/search`, `api/amount.js` · `deliverable.js` · `search.js`. 전부 없다.
4. **`ir_eval` 측정 마무리** — `chunks_ours.bak` 이 649청크임을 확인했다.
   `make_chunks.py` 를 다시 돌리면 4,967청크가 되어 비교가 깨진다. 실행하지 말 것.
