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

import math
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
        """2차원 리스트에 shape 과 나눗셈만 붙인 것. 정규화 검사에 필요하다."""

        @property
        def shape(self):
            return (len(self), len(self[0]) if self else 0)

        def __truediv__(self, norms):
            return _Arr([[v / norms[i][0] for v in row]
                         for i, row in enumerate(self)])

    def _norm(x, axis=None, keepdims=False):
        if axis == 1:
            out = [[math.sqrt(sum(v * v for v in row))] for row in x]
            return _Norms(out)
        return math.sqrt(sum(v * v for v in x))

    class _Norms(list):
        def __eq__(self, other):        # norms[norms == 0] = 1.0 을 받아낸다
            return _Mask([row[0] == other for row in self])

        def __setitem__(self, key, value):
            if isinstance(key, _Mask):
                for i, hit in enumerate(key):
                    if hit:
                        self[i][0] = value
                return
            list.__setitem__(self, key, value)

    class _Mask(list):
        pass

    stub.ndarray = _Arr          # 타입 힌트가 참조한다
    stub.asarray = lambda x, dtype=None: _Arr(x)
    stub.linalg = types.SimpleNamespace(norm=_norm)
    sys.modules["numpy"] = stub
    print("  (numpy 가 없어 흉내로 대신한다. 정규화까지 검사할 수 있다)\n")


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
out = enc.encode([f"청크{i}" for i in range(70)], input_role="document")
check("70개를 32씩 3번에 나눈다", len(CAPTURED) == 3, len(CAPTURED))
check("마지막 배치는 6개다",
      len(CAPTURED[-1]["payload"]["requests"]) == 6,
      len(CAPTURED[-1]["payload"]["requests"]))
check("결과 개수가 입력과 같다", len(out) == 70, len(out))

head("정규화 — Gemini 의 잘린 벡터 때문에 반드시 필요하다")
# 잘린 벡터를 흉내낸다. 길이가 1이 아닌 값을 응답으로 준다.
def unnormalized(url, payload, headers):
    CAPTURED.append({"url": url, "payload": payload, "headers": headers})
    n = len(payload["requests"])
    dim = payload["requests"][0]["outputDimensionality"]
    # 각 성분이 0.5 인 dim 차원 벡터. 길이는 0.5*sqrt(dim) 으로 1이 아니다.
    return {"embeddings": [{"values": [0.5] * dim} for _ in range(n)]}

ae._post = unnormalized
CAPTURED.clear()
enc = ae.build("gemini", "gemini-embedding-001", 1024)
raw_len = 0.5 * math.sqrt(1024)          # = 16.0
vecs = enc.encode(["문서1", "문서2"], input_role="document")
lens = [math.sqrt(sum(v * v for v in row)) for row in vecs]
check(f"제공자가 준 벡터는 길이가 1이 아니다 ({raw_len:.1f})",
      abs(raw_len - 16.0) < 1e-9, raw_len)
check("어댑터를 지나면 길이가 1이 된다",
      all(abs(l - 1.0) < 1e-6 for l in lens), lens)
check("차원은 그대로 1024 다", len(vecs[0]) == 1024, len(vecs[0]))
ae._post = spy

head("차원이 안 맞으면 잡아낸다")
def wrong_dim(url, payload, headers):
    return {"data": [{"embedding": [0.1] * 768, "index": 0}],
            "usage": {"total_tokens": 5}}
ae._post = wrong_dim
enc = ae.build("voyage", "voyage-4", 1024)
try:
    enc.encode(["문서1"], input_role="document")
    check("요청한 차원과 다르면 막는다", False, "예외가 나지 않았다")
except ae.ApiError as exc:
    check("요청한 차원과 다르면 막는다",
          "1024" in str(exc) and "768" in str(exc), str(exc))
ae._post = spy

head("한도 대응 — Voyage 카드 미등록(3 RPM · 10K TPM)")
# 실제로 자지 않게 가로챈다. 얼마나 자려 했는지만 기록한다.
NAPS: list[float] = []
real_sleep = ae.time.sleep
ae.time.sleep = lambda s: NAPS.append(s)

lim = ae.RateLimit(rpm=3, tpm=10000)
check("한도가 켜졌다", lim.active())
# 기본 추정 1.1 토큰/글자 · TPM 의 절반 → 10000*0.5/1.1 = 4545 자
expected_cap = int(10000 * 0.5 / ae.RateLimit.INITIAL_TOKENS_PER_CHAR)
check(f"배치 글자 상한을 TPM 에서 계산한다 ({expected_cap}자)",
      lim.batch_chars() == expected_cap, lim.batch_chars())

def realistic(url, payload, headers):
    CAPTURED.append({"url": url, "payload": payload, "headers": headers})
    n = len(payload["input"])
    chars = sum(len(s) for s in payload["input"])
    return {"data": [{"embedding": [0.5] * 1024, "index": i} for i in range(n)],
            "usage": {"total_tokens": int(chars * 0.9)}}   # 글자당 0.9 토큰

ae._post = realistic
CAPTURED.clear()
NAPS.clear()
# 캐시를 끈다. 한도 로직만 보려는 것이고, 캐시가 켜져 있으면 두 번째
# 실행부터 API 를 안 불러 대기가 일어나지 않는다.
enc = ae.build("voyage", "voyage-4", 1024, lim, cache=False)
# 청크 하나가 400자라고 보고 30개 = 12,000자. 상한이 있으면 여러 번 쪼개진다.
# 텍스트를 서로 다르게 만든다 — 같으면 중복 제거가 하나로 줄여버린다.
enc.encode([f"청크{i:02d}" + "가" * 394 for i in range(30)],
           input_role="document")
