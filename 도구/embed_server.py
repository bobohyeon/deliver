# =============================================================================
# 이 파일의 책임: sentence-transformers 모델을 호스트에 한 번 올리고, OpenAI 호환
#   POST /v1/embeddings 로 임베딩을 돌려준다. Tasqra 의 LocalEmbeddingClient 가
#   그 규격을 그대로 부르므로 백엔드 코드를 고치지 않고 실제 모델을 붙일 수 있다.
#
#   왜 이렇게 하는가
#     · 컨테이너에 sentence-transformers(+torch) 를 넣으면 api·worker 가 각각
#       약 2.3GB(BGE-M3 float32)를 올려 합계 4.6GB 다. 개발 노트북 가용 메모리가
#       4.8GB 여서 들어가지 않는다.
#     · Ollama 는 설치돼 있지 않고, BGE-m3-ko 의 GGUF 는 양자화·풀링이 미검증이다.
#     · 호스트에 한 번만 올리면 약 2.3GB 로 끝나고, 컨테이너 이미지도 그대로다.
#
#   새로 설치할 것이 없다 — C:\dev\embed-test\.venv 에 sentence-transformers 가
#   이미 있고, HTTP 서버는 표준 라이브러리(http.server)를 쓴다.
#
# 다른 파일과의 관계
#   · Tasqra backend/app/embedding/local_client.py 가 이 서버를 부른다.
#     openai SDK 가 {base_url}/embeddings 로 POST 하므로 base_url 을 /v1 로 끝낸다.
#   · 도구/ir_eval.py 와 같은 모델·같은 max_seq(1024)를 쓴다. 그래야 검색 결과가
#     우리가 측정한 조건과 같은 조건에서 나온 것이 된다.
#
# Spring 비교: 무거운 모델을 별도 프로세스로 떼어내고 HTTP 로 부르는 것.
#   사이드카(sidecar) 패턴이나 별도 추론 서비스와 같은 구조다.
#
# ⚠ 반드시 0.0.0.0 에 바인딩한다
#   컨테이너는 host.docker.internal 로 호스트를 본다. 127.0.0.1 에만 바인딩하면
#   컨테이너에서 닿지 않는다. 처음 실행할 때 Windows 방화벽이 물어보면 허용한다.
#
# ⚠ 이 서버는 개발용이다
#   인증이 없고 요청을 한 번에 하나씩 처리한다. 외부에 노출하지 않는다.
#
# 사용법
#   cd C:\dev\embed-test
#   .venv\Scripts\activate
#   python embed_server.py
#
#   다른 모델로:
#   python embed_server.py --model "C:\Users\bbb\Desktop\임베딩 모델\embedding-finetuned"
#
#   확인:
#   curl.exe -s -X POST http://localhost:8900/v1/embeddings -H "Content-Type: application/json" -d "{\"model\":\"x\",\"input\":\"대금 지급\"}"
# =============================================================================

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MODEL = "dragonkue/BGE-m3-ko"
DEFAULT_PORT = 8900
# ir_eval.py 와 같은 값. 다르게 두면 우리가 측정한 정확도와 조건이 달라진다.
DEFAULT_MAX_SEQ = 1024

_model = None
_model_name = ""


def model_dimension(model) -> int | None:
    """출력 차원을 얻는다.

    sentence-transformers 가 get_sentence_embedding_dimension 을
    get_embedding_dimension 으로 이름을 바꿨다. 판에 따라 둘 중 하나만 있으므로
    새 이름을 먼저 찾는다. 옛 이름만 쓰면 FutureWarning 이 뜬다.
    """
    for name in ("get_embedding_dimension", "get_sentence_embedding_dimension"):
        fn = getattr(model, name, None)
        if callable(fn):
            return int(fn())
    return None
# CPU 에서 여러 요청이 동시에 encode 하면 서로 느려지고 메모리도 튄다.
# 한 번에 하나만 처리한다 — 개발용이므로 그것으로 충분하다.
_lock = threading.Lock()
_stats = {"requests": 0, "texts": 0, "seconds": 0.0}


def load_model(path: str, max_seq: int, device: str):
    global _model, _model_name
    from sentence_transformers import SentenceTransformer

    print(f"모델을 올린다: {path}")
    print("  처음이면 내려받는 데 몇 분 걸린다. 약 2.3GB 를 메모리에 올린다.")
    started = time.perf_counter()
    model = SentenceTransformer(path, device=device)
    print(f"  max_seq_length 기본: {model.max_seq_length} -> 설정: {max_seq}")
    model.max_seq_length = max_seq
    _model = model
    _model_name = path
    print(f"  준비 완료 ({time.perf_counter() - started:.1f}초)")
    return model


def embed(texts: list[str], batch_size: int) -> list[list[float]]:
    with _lock:
        vectors = _model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            # 정규화한다. pgvector 인덱스가 코사인 거리(vector_cosine_ops)이고
            # 가짜 임베더도 단위 벡터를 주므로 성질을 같게 맞춘다.
            # 코사인은 크기를 무시하므로 순위에는 영향이 없다.
            normalize_embeddings=True,
        )
    return [[float(x) for x in row] for row in vectors]


