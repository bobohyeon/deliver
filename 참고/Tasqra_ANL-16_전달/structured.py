# =============================================================================
# 이 파일의 책임: LLM 응답을 Pydantic 스키마로 검증하고, 형식을 어기면 무엇이
#   틀렸는지 알려주며 재시도한다 (기능명세서 ANL-16 구조화 출력 검증·재시도).
#   분석기마다 같은 파싱·재시도 코드를 반복하지 않게 한 곳에 모은다.
# 다른 파일과의 관계: summary_analyzer.py · category_analyzer.py 가 지금
#   json.loads 를 직접 하고 실패하면 원문을 그대로 쓴다. 그 부분을 이 함수로
#   바꾸면 실패가 조용히 넘어가지 않는다. AIClientProtocol 만 알고 구현체
#   (openai_client · local_client · fake_client)는 모른다.
#   에러코드는 core/error_codes.py 의 AI_INVALID_RESPONSE 를 쓴다 (이미 있다).
# Spring 비교: @Valid + MethodArgumentNotValidException 처리에 재시도를 붙인 것.
#   Pydantic 모델이 DTO 이고 ValidationError 가 그 예외에 해당한다.
#   Spring Retry 의 @Retryable 을 손으로 만든 셈이다.
#
# 왜 필요한가
#   지금은 형식이 깨지면 조용히 넘어간다. summary_analyzer 가 이렇게 한다.
#
#       try:
#           parsed = json.loads(ai_result.text)
#           summary_text = parsed["summary"]
#       except (json.JSONDecodeError, KeyError):
#           summary_text = ai_result.text      # 원문을 그대로 요약으로 쓴다
#
#   요약은 그래도 쓸 만하지만 금액·항목 추출은 그럴 수 없다. 필드가 없으면
#   그냥 없는 것이고, 실패한 사실이 아무데도 남지 않아 나중에 원인을 못 찾는다.
#   ANL-16 판정 기준이 "모델이 형식을 어기면 검출해 재시도하고 실패가 로그에
#   남는다" 다.
#
# 학습보다 이것을 먼저 하는 이유
#   형식 준수를 파인튜닝으로 가르치는 것은 확률을 높이는 일이다. 스키마 검증과
#   재시도는 틀린 것을 걸러내는 일이다. 후자가 확실하고 훨씬 싸다.
#   제공자가 스키마 강제를 지원하면 애초에 형식이 깨지지 않는다 — json_schema()
#   가 그 스키마를 만들어 준다.
# =============================================================================

import asyncio
import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.client_protocol import AIClientProtocol, AIResult
from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# 재시도 횟수. 3회를 넘기면 형식 문제가 아니라 프롬프트나 모델 문제다.
MAX_ATTEMPTS = 3


def json_schema(model: type[BaseModel], name: str | None = None) -> dict[str, Any]:
    """제공자에게 넘길 JSON 스키마를 만든다.

    OpenAI 의 response_format={"type": "json_schema", ...} 와
    Ollama 의 format 파라미터가 받는 형태다.

    이것을 쓰면 형식이 깨지지 않는다. 학습으로 형식을 가르치는 것과 달리
    디코딩 단계에서 막기 때문이다. 다만 제공자가 지원해야 한다.
    지원 여부를 모를 때는 프롬프트에 스키마를 적어 넣는 것으로 대신한다
    (schema_instruction 참고).
    """
    schema = model.model_json_schema()
    # OpenAI 의 strict 모드는 추가 필드를 허용하지 않아야 한다.
    schema["additionalProperties"] = False
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name or model.__name__,
            "strict": True,
            "schema": schema,
        },
    }


def schema_instruction(model: type[BaseModel]) -> str:
    """프롬프트에 붙일 스키마 지시문.

    제공자가 스키마 강제를 지원하지 않을 때 쓴다. 강제보다 약하지만
    아무 지시가 없는 것보다 낫다.
    """
    return (
        "\n\n아래 JSON 스키마를 정확히 지켜서 JSON 객체 하나만 출력한다.\n"
        "설명·머리말·코드블록 표시를 붙이지 않는다.\n"
        "스키마에 없는 필드를 만들지 않는다.\n"
        "값을 모르면 null 로 두고 임의로 채우지 않는다.\n\n"
        f"{json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)}"
    )


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


