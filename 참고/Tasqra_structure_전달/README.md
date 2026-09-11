# Tasqra — element_type 자동 판정 (`structure.py`)

```
작성      2026-08-14  김보현
대상 레포  ParkSehyeon1009/Tasqra  (팀 레포 · 에이전트는 직접 커밋하지 않는다)
기준 커밋  9e1fc28  Merge pull request #20 from ParkSehyeon1009/document-async-processing
상태      커밋 대기 · 재정님 답변(호출을 누가 붙이나) 대기
```

## 무엇

`element_type` 자동 판정 두 개를 **순수 함수로** 만들었다.
**`extraction_service.py` 를 건드리지 않는다.** 새 파일 두 개만 추가한다.

| 파일 | 내용 |
|---|---|
| `backend/app/extractors/structure.py` | `detect_heading()` · `detect_header_footer()` (196줄) |
| `backend/tests/test_structure.py` | 단위 테스트 (136줄) |

## 왜 필요한가

리비전 `0012` 로 `element_type` 5종이 들어왔지만 **자동으로 채워지는 것은
표 두 개뿐**이다.

| 자동 판정 | 상태 |
|---|---|
| `TABLE_HEADER` · `TABLE_ROW` | 구현됨 (`ocr_extractor._build_table_rows`) |
| `is_paragraph_start` (좌표 기반) | 구현됨 (프론트 `자동 단락 제안`) |
| **`HEADING`** | **없음 — 전부 `TEXT_LINE`** |
| **`HEADER_FOOTER`** | **없음** |

`RAG-001-1` 완료 판정이 *"`element_type` 으로 단락을 묶고"* 인데, 지금은
사람이 전부 손으로 지정해야 충족된다.

### `HEADER_FOOTER` 의 이득이 가장 크다 — 실측 21.1%

한국인터넷진흥원 보고서 17건(1,150페이지)을 상용 파서로 분류한 분포다.

```
paragraph  1,723  52.7%
footer       424  13.0%   <-
heading1     349  10.7%
header       265   8.1%   <-
figure       194   5.9%
list         107   3.3%
table         92   2.8%
chart         58   1.8%
caption·footnote·index  60  1.9%

header + footer = 689 = 전체의 21.1%
```

**다섯 개 중 하나가 반복 상용구다.** 빼지 않으면 24페이지 문서에서 같은 문구가
24번 벡터화되어 검색 결과가 그만큼 오염된다.

---

## 설계 — 오탐을 미탐보다 비싸게 본다

`HEADING` 은 `is_paragraph_start=True` 를 **강제한다**(`document_service` 참고).
**잘못 붙으면 본문 한가운데서 단락이 끊겨 청크가 조각난다.** 반대로 놓치면
사람이 검수 화면에서 한 번 누르면 된다.

**그래서 애매하면 `TEXT_LINE` 으로 남긴다.**

### `detect_heading(text)`

| 받는 것 | 예 |
|---|---|
| 조항 | `제3조(계약의 목적)` · `제 12 조 계약기간` |
| 번호 항목 | `1. 사업개요` · `1.2 추진배경` · `3) 제출서류` |
| 한글 항목 | `가. 입찰참가자격` · `나) 유의사항` |
| 로마자 항목 | `Ⅱ. 사업내용` · `IV. 평가기준` |
| 마크다운 | `## 산출내역` |

| 받지 않는 것 | 이유 |
|---|---|
| **글머리 기호** `■ ○ ● ▪` | **목록 항목이다.** 제목으로 보면 목록마다 단락이 끊긴다 |
| 60자 초과 | 조항 번호로 시작하는 **본문 문장**을 걸러낸다 |
| 문장 종결 | `~한다.` `~제출함` `~확인됨` `~아래와 같음` |
| 번호만 있는 줄 | `1.` `가.` — 표 안의 순번일 수 있다 |
| **번호 없는 제목** | `사업 개요` `총칙` — **판정하지 못한다. 한계다** |

#### 문장 종결에서 `요` 와 `임` 을 뺀 이유

```
넣은 것   다 · 함 · 됨 · 음
뺀 것     요 · 임
```

**`요` 를 넣으면 `사업개요` `추진 개요` 를 놓친다.** 제목으로 아주 흔하다.

**`음` 은 넣었다.** 처음에 뺐더니 `~아래와 같음` `~해당 사항 없음` 이 제목으로
잡혔다. `~있음` `~없음` `~같음` 이 공문서에서 매우 흔해서 오탐이 크게 늘었다.

**`임` 은 판단이 갈려 넣지 않았다.** `책임` `위임` 은 제목에도 쓰이고
`~할 것임` `~예정임` 은 본문이다. **실측으로 정한다.**

### `detect_header_footer(pages)`

```python
pages: Sequence[Sequence[tuple[str, float | None]]]   # (텍스트, y비율)
-> set[tuple[int, int]]                               # (페이지 index, 요소 index)
```

**어떤 클래스에도 의존하지 않는다.** `(텍스트, y비율)` 튜플만 받는다.
`LayoutElement` 는 절대 좌표이고 `OcrElement` 는 정규화 좌표라, 어느 쪽에서
불러도 되도록 호출하는 쪽이 맞춰 넣게 했다.

