# `ANL-16` 구조화 출력 검증·재시도 — 쓰는 방법

```
파일      backend/app/analyzers/structured.py
기능      ANL-16 구조화 출력 검증 · 재시도 (P1)
판정 기준  모델이 형식을 어기면 검출해 재시도하고 실패가 로그에 남는다
```

---

## 지금 무엇이 문제인가

`summary_analyzer.py` 가 이렇게 한다.

```python
try:
    parsed = json.loads(ai_result.text)
    summary_text = parsed["summary"]
except (json.JSONDecodeError, KeyError):
    summary_text = ai_result.text      # 원문을 그대로 요약으로 쓴다
```

**형식이 깨지면 조용히 넘어간다.** 요약은 그래도 쓸 만하지만 금액·항목 추출은
그럴 수 없다. 필드가 없으면 그냥 없는 것이고, **실패한 사실이 아무데도 남지
않아 나중에 원인을 못 찾는다.**

---

## 세 줄로 바뀐다

**바꾸기 전**

```python
ai_result = await asyncio.wait_for(
    self._ai_client.generate_with_meta(prompt),
    timeout=settings.AI_TIMEOUT_SECONDS,
)
try:
    parsed = json.loads(ai_result.text)
    items = parsed["items"]
except (json.JSONDecodeError, KeyError):
    items = []          # 조용히 비어버린다
```

**바꾼 뒤**

```python
from app.analyzers.structured import generate_structured
from app.schemas.amount import AmountExtractionOut

parsed, ai_result = await generate_structured(
    self._ai_client, prompt, AmountExtractionOut, log_context="AMT-01",
)
items = parsed.items          # 타입이 보장된다
```

`asyncio.wait_for` · 타임아웃 · `AI_TIMEOUT` · `AI_PROVIDER_ERROR` 처리가
함수 안에 들어 있으므로 호출부에서 지운다.

---

## 무엇을 해 주는가