def extract_json(text: str) -> str:
    """모델이 JSON 앞뒤에 붙이는 것을 떼어낸다.

    실제로 자주 보는 형태 셋이다.
      ```json { ... } ```      코드블록으로 감싼다
      다음과 같습니다: { ... }  머리말을 붙인다
      { ... } 이상입니다        꼬리말을 붙인다
    """
    s = _FENCE.sub("", text.strip())
    # 가장 바깥 중괄호 짝을 찾는다. 문자열 안의 중괄호는 세지 않는다.
    start = s.find("{")
    if start < 0:
        return s
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(s[start:], start=start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return s[start:]


def _why(exc: Exception) -> str:
    """무엇이 틀렸는지 모델에게 돌려줄 문장으로 바꾼다.

    "형식이 틀렸다" 만 알려주면 같은 실수를 반복한다. 어느 필드가 왜
    틀렸는지 적어 줘야 고친다.
    """
    if isinstance(exc, json.JSONDecodeError):
        return f"JSON 으로 읽을 수 없다 ({exc.msg}, {exc.lineno}행 {exc.colno}칸)."
    if isinstance(exc, ValidationError):
        lines = []
        for e in exc.errors()[:8]:
            where = ".".join(str(x) for x in e["loc"]) or "(최상위)"
            lines.append(f"  {where} — {e['msg']}")
        return "스키마에 맞지 않는다.\n" + "\n".join(lines)
    return str(exc)


async def generate_structured(
    client: AIClientProtocol,
    prompt: str,
    model: type[T],
    *,
    max_attempts: int = MAX_ATTEMPTS,
    timeout: float | None = None,
    log_context: str = "",
) -> tuple[T, AIResult]:
    """스키마를 지킨 응답을 받을 때까지 재시도한다.

    돌려주는 것은 (검증된 모델, 마지막 AIResult) 다. AIResult 를 함께 주는
    이유는 analyses 테이블에 토큰·지연시간·모델명을 남겨야 하기 때문이다.

    실패하면 BusinessError(AI_INVALID_RESPONSE) 를 던진다. 조용히 넘어가지
    않는 것이 ANL-16 의 요점이다.

    재시도할 때마다 무엇이 틀렸는지 프롬프트에 붙인다. 그냥 다시 부르면
    같은 답이 온다 — 특히 temperature=0 인 지금 설정에서는 그렇다.
    """
    timeout = timeout if timeout is not None else settings.AI_TIMEOUT_SECONDS
    tag = f"[{log_context}] " if log_context else ""

    # 스키마 지시문은 첫 호출부터 붙인다. 제공자가 스키마 강제를 지원하면
    # 이 지시문 없이도 되지만, 지원 여부를 여기서 알 수 없다.
    current = prompt + schema_instruction(model)
    last_error: Exception | None = None
    last_result: AIResult | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            ai_result = await asyncio.wait_for(
                client.generate_with_meta(current), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise BusinessError(ErrorCode.AI_TIMEOUT) from exc
        except Exception as exc:
            raise BusinessError(ErrorCode.AI_PROVIDER_ERROR) from exc

        last_result = ai_result
        try:
            parsed = model.model_validate_json(extract_json(ai_result.text))
            if attempt > 1:
                logger.info("%s구조화 출력 %d회째에 성공 · model=%s",
                            tag, attempt, ai_result.model_name)
            return parsed, ai_result
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            reason = _why(exc)
            # 실패를 반드시 남긴다. ANL-16 판정 기준이다.
            logger.warning(
                "%s구조화 출력 실패 %d/%d · model=%s · schema=%s\n%s\n"
                "받은 응답 앞 300자: %s",
                tag, attempt, max_attempts, ai_result.model_name,
                model.__name__, reason, ai_result.text[:300])

            if attempt == max_attempts:
                break
            current = (
                f"{prompt}{schema_instruction(model)}\n\n"
                f"직전 응답이 형식을 어겼다. {reason}\n"
                f"스키마를 다시 확인하고 JSON 객체 하나만 출력한다."
            )

    logger.error("%s구조화 출력 %d회 모두 실패 · schema=%s · model=%s",
                 tag, max_attempts, model.__name__,
                 last_result.model_name if last_result else "?")
    raise BusinessError(ErrorCode.AI_INVALID_RESPONSE) from last_error