| 판정 조건 | 기본값 |
|---|---|
| 페이지 상·하단 대역 안 | `band = 0.12` |
| 여러 페이지에 반복 | `min_pages = 3` **또는** 전체의 `min_ratio = 0.5` 중 큰 값 |

**쪽번호가 페이지마다 다르므로 숫자를 `#` 으로 정규화해 비교한다.**
`- 3 -` 와 `- 4 -` 를 같은 것으로 본다.

**이 치환은 의도적으로 과감하다.** `제3장 사업개요` 와 `제4장 사업개요` 도 같은
것으로 보는데, 장이 넘어가도 이어지는 머리글을 잡으려면 그래야 한다.
**대가로 본문에서는 숫자만 다른 줄이 묶인다.** 그래서 상·하단 대역만 보는 것이
기본값이다.

**한 페이지에 같은 텍스트가 두 번 인식돼도 그 페이지는 1회로 센다.**
같은 줄이 중복 검출된 경우에 값이 부풀지 않게 한다.

---

## 검증

### 단위 테스트 — 39개 통과

`pytest` 가 없는 환경이라 함수를 직접 불러 돌렸고 **39개 전부 통과했다.**
`test_structure.py` 는 같은 내용을 `pytest` 형식으로 담고 있다.

```powershell
cd C:\dev\Tesqra\Tasqra\backend
python -m pytest tests/test_structure.py -v
```

### 실제 문서 정확도 — 아직 재지 않았다

`도구/embed-test/check_structure_rules.py` 를 만들어 뒀다. KISA 보고서
`elements` 라벨을 정답으로 **재현율·오탐률·정밀도**를 낸다.

```powershell
cd C:\dev\embed-test
python check_structure_rules.py
```

**정직하게 볼 것 두 개**

| | 내용 |
|---|---|
| 1 | **마크다운 표기(`#`)를 떼고 잰다.** 안 떼면 파서가 붙인 표기를 우리가 맞히는 셈이라 정확도가 부풀려진다 |
| 2 | **`elements` 라벨에 좌표가 없다.** 머리글·바닥글은 `use_position=False` 로 재므로 **오탐이 실제보다 높게 나온다.** 위치 조건은 실제 문서로 따로 봐야 한다 |

**오탐률이 재현율보다 중요하다.** 위 설계 이유와 같다.

---

## 호출은 재정님과 정한다

**이 패치에는 호출부가 없다.** `extraction_service.py` 를 건드리지 않으므로
지금 상태로 커밋해도 아무것과도 충돌하지 않는다.

붙일 자리는 이렇다.

```python
# extraction_service.py — OcrElement 를 만드는 자리
element_type=structure.detect_heading(item.text) and "HEADING" or item.element_type
element_type_source="AUTO"
```

**`HEADER_FOOTER` 는 페이지 전체를 봐야 판정되므로 페이지 루프가 끝난 뒤에 한 번
돌려야 한다.** 그 위치를 재정님과 정해야 한다.

주의 — `element_type` 을 덮어쓸 때 **이미 `TABLE_HEADER`/`TABLE_ROW` 인 것은
건드리지 않아야 한다.** 표 판정이 더 확실하기 때문이다.

### 재정님께 물은 것 (답 대기)

| | 물음 |
|---|---|
| 1 | `structure.py` 를 우리가 PR 올려도 되나. 호출은 누가 붙이나 |
| 2 | `HEADER_FOOTER` 판정을 어디서 돌릴까 (페이지 루프 뒤) |
| 3 | PDF 텍스트 레이어 경로는 표 인식이 없어 `table_id` 가 항상 `None` 이다. 나중 과제로 둘까 |
| 4 | `REV-004-1` 비고 `offset 기록 불필요` 가 지금도 유효한가 |

---

## 적용

```powershell
cd C:\dev\Tesqra\Tasqra
git checkout main
git pull
git checkout -b feat/element-type-auto-detect

git apply --check "C:\dev\deliver\참고\Tasqra_structure_전달\structure-auto-detect.patch"
git apply "C:\dev\deliver\참고\Tasqra_structure_전달\structure-auto-detect.patch"
git status
```

기대 결과 — **신규 2** (수정 0)

```
?? backend/app/extractors/structure.py
?? backend/tests/test_structure.py
```

**`9e1fc28` 기준으로 깨끗하게 적용되는 것을 별도 클론에서 확인했다.**
**리비전 `0014` 패치와 함께 적용해도 충돌하지 않는다** (건드리는 파일이 다르다).

## 커밋

```powershell
git add backend/app/extractors/structure.py backend/tests/test_structure.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat: element_type 자동 판정 (HEADING · HEADER_FOOTER) 순수 함수 추가"
git push -u origin feat/element-type-auto-detect
```

`--stat` 은 **2개 파일 · 332 insertions** 여야 한다.

**마이그레이션이 없고 기존 파일을 안 건드린다.** 컨테이너 재생성도, 팀 공지도
필요 없다. 호출부가 없으므로 **동작이 바뀌지 않는다** — 함수만 들어간다.