sizes = [sum(len(s) for s in c["payload"]["input"]) for c in CAPTURED]
# 첫 배치는 추정치로 상한에 맞춘다. 응답이 실제 토큰을 알려주면(0.9)
# 추정이 보정되어 이후 배치 상한이 늘어난다. 의도한 동작이다.
check(f"첫 배치는 보수적 추정으로 {expected_cap}자 안에 든다",
      sizes[0] <= expected_cap, sizes[0])
check("보정 뒤 배치는 더 커진다 (상한이 늘어난다)",
      len(sizes) > 1 and max(sizes[1:]) > sizes[0], sizes)
check("어떤 배치도 분당 토큰 예산의 절반을 넘지 않는다",
      all(s * 0.9 <= 10000 * 0.55 for s in sizes),
      [round(s * 0.9) for s in sizes])
check("여러 번에 나눠 보낸다", len(CAPTURED) >= 3, len(CAPTURED))
check("보낸 텍스트 총 개수가 입력과 같다",
      sum(len(c["payload"]["input"]) for c in CAPTURED) == 30,
      sum(len(c["payload"]["input"]) for c in CAPTURED))
check("3 RPM 을 넘으면 기다린다", len(NAPS) > 0, NAPS)
check("기다린 시간이 60초 창에 맞다", all(0 < s <= 65 for s in NAPS), NAPS)
check("응답의 실제 토큰으로 추정을 고친다",
      abs(lim.tokens_per_char - 0.9 * 1.1) < 0.01, lim.tokens_per_char)
check("보정 후 배치 상한이 늘어난다", lim.batch_chars() > 3125, lim.batch_chars())

lim2 = ae.RateLimit()
check("한도를 안 주면 쪼개지 않는다",
      not lim2.active() and lim2.batch_chars() > 10 ** 8, lim2.batch_chars())

check("429 재시도 하한을 올릴 수 있다",
      (ae.set_retry_floor(22.0), ae.RETRY_MIN_SEC == 22.0)[1], ae.RETRY_MIN_SEC)
ae.set_retry_floor(2.0)
ae.time.sleep = real_sleep
ae._post = spy

head("캐시 — 같은 텍스트를 두 번 사지 않는다")
import shutil
ae.Cache.DIR = ROOT / ".embed_cache_test"
shutil.rmtree(ae.Cache.DIR, ignore_errors=True)

CAPTURED.clear()
enc = ae.build("voyage", "voyage-4", 1024)
v1 = enc.encode(["문서1", "문서2", "문서3"], input_role="document")
first_calls = len(CAPTURED)
check("처음에는 API 를 부른다", first_calls >= 1, first_calls)
check("캐시 파일이 만들어진다", enc.cache.path.exists(), enc.cache.path)

# 새 인코더 = 새 프로세스를 흉내낸다. 파일에서 읽어야 한다.
CAPTURED.clear()
enc2 = ae.build("voyage", "voyage-4", 1024)
v2 = enc2.encode(["문서1", "문서2", "문서3"], input_role="document")
check("두 번째에는 API 를 아예 안 부른다", len(CAPTURED) == 0, len(CAPTURED))
check("캐시 적중이 3건", enc2.cache.hit == 3, enc2.cache.hit)
check("값이 같다", [list(r) for r in v1] == [list(r) for r in v2])

# 역할이 다르면 다른 벡터다. 재사용하면 점수가 조용히 틀린다.
CAPTURED.clear()
enc2.encode(["문서1"], input_role="query")
check("역할이 다르면 캐시를 재사용하지 않는다", len(CAPTURED) == 1, len(CAPTURED))

# 차원이 다르면 다른 파일이다.
enc3 = ae.build("voyage", "voyage-4", 512)
check("차원이 다르면 캐시 파일이 다르다", enc3.cache.path != enc.cache.path,
      enc3.cache.path.name)

# 일부만 캐시에 있을 때
CAPTURED.clear()
enc4 = ae.build("voyage", "voyage-4", 1024)
v4 = enc4.encode(["문서1", "새문서", "문서3"], input_role="document")
sent = [t for c in CAPTURED for t in c["payload"]["input"]]
check("캐시에 없는 것만 산다", sent == ["새문서"], sent)
check("순서가 유지된다", len(v4) == 3 and list(v4[0]) == list(v1[0]),
      len(v4))

# 같은 텍스트가 중복으로 들어오면 한 번만 산다
CAPTURED.clear()
enc5 = ae.build("voyage", "voyage-4", 1024)
enc5.encode(["중복", "중복", "중복"], input_role="document")
sent = [t for c in CAPTURED for t in c["payload"]["input"]]
check("중복 텍스트는 한 번만 산다", sent == ["중복"], sent)

enc6 = ae.build("voyage", "voyage-4", 1024, cache=False)
CAPTURED.clear()
enc6.encode(["문서1"], input_role="document")
check("--no-cache 면 캐시를 안 쓴다", len(CAPTURED) == 1 and not enc6.cache.enabled)

shutil.rmtree(ae.Cache.DIR, ignore_errors=True)

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
