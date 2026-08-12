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

# int | None 같은 표기를 파이썬 3.9 에서도 쓸 수 있게 한다.
# 팀원 환경의 파이썬 버전이 서로 다를 수 있어서 넣었다.
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

TIMEOUT_SEC = 120
MAX_RETRY = 6

# 429 재시도 최소 대기(초). 한도가 낮으면 run_eval 이 이 값을 올린다.
# 3 RPM 이면 20초를 기다려야 창이 비므로 2초씩 물러나는 것은 의미가 없다.
RETRY_MIN_SEC = 2.0


def set_retry_floor(seconds: float) -> None:
    global RETRY_MIN_SEC
    RETRY_MIN_SEC = max(2.0, seconds)


class RateLimit:
    """분당 요청 수(RPM)와 분당 토큰 수(TPM)를 지킨다.

    Voyage 는 결제 수단을 등록하지 않으면 3 RPM · 10K TPM 으로 묶인다.
    Gemini 무료 등급도 비슷하게 낮다. 배치를 크게 잡으면 429 만 받고 끝난다.

    Spring 비교: Resilience4j 의 RateLimiter 를 손으로 만든 것이다.
    최근 60초 안의 (보낸 시각, 토큰 수) 를 들고 있다가 한도를 넘으면
    가장 오래된 기록이 창을 벗어날 때까지 잔다 — 슬라이딩 윈도우다.

    이 대기는 검색 품질에 영향을 주지 않는다. 임베딩은 텍스트마다 독립이라
    배치 크기를 바꿔도 같은 청크는 같은 벡터가 나온다. 망가지는 것은
    속도 지표뿐이고 그것은 애초에 로컬과 비교할 수 없는 값이다.
    """

    # 한국어는 토크나이저에 따라 글자당 토큰 수가 크게 다르다.
    # 처음에는 넉넉히 잡고, 응답이 실제 토큰 수를 주면 그 값으로 고친다.
    INITIAL_TOKENS_PER_CHAR = 1.6

    def __init__(self, rpm: int = 0, tpm: int = 0) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self.tokens_per_char = self.INITIAL_TOKENS_PER_CHAR
        self.waited_sec = 0.0
        self._events: list[tuple[float, int]] = []
        self._calibrated = False

    def active(self) -> bool:
        return bool(self.rpm or self.tpm)

    def estimate(self, texts: list[str]) -> int:
        return int(sum(len(t) for t in texts) * self.tokens_per_char) + 1

    def batch_chars(self) -> int:
        """한 배치가 넘지 말아야 할 글자 수.

        TPM 의 절반으로 잡는다. 한 배치가 분당 한도를 다 쓰면 매 요청마다
        60초를 기다려야 해서 전체가 훨씬 느려진다.
        """
        if not self.tpm:
            return 10 ** 9
        return max(200, int(self.tpm * 0.5 / self.tokens_per_char))

    def _prune(self, now: float) -> None:
        self._events = [(t, n) for t, n in self._events if now - t < 60.0]

    def wait(self, est_tokens: int) -> None:
        while True:
            now = time.monotonic()
            self._prune(now)
            need = []
            oldest = self._events[0][0] if self._events else now
            if self.rpm and len(self._events) >= self.rpm:
                need.append(60.0 - (now - oldest))
            if self.tpm and self._events:
                used = sum(n for _, n in self._events)
                if used + est_tokens > self.tpm:
                    need.append(60.0 - (now - oldest))
            if not need:
                return
            nap = min(65.0, max(0.5, max(need)))
            used = sum(n for _, n in self._events)
            print(f"    한도 대기 {nap:.0f}초 "
                  f"(최근 60초: 요청 {len(self._events)}회 · 토큰 {used:,})",
                  file=sys.stderr)
            time.sleep(nap)
            self.waited_sec += nap

    def record(self, chars: int, est_tokens: int, actual: int | None) -> None:
        self._events.append((time.monotonic(), actual or est_tokens))
        if actual and chars > 0:
            measured = actual / chars
            # 과소평가하면 429 가 나므로 10% 여유를 둔다.
            self.tokens_per_char = measured * 1.1
            if not self._calibrated:
                print(f"    토큰 실측 — 글자당 {measured:.2f} 토큰 "
                      f"(추정은 {self.INITIAL_TOKENS_PER_CHAR} 였다)",
                      file=sys.stderr)
                self._calibrated = True


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
            # Retry-After 를 주면 그것을 따른다. 없으면 지수 후퇴하되
            # 한도가 낮을 때는 창이 비는 시간(RETRY_MIN_SEC)보다 짧게
            # 기다리는 것이 의미가 없으므로 그 값을 밑으로 둔다.
            hinted = exc.headers.get("Retry-After") if exc.headers else None
            try:
                wait = float(hinted) if hinted else 0.0
            except ValueError:
                wait = 0.0
            wait = max(wait, RETRY_MIN_SEC, 2 ** attempt)
            print(f"    {exc.code} 응답. {wait:.0f}초 후 재시도 "
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

    def __init__(self, model: str, dim: int,
                 limit: "RateLimit | None" = None) -> None:
        self.model = model
        self.dim = dim
        self.limit = limit or RateLimit()
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
        i = 0
        while i < len(texts):
            # 개수 한도와 글자 한도 둘 다 지켜 한 배치를 만든다.
            # 글자 한도는 TPM 에서 나온다. 첫 텍스트는 혼자라도 넣는다 —
            # 그 하나가 한도를 넘으면 어차피 쪼갤 수 없다.
            cap = self.limit.batch_chars()
            part = [texts[i]]
            chars = len(texts[i])
            while len(part) < size and i + len(part) < len(texts):
                nxt = texts[i + len(part)]
                if chars + len(nxt) > cap:
                    break
                part.append(nxt)
                chars += len(nxt)

            est = self.limit.estimate(part)
            if self.limit.active():
                self.limit.wait(est)

            before = self.total_tokens
            out.extend(self._encode_batch(part, input_role))
            self.limit.record(chars, est, (self.total_tokens - before) or None)

            self.api_calls += 1
            i += len(part)
            if show_progress_bar:
                print(f"\r    {self.provider} {i}/{len(texts)} "
                      f"(요청 {self.api_calls}회)", end="", file=sys.stderr)
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

    def __init__(self, model: str, dim: int,
                 limit: "RateLimit | None" = None) -> None:
        super().__init__(model, dim, limit)
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


def build(provider: str, model: str, dim: int,
          limit: RateLimit | None = None) -> ApiEncoder:
    if provider not in PROVIDERS:
        raise ApiError(f"모르는 제공자: {provider}. "
                       f"쓸 수 있는 것 — {', '.join(PROVIDERS)}")
    return PROVIDERS[provider](model, dim, limit)
