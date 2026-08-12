# =============================================================================
# 이 파일의 책임: Voyage · OpenAI · Gemini 임베딩 API 를 SentenceTransformer 와
#   똑같이 생긴 객체로 감싼다. run_eval.py 의 채점 코드를 한 줄도 고치지 않고
#   API 모델을 같은 자로 비교할 수 있게 하는 것이 목적이다.
# 다른 파일과의 관계: run_eval.py 가 model_cfg["provider"] 를 보고 여기서
#   인코더를 만든다. provider 가 없거나 "local" 이면 기존 SentenceTransformer 를
#   그대로 쓴다. 새 패키지를 설치하지 않는다 — urllib 은 표준 라이브러리다.
# Spring 비교: 같은 인터페이스에 구현체를 바꿔 끼우는 것이라
#   Tasqra 의 app/ai/client_protocol.py + openai_client / local_client 구조와
#   똑같다. Java 로 치면 EmbeddingClient 인터페이스에 구현 클래스 셋을 두고
#   @Qualifier 로 고르는 것이다. 파이썬은 인터페이스 선언 없이
#   메서드 이름만 맞으면 되므로(덕 타이핑) 상속조차 필요 없다.
#
# 공정성 — 접두어 규칙과 같은 문제가 API 에도 있다
#   e5 계열이 "query: " / "passage: " 를 붙여야 제 성능이 나는 것처럼,
#   Voyage 는 input_type, Gemini 는 taskType 으로 질의와 문서를 구분해야 한다.
#   이걸 빼면 두 모델이 억울하게 진다. 그래서 encode() 에 input_role 을 받는다.
#   OpenAI 는 이 구분이 없다.
#
# 정규화를 우리가 직접 한다 — Gemini 때문에 반드시 필요하다
#   Gemini 는 outputDimensionality 로 차원을 줄일 때 뒤쪽을 그냥 잘라낸다.
#   자른 벡터는 길이가 1이 아니다. run_eval.py 는 내적을 코사인 유사도로
#   쓰므로 정규화하지 않으면 점수가 틀린다. 세 제공자 모두 여기서 정규화한다.
#   권장 차원(768 · 1536 · 3072)이 아닌 값을 쓸 때 특히 문제가 된다.
# =============================================================================
"""임베딩 API 어댑터. 실행에 API 키가 필요하다 (run_eval.py --api)."""

import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

TIMEOUT_SEC = 120
MAX_RETRY = 4


class ApiError(RuntimeError):
    pass


def _post(url: str, payload: dict, headers: dict) -> dict:
    """재시도까지 포함한 POST. 429 와 5xx 는 기다렸다 다시 던진다."""
    body = json.dumps(payload).encode("utf-8")
    last = None
    for attempt in range(MAX_RETRY):
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            last = f"HTTP {exc.code} — {detail}"
            # 400·401·403 은 다시 던져도 같은 답이 온다. 키나 요청이 잘못됐다.
            if exc.code in (400, 401, 403, 404):
                raise ApiError(last) from None
            wait = 2 ** attempt
            print(f"    {exc.code} 응답. {wait}초 후 재시도 "
                  f"({attempt + 1}/{MAX_RETRY})", file=sys.stderr)
            time.sleep(wait)
        except urllib.error.URLError as exc:
            last = f"연결 실패 — {exc.reason}"
            time.sleep(2 ** attempt)
    raise ApiError(last or "알 수 없는 실패")


