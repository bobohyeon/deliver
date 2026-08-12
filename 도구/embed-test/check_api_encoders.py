# =============================================================================
# 이 파일의 책임: api_encoders.py 가 각 제공자 문서 규격에 맞는 요청을 만드는지
#   확인한다. API 키도 네트워크도 쓰지 않는다. HTTP 호출을 가로채 요청 본문만
#   들여다보는 방식이다.
# 다른 파일과의 관계: api_encoders.py 를 검사한다. run_eval.py --self-test 와
#   check_queries.py 와 같은 성격이다 — 돈과 시간이 드는 실행 전에 값싸게
#   틀린 곳을 잡는다.
# Spring 비교: MockRestServiceServer 로 RestTemplate 요청을 가로채
#   본문을 검증하는 것과 같다. 실제 서버를 부르지 않는다.
#
# 왜 필요한가
#   Voyage 의 input_type 이나 Gemini 의 taskType 을 빼먹으면 에러가 나지 않는다.
#   그냥 점수가 낮게 나온다. e5 계열 접두어를 빼먹는 것과 같은 종류의 실수인데,
#   API 는 호출마다 돈이 들어서 다 돌린 뒤에 알아차리면 손해가 크다.
# =============================================================================
"""API 요청 본문 검사. 실행: python check_api_encoders.py"""

import os
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent


def install_numpy_stub() -> None:
    """numpy 가 없는 환경에서도 이 검사만은 돌아가게 한다.

    api_encoders 는 마지막 정규화에서만 numpy 를 쓴다. 이 검사는 요청 본문을
    보는 것이라 그 앞까지만 필요하다.
    """
    if "numpy" in sys.modules:
        return
    try:
        import numpy  # noqa: F401
        return
    except ImportError:
        pass
    stub = types.ModuleType("numpy")
    stub.float32 = "float32"

    class _Arr(list):
        @property
        def shape(self):
            return (len(self), len(self[0]) if self else 0)

    stub.ndarray = _Arr          # 타입 힌트가 참조한다
    stub.asarray = lambda x, dtype=None: _Arr(x)
    stub.linalg = types.SimpleNamespace(norm=lambda *a, **k: None)
    sys.modules["numpy"] = stub
    print("  (numpy 가 없어 흉내로 대신한다. 요청 본문 검사에는 지장 없다)\n")


install_numpy_stub()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VOYAGE_API_KEY", "검사용가짜키V")
os.environ.setdefault("OPENAI_API_KEY", "검사용가짜키O")
os.environ.setdefault("GEMINI_API_KEY", "검사용가짜키G")

import api_encoders as ae  # noqa: E402

CAPTURED: list[dict] = []
FAILED = 0


def spy(url, payload, headers):
    """_post 를 대신한다. 요청을 기록하고 그럴듯한 응답을 만들어 돌려준다."""
    CAPTURED.append({"url": url, "payload": payload, "headers": headers})
    if "requests" in payload:
        n = len(payload["requests"])
        dim = payload["requests"][0]["outputDimensionality"]
        return {"embeddings": [{"values": [0.5] * dim} for _ in range(n)]}
    n = len(payload["input"])
    dim = payload.get("output_dimension") or payload.get("dimensions") or 8
    return {"data": [{"embedding": [0.5] * dim, "index": i} for i in range(n)],
            "usage": {"total_tokens": 111}}


ae._post = spy


def check(label: str, cond: bool, got="") -> None:
    global FAILED
    mark = "통과" if cond else "실패"
    line = f"  {mark}  {label}"
    if not cond:
        FAILED += 1
        line += f"\n          실제 값: {got!r}"
    print(line)


