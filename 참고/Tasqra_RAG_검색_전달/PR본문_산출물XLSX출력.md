# PR 본문 — 산출물 XLSX 출력 (복사해 붙이는 용도)

**패치 파일**: `52-deliverable-xlsx-format.patch` → 그 위에
`53-deliverable-xlsx-report-quality.patch` (**둘 다 적용해야 합니다.** 53 이
52 위에 얹히는 보완 패치입니다 — 52 만 적용하면 XLSX 가 거의 빈 파일로 나옵니다)
**베이스**: `origin/main` = `d1e0e45` (2026-08-25 PR #71 머지 시점)

**제목**

```
feat: 산출물 XLSX 출력 - 담길 내용 501 채우기 (DLV-002-1)
```

**아래 선 밑을 전부 복사해서 PR 본문에 붙입니다.**

---

## 무엇

산출물 출력 형식 넷(`XLSX`·`HTML`·`MD`·`PDF`) 중 `XLSX` 를 추가로 만들 수 있게
합니다. `SUPPORTED_DELIVERABLE_FORMATS` 가 `("MD", "HTML")` → `("MD", "HTML",
"XLSX")` 가 됩니다. 남은 것은 `PDF` 하나(501 유지, 이 PR 에서 건드리지 않음).

## 왜 한 줄로 안 끝났나

`RENDERERS` 에 한 줄 더하면 될 줄 알았는데 코드로 확인하니 걸리는 것이 셋이었습니다.

### ① `openpyxl` 이 새 의존성입니다

MD·HTML 은 문자열만 만들면 돼서 의존성이 0 이었습니다. `requirements.txt` 에
`openpyxl==3.1.5` 를 추가했습니다 — **머지 후 `docker compose build api` 가
필요합니다.** 순수 파이썬 라이브러리라 이미지 크기 증가는 미미합니다(torch 같은
무거운 의존성 없음).

### ② `_write_file` 이 문자열만 받았습니다

```python
def _write_file(project_id: int, body: str, extension: str) -> str:
    ...
    with open(path, "w", encoding="utf-8") as file:
        file.write(body)
```

XLSX 는 zip 컨테이너라 바이너리입니다. `body: str | bytes` 로 넓히고, `bytes` 면
`"wb"` 로 쓰도록 분기했습니다. MD·HTML 은 그대로 `str` 경로를 타므로 회귀가
없습니다.

### ③ 새 렌더러 `deliverable_xlsx.py`

`deliverable_html.py`·`deliverable_markdown.py` 와 같은 구조입니다 —
`build_document()` 가 만든 형식 무관 문서 구조(`DeliverableDocument`)를 받아
그리기만 합니다. 절을 고르는 규칙은 여기 없습니다(그 파일들과 같은 이유).

시트 구성:

| 시트 | 내용 |
|---|---|
| `요약` | 제목·기간·개요 + **어느 시트에 무엇이 몇 건 있는지** 표 |
| 절 이름별 | 표가 있는 절마다 하나 (문서 / 완료한 태스크 / 결정사항 / 일정·기한 / 금액) |

**판단 셋을 짚어 둡니다.**

**절이 비어도 시트를 만듭니다.** "행이 있는 절만 시트로" 만들면 자료가 없는 주에
파일을 열었을 때 절이 사라집니다 — 받는 사람은 그것을 "빠뜨렸다" 로 읽습니다.
그래서 0건이어도 시트를 만들고 머리글과 «없습니다» 문장을 함께 넣습니다.
HTML·MD 가 빈 절에도 문장을 적는 것과 같은 판단입니다.

**요약 시트를 채웁니다.** 엑셀은 첫 시트를 열어서 보여줍니다. 제목 세 줄만 있는
시트가 먼저 보이면 파일이 비어 보입니다. 그래서 제목·기간·개요와 함께 어느 시트에
무엇이 몇 건 있는지 표로 적습니다 — 시트 탭을 하나씩 눌러보지 않아도 됩니다.

**금액·수량을 숫자로 넣습니다.** XLSX 를 고르는 이유가 «표 계산과 편집» 입니다.
`"6,000,000"` 이 글자로 들어가면 합계가 안 나와서 형식을 고른 이유가 없어집니다.
머리글이 수량·단가·금액인 칸만 숫자로 되돌리고 표시 서식(`#,##0`)을 줍니다.
**머리글로 판단하는 이유**는 값만 보고 바꾸면 `"2026"` 같은 제목이 숫자가 되기
때문입니다. `—`(값 없음)은 0 으로 바꾸지 않습니다 — 바꾸면 «0원» 과 구별되지
않습니다(`money()` 와 같은 판단).

그 밖에:

- 열 너비를 내용에서 계산합니다. 한글·한자는 두 칸으로 세고(`len()` 만 쓰면 한글
  열이 절반 너비로 잡혀 잘립니다) 상·하한을 둡니다 — 상한이 없으면 긴 파일명
  하나가 열을 화면 밖으로 밀어냅니다
- 병합한 칸은 엑셀이 행 높이를 자동으로 늘려주지 않아 직접 줄 수를 셉니다
- 표 시트는 머리글 행을 고정합니다(`freeze_panes`) — 행 상한이 200건이라 스크롤됩니다
- 흑백 무채색 — 머리글 배경(연회색)·굵은 글씨·얇은 테두리로만 구분합니다
- escape 를 하지 않습니다. Markdown 은 `|` 가 표를 깨고 HTML 은 `<` 가 태그가
  되는데, XLSX 셀 값은 그대로 들어가고 브라우저에서 실행되지 않아 이 형식만의
  escape 규칙이 없습니다

## 짚어 둔 것 하나 — 본문 미리보기(`GET /deliverables/preview/content`)는 XLSX 를 그대로 못 받습니다

`DeliverableContentResponse.body` 가 `str` 필드입니다. XLSX 는 바이너리라 이
응답에 담을 수 없습니다 — 만들기(`POST`)와는 다른 제약입니다.

그래서 `SUPPORTED_DELIVERABLE_FORMATS` 와 별도로 상수를 하나 더 뒀습니다:

```python
# 본문을 문자열로 돌려주는 형식. DeliverableContentResponse.body 가 str 이라
# XLSX(바이너리) 는 여기 없다.
TEXT_PREVIEW_FORMATS = ("MD", "HTML")
```

`preview_content()` 의 형식 검사를 `SUPPORTED_DELIVERABLE_FORMATS` 대신 이걸로
바꿨습니다. 결과: XLSX 는 **만들기는 되지만 본문 미리보기는 501** 입니다. 화면에서
XLSX 를 만들기 형식으로는 고를 수 있게 하고, 미리보기 「보기 방식」 버튼에는 넣지
않았습니다(`DeliverablesView.jsx`) — 골라도 501 만 받으므로.

파일로 XLSX 내용을 보려면: 먼저 만들고(`POST /deliverables`) `GET
.../deliverables/{id}/file` 로 받으면 됩니다. 다운로드 경로는 `FORMAT_FILE_TYPES`
를 그대로 쓰므로 고칠 것이 없었습니다.

## 화면

`DeliverablesView.jsx` 두 곳입니다.

- 형식 선택 목록에서 XLSX 의 `ready` 를 `false` → `true` 로 바꿨습니다.
  `PDF` 는 그대로 `false` 입니다(이 PR 대상 아님)
- 미리보기 아래 설명이 *"XLSX·PDF 는 아직 만들 수 없어 미리보기에도 없습니다"* 였는데
  **XLSX 는 이제 만들 수 있으므로 틀린 문장**이 됐습니다. "만들 수는 있지만 표 파일을
  브라우저가 그리지 못해 여기서는 HTML·MD 로만 본다"로 바꿨습니다

## 검증

**`git apply --check` 로만 검증했습니다.** 샌드박스에 `pydantic`·`openpyxl` 이
없어(외부 네트워크 막힘) pytest 를 여기서 돌릴 수 없습니다. `python3 -m py_compile`
로 문법을 확인하고, **openpyxl API 를 흉내낸 스텁으로 `to_xlsx()` 를 실제로 돌려**
어떤 시트에 어떤 값이 들어가는지 확인했습니다(시트 6개 생성, 빈 절에도 문장,
금액이 문자열 `"6,000,000"` 이 아니라 정수 `6000000` 으로 들어감).

**⚠ 이 레포에는 CI 가 없습니다**(`.github/workflows` 없음). 그래서 pytest 는 누군가
손으로 돌려야 확인됩니다. 아래 두 개를 봐 주세요.

- `test_deliverable_generate.py::test_unsupported_format_is_not_ready_not_invalid`
  — XLSX 를 뺐습니다(이제 501 은 PDF 만)
- `test_deliverable_html.py` — MD·HTML 문자열 경로가 그대로인지(회귀)

**`docker compose exec api pytest` 는 안 됩니다.** `pytest` 가
`requirements-dev.txt` 에만 있고 `Dockerfile` 은 `requirements.txt` 만 이미지에
넣습니다(16행). 컨테이너 안에는 `requirements-dev.txt` 자체가 없습니다.

이 테스트들은 **모델도 DB 도 쓰지 않습니다**(리포지토리는 `MagicMock`, 파일 저장만
임시폴더에 실제로 합니다). import 를 따라가면 필요한 것은 `pytest`·`pydantic`·
`pydantic-settings`·`sqlalchemy`·`fastapi`·`openpyxl`·`pgvector` 뿐이고
`torch`·`paddleocr` 는 필요 없습니다. 그래서 가벼운 venv 로 돌릴 수 있습니다:

```
cd backend
python -m venv .venv-test
.venv-test\Scripts\Activate.ps1
pip install pytest pydantic pydantic-settings sqlalchemy fastapi openpyxl pgvector
python -m pytest tests/test_deliverable_generate.py tests/test_deliverable_html.py -q
```

`python -m pytest` 여야 합니다 — `tests/__init__.py` 도 `pytest.ini` 도 없어서
`pytest` 만 치면 `from app...` 이 안 잡힙니다. 그리고 `Settings` 에 기본값 없는
필수 항목이 여러 개라 `backend/.env` 가 있어야 import 가 됩니다.

## 이 PR 에 없는 것

- **PDF** — 한글 폰트가 붙어 이미지가 더 커지므로 XLSX 와 같은 PR 에서 하지
  않기로 했습니다(2026-08-25 판단, `관리/현재상태.md`)
- **XLSX 렌더러 단위 테스트** — `deliverable_xlsx.py` 를 새로 만들었는데
  `test_deliverable_xlsx.py` 는 이 PR 에 없습니다. 필요하면 `test_deliverable_html.py`
  와 같은 구조로 다음에 추가합니다.


---

# 덧붙임 — HTML 산출물 디자인 (`54-html-report-design.patch`)

**적용 순서**: `52` → `53` → `54`

## 왜 HTML 만 꾸미나 (2026-08-26 판단)

형식마다 **쓰임이 다릅니다.**

| 형식 | 쓰임 | 그래서 |
|---|---|---|
| `XLSX` · `MD` | 받아서 **더 가공한다** | 무채색·최소 서식 유지. 셀 배경·글꼴을 넣으면 붙여 쓸 때 방해가 된다 |
| `HTML` (나중의 `PDF`) | **그대로 보내고 그대로 인쇄한다** | 표지·절 번호·머리글 대비 같은 짜임을 갖는다 |

`XLSX`·`MD` 는 이 패치에서 **모양을 건드리지 않았습니다.**

## 색은 여전히 쓰지 않습니다

검정(`#1b1b1b`)·회색 몇 단계·흰색뿐입니다. 강조는 **면·굵기·선·여백**으로만
만듭니다 — 흑백 복사와 인쇄에서 흐려지지 않는 것이 기준입니다.

| 요소 | 무엇 |
|---|---|
| 표지 띠 | 검정 배경 + 흰 제목. 기간·만든 시각은 회색 작은 글씨로 그 안에 |
| 절 머리 | `01` 번호 뱃지(검정 면) + 제목 + 남는 폭을 채우는 가는 선 |
| 표 | 머리글 행 검정 배경·흰 글씨, 본문 행 교차 음영(`#fafafa`), 아래쪽 가는 선 |
| 숫자 칸 | **오른쪽 정렬 + 자릿수 폭 고정**(`tabular-nums`) — 금액이 나란히 읽힌다 |
| 빈 절·개요 | 왼쪽 굵은 선 + 연회색 바탕의 문장 상자 |
| 꼬리말 | 가는 선 위에 제목·기간·만든 시각 (인쇄해서 나눠줄 때 근거가 남는다) |

## 숫자 칸을 어떻게 아는가 — 상수를 한 곳으로 모았습니다

`deliverable_markdown.NUMERIC_HEADERS`(`수량`·`단가`·`금액`·`건수`) 하나를
**HTML 과 XLSX 가 함께 봅니다.** HTML 은 오른쪽 정렬에, XLSX 는 문자열을 숫자로
되돌리는 데 씁니다. 패치 53 에서 XLSX 안에 따로 두었던 것을 옮겼습니다 — 두 곳에
있으면 한쪽만 고쳐서 «엑셀에서는 합계가 되는데 HTML 에서는 왼쪽에 붙는» 어긋남이
생깁니다.

**값이 아니라 머리글로 판단하는 이유**: 값만 보고 «숫자처럼 생겼으면 숫자» 로
다루면 `"2026"` 같은 제목이 숫자가 됩니다.

## 인쇄 규칙을 넣었습니다 (PDF 준비이지 PDF 구현은 아닙니다)

`@media print` 에 `@page` 여백, 절·행이 페이지 경계에서 잘리지 않게 하는
`page-break-inside: avoid`, 표 머리글이 다음 장에도 따라가는
`thead { display: table-header-group }` 를 넣었습니다. 브라우저 «인쇄 →
PDF 로 저장» 이 지금 바로 쓸 만해지고, 나중에 서버 PDF 를 붙일 때도 이 스타일을
그대로 씁니다. **`PDF` 형식 자체는 여전히 501 입니다.**

`-webkit-print-color-adjust: exact` 를 켰습니다 — 없으면 브라우저가 인쇄할 때
검정 배경 띠를 빼버려서 표지와 표 머리글이 사라집니다.

CSS 변수(`--foo`)는 쓰지 않았습니다. 나중에 붙일 PDF 변환기가 오래된 엔진이면
변수를 이해하지 못해 색이 전부 빠집니다 — 값을 그대로 적어 두면 그런 일이 없습니다.

## 마크업을 바꿀 때의 함정 (주석에 적어 뒀습니다)

`test_deliverable_html.py` 가 **`<h2>{절 제목}</h2>` 와 `<table>` 을 속성 없이
그대로** 찾습니다(두 형식이 같은 절을 담는지, 빈 표를 그리지 않는지 검사합니다).
그래서 절 번호는 `<h2>` **밖에** 두고 `<table>` 에는 class 를 붙이지 않았습니다.
꾸미는 것은 바깥 요소와 CSS 선택자로 합니다.

## 검증

기존 `test_deliverable_html.py` 의 단정 전부와 새 마크업 검사를 합쳐 **29개를
스텁 환경에서 실제로 돌려 통과**시켰습니다(`pydantic` 이 없어 `app.schemas.deliverable`
만 스텁으로 대체하고 `deliverable_markdown`·`deliverable_html` 은 실제 파일을
불렀습니다). 헤드리스 브라우저로 렌더링해 배치도 확인했습니다.

**CI 가 없으므로** `test_deliverable_html.py` 는 손으로 돌려 확인해 주세요 — 방법은
위 「검증」 절의 venv 명령을 참고하세요.


---

# 덧붙임 2 — XLSX 단위 테스트 (`55-deliverable-xlsx-tests.patch`)

**적용 순서**: `52`~`54` 가 **이미 main(`05e3bdc`)에 머지됨.** 이 패치는 그 위에
얹는 **테스트 파일 하나**다(`backend/tests/test_deliverable_xlsx.py`). 프로덕션
코드는 건드리지 않는다.

## 왜 지금

`deliverable_xlsx.py` 는 새로 만든 파일인데 테스트가 없었다(원래 PR 본문에도
「없는 것」으로 적었다). 이번에 겪은 **「XLSX 가 거의 빈 파일로 나오던」 버그**는
테스트가 있었으면 처음부터 잡혔다. 그래서 회귀 테스트로 남긴다.

## 검사하는 것 (12개)

만든 바이트를 **`openpyxl.load_workbook` 으로 되읽어** 셀을 본다 — 사용자가
엑셀에서 여는 것과 같은 관점이다.

| 무엇 | 왜 |
|---|---|
| `bytes` 이고 `PK`(zip) 로 시작 | MD·HTML(str)과 다른 계약 |
| **빈 절도 시트가 생긴다** | 자료 없는 주에 절이 사라지던 버그의 회귀 |
| 0건 절 시트에 머리글 + 없다는 문장 | 빈 시트로 두지 않는다 |
| 금액·단가가 **정수 + `#,##0`** | XLSX 를 고르는 이유가 «표 계산» |
| 숫자처럼 생긴 **항목명(`"2026"`)은 문자열로** | 값이 아니라 머리글로 판단 |
| 값 없음(`—`)은 **0 이 아니다** | «0원» 과 구별 |
| 요약 시트에 «담긴 내용»(시트별 건수) 표 | 첫 화면이 비어 보이지 않게 |
| 회의 안건은 결정사항 시트만 | build_document 규칙 |
| 시트 이름: 금지문자 치환·31자·중복 번호 | 엑셀 규칙 위반 시 파일이 깨진다 |

## 검증

샌드박스에 `openpyxl` 이 없어(외부 네트워크 막힘) pytest 를 거기서 돌리지
못했다. 대신 **가장 까다로운 단정(절 순서·회의 안건 절·금지문자 변환·
`NUMERIC_HEADERS`·`EMPTY`)을 실제 `build_document` 를 불러 확인**하고,
나머지는 `to_xlsx` 출력 구조를 스텁으로 확인했다. `py_compile` 통과.

**로컬 venv 에서 돌려 확인해 주세요:**

```
cd C:\dev\Tesqra\Tasqra\backend
python -m pytest tests/test_deliverable_xlsx.py -q
```

`383 passed` 였던 전체 스위트가 이 파일만큼(12개) 늘어야 한다.