def _l2(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


class ApiEncoder:
    """SentenceTransformer 와 같은 메서드 두 개만 맞춘다.

    run_eval.py 는 get_sentence_embedding_dimension() 과 encode() 만 쓰므로
    이 둘만 있으면 기존 채점 코드가 그대로 돈다.
    """

    provider = "api"
    env_key = ""
    # 한 번에 보낼 텍스트 개수. 제공자 제한보다 넉넉히 낮춰 잡았다.
    batch_limit = 64

    def __init__(self, model: str, dim: int) -> None:
        self.model = model
        self.dim = dim
        self.total_tokens = 0
        self.api_calls = 0
        self.key = os.environ.get(self.env_key, "").strip()
        if not self.key:
            raise ApiError(
                f"환경변수 {self.env_key} 가 비어 있다.\n"
                f"    PowerShell:  $env:{self.env_key}='키값'\n"
                f"    키를 코드나 커밋에 넣지 마라."
            )

    def get_sentence_embedding_dimension(self) -> int:
        return self.dim

    def _encode_batch(self, texts: list[str], role: str) -> list[list[float]]:
        raise NotImplementedError

    def encode(self, texts, input_role: str = "document",
               batch_size: int = 0, show_progress_bar: bool = False,
               normalize_embeddings: bool = True,
               convert_to_numpy: bool = True, **_ignored):
        """SentenceTransformer.encode 와 인자 이름을 맞췄다.

        normalize_embeddings 는 받아도 무시하고 항상 정규화한다.
        Gemini 의 잘린 벡터를 정규화하지 않으면 점수가 틀리기 때문이다.
        """
        texts = list(texts)
        size = min(batch_size or self.batch_limit, self.batch_limit)
        out: list[list[float]] = []
        for i in range(0, len(texts), size):
            part = texts[i:i + size]
            out.extend(self._encode_batch(part, input_role))
            self.api_calls += 1
            if show_progress_bar:
                done = min(i + size, len(texts))
                print(f"\r    {self.provider} {done}/{len(texts)}",
                      end="", file=sys.stderr)
        if show_progress_bar:
            print(file=sys.stderr)

        vecs = np.asarray(out, dtype=np.float32)
        if vecs.shape[1] != self.dim:
            raise ApiError(
                f"차원이 다르다. 요청 {self.dim} · 응답 {vecs.shape[1]}. "
                f"이 모델이 그 차원을 지원하지 않는 것이다"
            )
        return _l2(vecs)


class VoyageEncoder(ApiEncoder):
    """Voyage AI. input_type 으로 질의와 문서를 구분한다.

    voyage-4 계열은 2048 · 1024 · 512 · 256 을 지원하고 기본이 1024 라
    우리 컬럼을 바꾸지 않고 비교할 수 있다. 컨텍스트는 32K 다.
    """

    provider = "voyage"
    env_key = "VOYAGE_API_KEY"
    batch_limit = 64
    URL = "https://api.voyageai.com/v1/embeddings"

    def _encode_batch(self, texts, role):
        data = _post(self.URL, {
            "input": texts,
            "model": self.model,
            # query / document 를 안 주면 검색 성능이 떨어진다.
            "input_type": "query" if role == "query" else "document",
            "output_dimension": self.dim,
        }, {"Authorization": f"Bearer {self.key}"})
        self.total_tokens += (data.get("usage") or {}).get("total_tokens", 0)
        rows = sorted(data["data"], key=lambda d: d.get("index", 0))
        return [r["embedding"] for r in rows]


class OpenAIEncoder(ApiEncoder):
    """OpenAI. 질의와 문서 구분이 없어서 role 을 쓰지 않는다.

    text-embedding-3-large 는 dimensions 로 256~3072 를 임의 지정할 수 있다.
    text-embedding-3-small 은 512 · 1536 만 된다.
    """

    provider = "openai"
    env_key = "OPENAI_API_KEY"
    batch_limit = 64
    URL = "https://api.openai.com/v1/embeddings"

    def _encode_batch(self, texts, role):
        payload = {"input": texts, "model": self.model}
        # 기본 차원(3072)을 그대로 쓸 때는 dimensions 를 보내지 않는다.
        if self.dim:
            payload["dimensions"] = self.dim
        data = _post(self.URL, payload,
                     {"Authorization": f"Bearer {self.key}"})
        self.total_tokens += (data.get("usage") or {}).get("total_tokens", 0)
        rows = sorted(data["data"], key=lambda d: d.get("index", 0))
        return [r["embedding"] for r in rows]


class GeminiEncoder(ApiEncoder):
    """Google Gemini. taskType 으로 질의와 문서를 구분한다.

    주의 둘.
      1. outputDimensionality 는 128~3072 를 받지만 권장은 768 · 1536 · 3072 다.
         1024 를 주면 3072 벡터의 뒤를 잘라낸다. 잘린 벡터는 길이가 1이 아니라
         부모 클래스에서 반드시 정규화해야 한다.
      2. batchEmbedContents 는 요청마다 model 을 다시 적어야 한다.
    """

    provider = "gemini"
    env_key = "GEMINI_API_KEY"
    batch_limit = 32
    BASE = "https://generativelanguage.googleapis.com/v1beta"
    RECOMMENDED_DIMS = (768, 1536, 3072)

    def __init__(self, model: str, dim: int) -> None:
        super().__init__(model, dim)
        if dim not in self.RECOMMENDED_DIMS:
            print(f"    주의 — {dim} 은 Gemini 권장 차원이 아니다 "
                  f"(권장 {self.RECOMMENDED_DIMS}). 잘라낸 벡터를 "
                  f"직접 정규화해서 쓴다.", file=sys.stderr)

    def _encode_batch(self, texts, role):
        name = self.model if self.model.startswith("models/") \
            else f"models/{self.model}"
        task = "RETRIEVAL_QUERY" if role == "query" else "RETRIEVAL_DOCUMENT"
        url = f"{self.BASE}/{name}:batchEmbedContents?key={self.key}"
        data = _post(url, {
            "requests": [{
                "model": name,
                "content": {"parts": [{"text": t}]},
                "taskType": task,
                "outputDimensionality": self.dim,
            } for t in texts],
        }, {})
        # Gemini 는 토큰 사용량을 이 응답에 주지 않는다.
        return [e["values"] for e in data["embeddings"]]


PROVIDERS = {
    "voyage": VoyageEncoder,
    "openai": OpenAIEncoder,
    "gemini": GeminiEncoder,
}


def build(provider: str, model: str, dim: int) -> ApiEncoder:
    if provider not in PROVIDERS:
        raise ApiError(f"모르는 제공자: {provider}. "
                       f"쓸 수 있는 것 — {', '.join(PROVIDERS)}")
    return PROVIDERS[provider](model, dim)