def head(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


head("Voyage — input_type 으로 질의와 문서를 구분해야 한다")
CAPTURED.clear()
enc = ae.build("voyage", "voyage-4", 1024)
enc._encode_batch(["문서1", "문서2"], "document")
enc._encode_batch(["질의1"], "query")
doc, qry = CAPTURED[0]["payload"], CAPTURED[1]["payload"]
check("엔드포인트가 /v1/embeddings 다",
      CAPTURED[0]["url"] == "https://api.voyageai.com/v1/embeddings",
      CAPTURED[0]["url"])
check("Bearer 인증 헤더를 붙인다",
      CAPTURED[0]["headers"].get("Authorization", "").startswith("Bearer "),
      CAPTURED[0]["headers"])
check("문서는 input_type=document", doc.get("input_type") == "document",
      doc.get("input_type"))
check("질의는 input_type=query", qry.get("input_type") == "query",
      qry.get("input_type"))
check("output_dimension 을 1024 로 준다", doc.get("output_dimension") == 1024,
      doc.get("output_dimension"))
check("model 이름이 그대로 실린다", doc.get("model") == "voyage-4",
      doc.get("model"))
check("토큰 사용량을 누적한다", enc.total_tokens == 222, enc.total_tokens)

head("OpenAI — 질의·문서 구분이 없다. dimensions 로 차원을 줄인다")
CAPTURED.clear()
enc = ae.build("openai", "text-embedding-3-large", 1024)
enc._encode_batch(["문서1"], "document")
enc._encode_batch(["질의1"], "query")
doc, qry = CAPTURED[0]["payload"], CAPTURED[1]["payload"]
check("엔드포인트가 /v1/embeddings 다",
      CAPTURED[0]["url"] == "https://api.openai.com/v1/embeddings",
      CAPTURED[0]["url"])
check("dimensions 를 1024 로 준다", doc.get("dimensions") == 1024,
      doc.get("dimensions"))
check("역할이 달라도 본문이 같다 (구분이 없는 모델이다)",
      doc["model"] == qry["model"] and "input_type" not in doc)

head("Gemini — taskType 으로 구분. 요청마다 model 을 다시 적어야 한다")
CAPTURED.clear()
enc = ae.build("gemini", "gemini-embedding-001", 1024)
enc._encode_batch(["문서1", "문서2"], "document")
enc._encode_batch(["질의1"], "query")
doc, qry = CAPTURED[0]["payload"], CAPTURED[1]["payload"]
check("batchEmbedContents 를 부른다", ":batchEmbedContents" in CAPTURED[0]["url"],
      CAPTURED[0]["url"])
check("키를 쿼리스트링으로 보낸다", "key=" in CAPTURED[0]["url"])
check("model 에 models/ 접두어를 붙인다",
      doc["requests"][0]["model"] == "models/gemini-embedding-001",
      doc["requests"][0]["model"])
check("문서는 taskType=RETRIEVAL_DOCUMENT",
      doc["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT",
      doc["requests"][0]["taskType"])
check("질의는 taskType=RETRIEVAL_QUERY",
      qry["requests"][0]["taskType"] == "RETRIEVAL_QUERY",
      qry["requests"][0]["taskType"])
check("outputDimensionality 를 1024 로 준다",
      doc["requests"][0]["outputDimensionality"] == 1024,
      doc["requests"][0]["outputDimensionality"])
check("텍스트를 content.parts[].text 에 넣는다",
      doc["requests"][0]["content"]["parts"][0]["text"] == "문서1",
      doc["requests"][0]["content"])
check("배치 안에 두 건이 들어간다", len(doc["requests"]) == 2,
      len(doc["requests"]))

head("배치 쪼개기 — 제공자 한도를 넘기지 않는다")
CAPTURED.clear()
enc = ae.build("gemini", "gemini-embedding-001", 1024)   # batch_limit = 32
try:
    enc.encode([f"청크{i}" for i in range(70)], input_role="document")
except Exception:
    pass   # numpy 흉내라 마지막 정규화에서 멈춘다. 호출 횟수만 본다.
check("70개를 32씩 3번에 나눈다", len(CAPTURED) == 3, len(CAPTURED))
check("마지막 배치는 6개다",
      len(CAPTURED[-1]["payload"]["requests"]) == 6,
      len(CAPTURED[-1]["payload"]["requests"]))

head("실수 막기 — 키가 없을 때 · 모르는 제공자")
saved = os.environ.pop("VOYAGE_API_KEY")
try:
    ae.build("voyage", "voyage-4", 1024)
    check("키가 없으면 막는다", False, "예외가 나지 않았다")
except ae.ApiError as exc:
    check("키가 없으면 막고 설정법을 알려준다",
          "VOYAGE_API_KEY" in str(exc) and "PowerShell" in str(exc), str(exc))
os.environ["VOYAGE_API_KEY"] = saved
try:
    ae.build("cohere", "embed-v3", 1024)
    check("모르는 제공자를 막는다", False, "예외가 나지 않았다")
except ae.ApiError as exc:
    check("모르는 제공자를 막고 쓸 수 있는 것을 알려준다",
          "cohere" in str(exc) and "voyage" in str(exc), str(exc))

print(f"\n{'=' * 72}")
print("전부 통과" if not FAILED else f"실패 {FAILED}건 — 위를 고쳐라")
print(f"{'=' * 72}")
sys.exit(1 if FAILED else 0)