class Handler(BaseHTTPRequestHandler):
    # 기본 로그는 한 줄이 너무 길어서 우리가 직접 찍는다.
    def log_message(self, fmt, *args):  # noqa: A003
        pass

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/"):
            self._send(200, {
                "status": "ok",
                "model": _model_name,
                "dimension": model_dimension(_model) if _model else None,
                "max_seq_length": _model.max_seq_length if _model else None,
                "stats": dict(_stats),
            })
            return
        # OpenAI SDK 가 모델 목록을 물어볼 수 있다.
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list", "data": [
                {"id": _model_name, "object": "model", "owned_by": "local"},
            ]})
            return
        self._send(404, {"error": {"message": f"없는 경로: {self.path}"}})

    def do_POST(self) -> None:  # noqa: N802
        # openai SDK 는 base_url 뒤에 /embeddings 를 붙인다. base_url 이 /v1 로
        # 끝나므로 경로는 /v1/embeddings 가 된다. 혹시 다르게 와도 받아 준다.
        if not self.path.rstrip("/").endswith("/embeddings"):
            self._send(404, {"error": {"message": f"없는 경로: {self.path}"}})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"error": {"message": f"본문을 읽을 수 없다: {exc}"}})
            return

        raw = payload.get("input")
        if raw is None:
            self._send(400, {"error": {"message": "input 이 없다"}})
            return
        texts = [raw] if isinstance(raw, str) else list(raw)
        if not texts:
            self._send(200, {"object": "list", "data": [], "model": _model_name})
            return
        if any(not isinstance(t, str) for t in texts):
            # OpenAI 는 토큰 id 배열도 받지만 우리는 문자열만 다룬다.
            self._send(400, {"error": {"message": "input 은 문자열이거나 문자열 배열이어야 한다"}})
            return

        started = time.perf_counter()
        try:
            vectors = embed(texts, self.server.batch_size)
        except Exception as exc:  # noqa: BLE001
            print(f"  [실패] {type(exc).__name__}: {exc}")
            self._send(500, {"error": {"message": f"임베딩 실패: {exc}"}})
            return
        elapsed = time.perf_counter() - started

        _stats["requests"] += 1
        _stats["texts"] += len(texts)
        _stats["seconds"] += elapsed
        print(f"  {len(texts):>4}건 · {elapsed * 1000:>7.0f}ms "
              f"· {elapsed / len(texts) * 1000:>6.0f}ms/건 "
              f"· 첫 텍스트: {texts[0][:40]!r}")

        # 요청에 온 model 이름을 그대로 되돌려 주지 않는다. 실제로 쓴 모델을
        # 돌려줘야 백엔드가 document_chunks.embedding_model 에 옳게 기록한다.
        self._send(200, {
            "object": "list",
            "model": _model_name,
            "data": [
                {"object": "embedding", "index": i, "embedding": v}
                for i, v in enumerate(vectors)
            ],
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        })


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenAI 호환 /v1/embeddings 개발 서버 (sentence-transformers)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="HuggingFace 이름 또는 로컬 폴더 경로")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0",
                        help="컨테이너에서 닿으려면 0.0.0.0 이어야 한다")
    parser.add_argument("--max-seq", type=int, default=DEFAULT_MAX_SEQ,
                        help="ir_eval.py 와 같은 값을 써야 조건이 맞는다")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    load_model(args.model, args.max_seq, args.device)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.batch_size = args.batch_size

    print()
    print("=" * 68)
    print(f"  듣는 곳   http://{args.host}:{args.port}")
    print(f"  컨테이너  http://host.docker.internal:{args.port}/v1")
    print(f"  모델      {_model_name}")
    print(f"  차원      {model_dimension(_model)}")
    print(f"  max_seq   {_model.max_seq_length}")
    print("=" * 68)
    print()
    print("  Tasqra 쪽 설정 (루트 .env)")
    print("    USE_FAKE_EMBEDDING=false")
    print(f"    EMBEDDING_BASE_URL=http://host.docker.internal:{args.port}/v1")
    print(f"    EMBEDDING_MODEL={_model_name}")
    print()
    print("  ⚠ 모델을 바꾸면 청킹을 다시 돌려야 한다. 검색이")
    print("    WHERE embedding_model = <현재 모델> 로 걸리므로, 옛 모델로 만든")
    print("    청크는 결과에 나오지 않는다 (서로 다른 벡터 공간을 섞지 않기 위한 조건).")
    print()
    print("  멈추려면 Ctrl+C")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        if _stats["requests"]:
            print(f"처리한 요청 {_stats['requests']}건 · 텍스트 {_stats['texts']}건 "
                  f"· 평균 {_stats['seconds'] / _stats['texts'] * 1000:.0f}ms/건")
        print("종료한다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