| | 내용 |
|---|---|
| **JSON 꺼내기** | 코드블록(` ```json `) · 머리말 · 꼬리말을 떼어낸다. 문자열 안의 중괄호를 세지 않는다 |
| **스키마 검증** | Pydantic 으로 필드·타입을 검사한다 |
| **재시도** | **무엇이 틀렸는지 프롬프트에 붙여서** 다시 부른다. 최대 3회 |
| **실패 기록** | 시도마다 `WARNING`, 최종 실패는 `ERROR`. 받은 응답 앞 300자를 남긴다 |
| **예외** | 다 실패하면 `BusinessError(AI_INVALID_RESPONSE)` — 조용히 넘어가지 않는다 |

### 재시도할 때 무엇을 붙이나

**그냥 다시 부르면 같은 답이 온다.** 지금 `temperature=0` 이라 더 그렇다.
그래서 무엇이 틀렸는지 적어 준다.

```
직전 응답이 형식을 어겼다. 스키마에 맞지 않는다.
  items.0.amount — Input should be a valid integer
  items.1.item_name — Field required
스키마를 다시 확인하고 JSON 객체 하나만 출력한다.
```

---

## 제공자가 스키마를 강제할 수 있으면 더 확실하다

`json_schema(model)` 이 제공자에게 넘길 스키마를 만들어 준다.

```python
from app.analyzers.structured import json_schema
from app.schemas.amount import AmountExtractionOut

json_schema(AmountExtractionOut)
# {"type": "json_schema",
#  "json_schema": {"name": "AmountExtractionOut", "strict": True, "schema": {...}}}
```

**이걸 쓰면 형식이 애초에 깨지지 않는다.** 학습으로 형식을 가르치는 것은
확률을 높이는 일이고, 스키마 강제는 **디코딩 단계에서 막는 것**이다.

지금 `local_client.py` · `openai_client.py` 는 이렇게 되어 있다.

```python
response_format={"type": "json_object"}    # JSON 이기만 하면 통과. 필드는 보장 안 됨
```

이것을 `json_schema(...)` 로 올리면 필드와 타입까지 강제된다.
**다만 `AIClientProtocol` 에 인자를 추가해야 하므로 세현님과 정하고 한다.**
지금은 프롬프트에 스키마를 적어 넣는 방식으로 동작하고, 강제로 올리면
재시도가 거의 일어나지 않게 된다.

| 방식 | 형식 보장 | 손대는 곳 |
|---|---|---|
| 프롬프트에 스키마 지시 | 약하다 | **없다 — 지금 이대로 된다** |
| `json_object` | JSON 이기만 | 이미 되어 있다 |
| **`json_schema`** | **필드·타입까지** | `AIClientProtocol` 에 인자 추가 |
| 파인튜닝 | 확률만 높인다 | 학습 데이터 수백~수천 건 |

---

## 학습보다 이것을 먼저 하는 이유

**금액 쪽에서 LLM 이 할 일은 "문서에 적힌 값을 찾아서 JSON 으로 내놓기" 뿐이다.**

| 기능 | 작업명 | 누가 하나 | 상태 |
|---|---|---|---|
| `AMT-01` | 금액 항목 추출 | **LLM** | 미착수 |
| `AMT-12` | 스키마 검증 · 정규화 | **코드** | **완료** |
| `AMT-14` | 비용 산출 엔진 | **코드** | **완료** (단위테스트 포함) |

`AMT-14` 판정 기준이 **"LLM 은 계산에 관여하지 않는다"** 다. 수량 × 단가와
항목 합계는 코드가 한다. `AMT-12` 가 `"1,200만원"` 을 원 단위 정수로 바꾼다.

**그래서 학습으로 고칠 것이 남는지 먼저 확인해야 한다.**

| 증상 | 해결 |
|---|---|
| JSON 형식을 어긴다 | **`ANL-16`.** 학습 불필요 |
| 금액 계산이 틀린다 | **`AMT-14`.** 코드가 계산한다. 학습 무관 |
| 금액 항목을 못 찾아낸다 | **학습이 도움될 수 있다** |

**셋째만 학습 대상이다.** 그리고 요구사항 `COR-05` 가 "학습은 출력 형식
안정화에만 쓴다. 지식은 학습시키지 않는다" 이므로 방침 확인이 필요하다.

---

## 어댑터를 나눌지 합칠지 — 이 함수가 판단을 미룰 수 있게 한다

| | 방식 | 대가 |
|---|---|---|
| **A** | 학습 안 함. 원본 + 스키마 강제 + 재시도 | **반나절** |
| B | 어댑터 하나로 통합 학습 | **잘 되는 요약·분류가 같이 변한다** |
| C | 어댑터 둘 스위칭 | Ollama 제약 · 메모리 2배 |

**B 가 위험하다.** 어댑터를 나누는 이유가 원본 성능 보존인데, 하나로 합치면
그 이유가 사라진다. 요약·분류가 이미 괜찮다면 건드리지 않는 것이 맞다.

**A 를 먼저 해보고 남는 문제만 학습 대상으로 잡으면 된다.**

---

## 적용 대상

| 분석기 | 기능 | 지금 | 적용 후 |
|---|---|---|---|
| `summary_analyzer` | `ANL-01` | 실패 시 원문을 요약으로 씀 | **코드를 고치지 않는다** — 명세서가 그렇게 정했다 |
| `category_analyzer` | `ANL-02` | 후보 밖 값 보정 | 후보를 `Literal` 로 두면 검증으로 잡힌다 |
| `amount_analyzer` | `AMT-01` | **미구현** | **처음부터 이걸로 만든다** |
| `extract_analyzer` | `ANL-03` · `14` · `15` | **미구현** | **처음부터 이걸로 만든다** |

**`ANL-01` 요약은 건드리지 않는다.** 기능명세서에 "코드를 고치지 않는다" 로
적혀 있다. 요약은 형식이 깨져도 원문이 쓸 만하다.

**미구현 분석기 둘은 이걸로 만드는 것이 이득이 크다.** 액션·결정·일정을 한
번에 배열로 받아야 하고(`ANL-03`), 배열은 필드 누락이 훨씬 잘 생긴다.

---

## 검증한 것

`extract_json` 을 10건으로 확인했다.

```
그냥 JSON · 코드블록 · 코드블록(json 없이) · 머리말 · 꼬리말
중첩 객체 · 문자열 안의 중괄호 · 이스케이프된 따옴표
머리말+코드블록+꼬리말 · JSON 이 아예 없으면 원문 그대로
```

**문자열 안의 중괄호를 세지 않는 것이 중요하다.** 금액 항목명에 괄호가
들어가는 일이 흔하다 (`"소프트웨어 라이선스(3년)"`).
