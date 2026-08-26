# PR 본문 — 산출물 XLSX 출력 (복사해 붙이는 용도)

**패치 파일**: `52-deliverable-xlsx-format.patch`
**베이스**: `origin/main` = `7ff17a9` (2026-08-25 PR #67 머지 시점)

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

- 표가 있는 절은 시트 하나씩(문서 / 완료한 태스크 / 결정사항 / 일정·기한 / 금액)
- 표가 없는 절(개요)은 "안내" 시트에 문단으로 모읍니다 — 절마다 시트를 만들면
  표 없는 절이 늘 때 빈 시트가 쌓입니다
- 시트 이름은 엑셀 규칙(31자 제한, `\ / ? * [ ] :` 금지)에 맞춰 자릅니다
- 흑백 무채색 — 강조는 헤더 행 배경(회색)과 굵은 글씨 하나로만 합니다
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

`DeliverablesView.jsx` 의 형식 선택 목록에서 XLSX 의 `ready` 를 `false` → `true` 로
바꿨습니다. `PDF` 는 그대로 `false` 입니다(이 PR 대상 아님).

## 검증

**`git apply --check` 로만 검증했습니다.** 샌드박스에 `pydantic`·`openpyxl` 이
없어(외부 네트워크 막힘) pytest 를 여기서 돌릴 수 없습니다. `python3 -m
py_compile` 로 문법만 확인했습니다. **팀 CI 에서 pytest 통과를 확인해 주세요** —
특히 `test_deliverable_generate.py::test_unsupported_format_is_not_ready_not_invalid`
(XLSX 를 뺐습니다, 이제 501 은 PDF 만)와 `test_deliverable_html.py` 의 회귀
(MD·HTML 문자열 경로 유지).

## 이 PR 에 없는 것

- **PDF** — 한글 폰트가 붙어 이미지가 더 커지므로 XLSX 와 같은 PR 에서 하지
  않기로 했습니다(2026-08-25 판단, `관리/현재상태.md`)
- **XLSX 렌더러 단위 테스트** — `deliverable_xlsx.py` 를 새로 만들었는데
  `test_deliverable_xlsx.py` 는 이 PR 에 없습니다. 필요하면 `test_deliverable_html.py`
  와 같은 구조로 다음에 추가합니다.
