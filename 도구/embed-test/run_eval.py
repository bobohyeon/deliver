# =============================================================================
# 이 파일의 책임: 임베딩 모델 여러 개를 같은 자로 비교한다. 청크를 임베딩해
#   질의로 검색하고 Recall@k · MRR · 속도 · 메모리 · 차원을 표로 뽑는다.
#   결과를 단어겹침 / 단어안겹침으로 나눠 보여준다.
# 다른 파일과의 관계: make_chunks.py 의 chunks.csv 와 make_queries.py 로 만든
#   queries.csv 를 읽는다. 여기서 정한 모델과 차원이 리비전의 pgvector
#   컬럼(vector(N))을 결정하므로, 이 결과가 나오기 전에 마이그레이션을 쓰지 않는다.
#   확정 후 이 평가 코드가 기능명세서 RAG-10(검색 품질 측정)이 된다.
# Spring 비교: JMH 벤치마크에 가깝다. 다만 성능이 아니라 검색 품질을 잰다.
#   여러 구현을 같은 입력으로 돌려 표로 비교하는 구조는 같다.
#
# 접두어 규칙이 비교의 공정성을 정한다
#   e5 계열은 질의에 "query: ", 문서에 "passage: " 를 붙여야 제 성능이 난다.
#   bge-m3 계열은 접두어가 없다. 규칙을 섞으면 한쪽이 억울하게 진다.
#   모델을 추가할 때는 반드시 모델 카드에서 접두어 규칙을 확인해라.
#
# 판단 기준
#   no_overlap 의 Recall@5 를 먼저 본다. 단어가 겹치는 질의는 기존 ILIKE
#   검색으로도 찾히므로 임베딩을 쓸 근거가 되지 않는다.
# =============================================================================

# int | None 같은 표기를 파이썬 3.9 에서도 쓸 수 있게 한다.
from __future__ import annotations

import argparse
import csv
import gc
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
CHUNKS = ROOT / "chunks.csv"
QUERIES = ROOT / "queries.csv"
RESULT = ROOT / "results.csv"
DETAIL = ROOT / "results_detail.csv"

# ── 비교할 모델 ──────────────────────────────────────────────────────────────
# query_prefix / passage_prefix 는 모델 카드에 적힌 규칙을 그대로 넣는다.
# 모르면 빈 문자열로 두지 말고 카드를 확인해라. 성능 차이가 크다.
MODELS = [
    {
        "name": "BAAI/bge-m3",
        "query_prefix": "",
        "passage_prefix": "",
        "note": "기준선. 다국어. 한국어 특화가 이걸 못 이기면 의미 없다",
    },
    {
        "name": "nlpai-lab/KURE-v1",
        "query_prefix": "",
        "passage_prefix": "",
        "note": "고려대. 한국어 검색 특화. bge-m3 기반이라 접두어 없음",
    },
    {
        "name": "dragonkue/multilingual-e5-small-ko-v2",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "note": "384차원. CPU 현실 후보. e5 계열이라 접두어 필수",
    },
    # ── 차원과 모델 크기를 분리하기 위해 추가한 두 개 ────────────────────
    # 1차 시험은 384 와 1024 두 점만 재서 "차원이 원인인지 모델 크기가
    # 원인인지" 를 나눌 수 없었다. e5 원본 계열의 base(768)·large(1024)를
    # 넣으면 같은 학습 조건 안에서 차원만 다른 비교가 된다.
    #   e5-base 대 e5-large   = 순수 차원 비교 (같은 계열)
    #   e5-large 대 KURE-v1   = 한국어 특화 효과 (같은 차원 1024)
    {
        "name": "intfloat/multilingual-e5-base",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "note": "768차원. 384와 1024 사이를 채운다. 12층",
    },
    {
        "name": "intfloat/multilingual-e5-large",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "note": "1024차원. e5-base 와 같은 계열이라 차원만 다른 비교가 된다",
    },
]

# ── API 모델 ────────────────────────────────────────────────────────────────
# 기본 실행에서 제외한다. --api 를 줄 때만 돈다. 이유 둘.
#   1. 문서 전량이 외부로 나간다. 실수로 돌아가면 안 된다.
#   2. 키가 없으면 실패한다.
#
# dim 을 1024 로 맞춘 것은 로컬 실측(vector(1024) 결정)과 같은 자로 재기
# 위한 것이다. 차원을 다르게 주면 저장 용량이 달라져 비교가 흐려진다.
#
# 접두어는 비운다. 질의·문서 구분을 API 파라미터로 하기 때문이다
# (Voyage input_type · Gemini taskType). api_encoders.py 참고.
API_MODELS = [
    {
        "provider": "voyage",
        "name": "voyage-4",
        "dim": 1024,
        "query_prefix": "", "passage_prefix": "",
        "note": "1024 기본 · 32K 컨텍스트 · 첫 2억 토큰 무료. 2라운드 첫 후보",
    },
    {
        "provider": "voyage",
        "name": "voyage-4-lite",
        "dim": 1024,
        "query_prefix": "", "passage_prefix": "",
        "note": "같은 차원에 더 싸다. 성능이 얼마나 떨어지는지 본다",
    },
    {
        "provider": "openai",
        "name": "text-embedding-3-large",
        "dim": 1024,
        "query_prefix": "", "passage_prefix": "",
        "note": "3072 을 1024 로 줄여서 쓴다. 질의·문서 구분이 없는 모델",
    },
    {
        "provider": "gemini",
        "name": "gemini-embedding-001",
        "dim": 1024,
        "query_prefix": "", "passage_prefix": "",
        "note": "1024 는 Gemini 권장(768·1536·3072) 밖이라 잘린 벡터를 정규화한다",
    },
]

TOP_K = (1, 3, 5, 10)


def load_csv(path: pathlib.Path, required: list[str]) -> list[dict]:
    if not path.exists():
        print(f"파일이 없다: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"내용이 비어 있다: {path}", file=sys.stderr)
        sys.exit(1)
    missing = [c for c in required if c not in rows[0]]
    if missing:
        print(f"{path.name} 에 열이 없다: {missing}", file=sys.stderr)
        sys.exit(1)
    return rows


def load_queries(valid_ids: set[int]) -> list[dict]:
    rows = load_csv(QUERIES, ["query", "gold_chunk_ids", "kind"])
    out = []
    for i, row in enumerate(rows, start=2):   # 2행부터 (1행은 머리글)
        text = (row["query"] or "").strip()
        if not text:
            continue
        if "예시" in (row.get("note") or ""):
            continue

        gold = set()
        for part in (row["gold_chunk_ids"] or "").replace(" ", "").split(","):
            if not part:
                continue
            if not part.isdigit():
                print(f"  [{QUERIES.name} {i}행] 정답이 숫자가 아니다: {part}")
                continue
            cid = int(part)
            if cid not in valid_ids:
                print(f"  [{QUERIES.name} {i}행] 없는 청크 번호: {cid}")
                continue
            gold.add(cid)

        if not gold:
            print(f"  [{QUERIES.name} {i}행] 정답이 없어 건너뛴다: {text[:30]}")
            continue

        kind = (row["kind"] or "").strip() or "unknown"
        out.append({"query": text, "gold": gold, "kind": kind})

    if not out:
        print("\n채점할 질의가 없다. queries.csv 를 채워라.", file=sys.stderr)
        print("  query · gold_chunk_ids · kind 세 칸이 필요하다.", file=sys.stderr)
        sys.exit(1)
    return out


def rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return float("nan")


class _FakeModel:
    """자체 점검용 가짜 인코더. 글자 빈도로 벡터를 만든다.

    모델을 내려받기 전에 채점 로직과 CSV 처리가 맞는지 확인하는 용도다.
    글자가 겹치면 유사해지므로 overlap 질의는 잘 맞고 no_overlap 은 잘
    틀린다. 그 경향이 표에 나타나면 하네스가 제대로 도는 것이다.
    """

    def __init__(self, name: str, device: str | None = None) -> None:
        self.name = name

    def get_sentence_embedding_dimension(self) -> int:
        return 64

    def encode(self, texts, **kwargs):
        out = []
        for text in texts:
            vec = np.zeros(64)
            for ch in text:
                vec[ord(ch) % 64] += 1.0
            norm = np.linalg.norm(vec) or 1.0
            out.append(vec / norm)
        return np.array(out)


def evaluate(model_cfg: dict, chunks: list[dict], queries: list[dict],
             batch_size: int, self_test: bool = False,
             rpm: int = 0, tpm: int = 0,
             cache: bool = True) -> tuple[dict, list[dict]]:
    provider = model_cfg.get("provider", "local")
    is_api = provider != "local"

    name = model_cfg["name"]
    print(f"\n{'=' * 66}")
    print(f"{name}" + (f"   [{provider} API]" if is_api else ""))
    print(f"  {model_cfg['note']}")
    print(f"{'=' * 66}")

    before = rss_mb()
    t0 = time.perf_counter()
    if is_api:
        import api_encoders
        limit = api_encoders.RateLimit(rpm, tpm)
        if limit.active():
            # 3 RPM 이면 창이 비는 데 20초가 걸린다. 2초씩 물러나도 소용없다.
            api_encoders.set_retry_floor(60.0 / rpm + 2 if rpm else 20.0)
            print(f"  한도 적용 — {rpm or '제한없음'} RPM · "
                  f"{tpm or '제한없음'} TPM · 배치 상한 {limit.batch_chars():,}자")
        model = api_encoders.build(provider, name, model_cfg["dim"], limit, cache)
    elif self_test:
        model = _FakeModel(name, device="cpu")
    else:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(name, device="cpu")
    load_sec = time.perf_counter() - t0
    dim = model.get_sentence_embedding_dimension()
    print(f"  {'준비' if is_api else '적재'} {load_sec:.1f}초 · 차원 {dim}")

    def run(texts: list[str], role: str, progress: bool):
        """로컬과 API 를 같은 호출로 묶는다.

        input_role 은 API 전용이다. 로컬 모델은 접두어(query: / passage: )로
        같은 구분을 하므로 넘기지 않는다.
        """
        kwargs = dict(batch_size=batch_size, normalize_embeddings=True,
                      show_progress_bar=progress, convert_to_numpy=True)
        if is_api:
            kwargs["input_role"] = role
        return model.encode(texts, **kwargs)

    passages = [model_cfg["passage_prefix"] + c["text"] for c in chunks]
    t0 = time.perf_counter()
    doc_vecs = run(passages, "document", True)
    encode_sec = time.perf_counter() - t0
    peak = rss_mb()

    q_texts = [model_cfg["query_prefix"] + q["query"] for q in queries]
    q_vecs = run(q_texts, "query", False)

    api_calls = getattr(model, "api_calls", 0)
    api_tokens = getattr(model, "total_tokens", 0)
    if is_api:
        print(f"  API 호출 {api_calls}회"
              + (f" · 토큰 {api_tokens:,}" if api_tokens
                 else " · 토큰 사용량을 응답에 주지 않는 제공자다"))

    # 정규화했으므로 내적이 곧 코사인 유사도다.
    sims = q_vecs @ doc_vecs.T
    ids = np.array([int(c["chunk_id"]) for c in chunks])

    hits = {k: {"overlap": 0, "no_overlap": 0, "all": 0} for k in TOP_K}
    counts = {"overlap": 0, "no_overlap": 0, "all": 0}
    rr_sum = {"overlap": 0.0, "no_overlap": 0.0, "all": 0.0}
    detail = []

    for qi, query in enumerate(queries):
        order = np.argsort(-sims[qi])
        ranked = ids[order]
        kind = query["kind"]

        groups = ["all"]
        if kind in counts and kind != "all":
            groups.append(kind)
        for g in groups:
            counts[g] += 1

        rank = None
        for pos, cid in enumerate(ranked[:max(TOP_K)], start=1):
            if cid in query["gold"]:
                rank = pos
                break

        for k in TOP_K:
            if rank is not None and rank <= k:
                for g in groups:
                    hits[k][g] += 1

        if rank is not None:
            for g in groups:
                rr_sum[g] += 1.0 / rank

        detail.append({
            "model": name,
            "query": query["query"],
            "kind": kind,
            "gold": ",".join(str(x) for x in sorted(query["gold"])),
            "top5": ",".join(str(x) for x in ranked[:5]),
            "rank": rank if rank else "",
            "top1_score": round(float(sims[qi][order[0]]), 4),
        })

    # model 을 지우기 전에 필요한 값을 다 꺼내 둔다.
    # 여기서 안 꺼내고 summary 안에서 model 을 참조하면 아래 del 때문에
    # UnboundLocalError 가 난다. 실제로 그렇게 터뜨렸다 — API 26회를 다 쓰고
    # 마지막 한 줄에서 죽어서 10분치 결과를 버렸다.
    limit_obj = getattr(model, "limit", None)
    wait_sec = round(limit_obj.waited_sec, 1) if is_api and limit_obj else ""

    del model, doc_vecs, q_vecs, sims
    gc.collect()

    summary = {
        "model": name,
        # 로컬과 API 를 섞어 놓고 속도·메모리를 같은 열에서 비교하면 안 된다.
        # 로컬은 CPU 시간이고 API 는 네트워크 왕복 시간이다.
        "runner": provider if is_api else "로컬CPU",
        "dim": dim,
        "load_sec": round(load_sec, 1),
        "encode_sec": round(encode_sec, 1),
        "sec_per_100_chunks": round(encode_sec / max(len(chunks), 1) * 100, 2),
        # API 는 모델이 우리 메모리에 없으므로 잴 것이 없다.
        "mem_mb": "" if is_api else (round(peak - before, 0) if peak == peak else ""),
        "api_calls": api_calls if is_api else "",
        "api_tokens": api_tokens if is_api else "",
        # 한도 때문에 잔 시간. encode_sec 안에 포함돼 있다.
        "wait_sec": wait_sec,
    }
    for group in ("all", "overlap", "no_overlap"):
        n = counts[group]
        for k in TOP_K:
            summary[f"R@{k}_{group}"] = round(hits[k][group] / n, 3) if n else ""
        summary[f"MRR_{group}"] = round(rr_sum[group] / n, 3) if n else ""
        summary[f"n_{group}"] = n

    return summary, detail


def api_check(only: list[str] | None) -> int:
    """API 키·모델명·차원을 짧은 문장 하나로 확인한다.

    본 실행은 청크 127개와 질의 73개를 보낸다. 키가 틀렸거나 모델명이 틀렸으면
    그걸 다 보낸 뒤에 실패한다. 그 전에 값싸게 확인하려고 만들었다.
    문서를 보내지 않으므로 데이터 유출 걱정도 없다.
    """
    import api_encoders

    probe = "입찰 참가 자격을 확인한다"
    targets = API_MODELS
    if only:
        targets = [m for m in API_MODELS
                   if any(p.lower() in m["name"].lower() or
                          p.lower() == m["provider"] for p in only)]
        if not targets:
            print("--only 에 맞는 API 모델이 없다. --list 로 이름을 본다.",
                  file=sys.stderr)
            return 1

    print("=" * 70)
    print("API 예비 점검 — 짧은 문장 하나만 보낸다 (문서는 나가지 않는다)")
    print(f'  보낼 문장: "{probe}"')
    print("=" * 70)

    bad = 0
    for cfg in targets:
        label = f"{cfg['provider']:8} {cfg['name']:26}"
        try:
            enc = api_encoders.build(cfg["provider"], cfg["name"], cfg["dim"])
        except api_encoders.ApiError as exc:
            print(f"  건너뜀  {label} 키가 없다")
            print(f"           {exc}".replace("\n", "\n           "))
            continue

        t0 = time.perf_counter()
        try:
            vecs = enc.encode([probe], input_role="query")
        except api_encoders.ApiError as exc:
            print(f"  실패    {label}")
            print(f"           {exc}")
            print(f"           {_explain(str(exc))}")
            bad += 1
            continue
        except Exception as exc:                      # noqa: BLE001
            print(f"  실패    {label} {type(exc).__name__}: {exc}")
            bad += 1
            continue

        ms = int((time.perf_counter() - t0) * 1000)
        norm = float(np.linalg.norm(vecs[0]))
        tok = f" · 토큰 {enc.total_tokens}" if enc.total_tokens else ""
        print(f"  통과    {label} 차원 {vecs.shape[1]} · {ms}ms · "
              f"길이 {norm:.4f}{tok}")

    print("=" * 70)
    if bad:
        print(f"실패 {bad}건 — 위 설명을 보고 고친 뒤 다시 돌린다.")
    else:
        print("쓸 수 있는 모델은 위에 '통과' 로 나온 것이다.")
        print("본 실행:  python run_eval.py --api-only")
    print("=" * 70)
    return 1 if bad else 0


def _explain(msg: str) -> str:
    """제공자 오류를 무엇을 고쳐야 하는지로 바꿔준다."""
    if "HTTP 401" in msg or "HTTP 403" in msg:
        return "키가 틀렸거나 권한이 없다. 환경변수 값을 다시 확인한다."
    if "HTTP 404" in msg:
        return ("모델 이름이 틀렸다. 제공자 문서에서 현재 이름을 확인하고 "
                "API_MODELS 의 name 을 고친다.")
    if "HTTP 429" in msg:
        return "호출 한도에 걸렸다. 잠시 뒤에 다시 돌린다."
    if "output_dimension" in msg or "dimension" in msg.lower():
        return "이 모델이 그 차원을 지원하지 않는다. dim 을 고친다."
    if "연결 실패" in msg:
        return "네트워크가 막혀 있다. 회사망·프록시를 확인한다."
    return "제공자 문서에서 요청 형식이 바뀌었는지 확인한다."


def print_table(rows: list[dict]) -> None:
    print(f"\n\n{'=' * 78}")
    print("결과 — no_overlap 의 R@5 를 먼저 본다")
    print(f"{'=' * 78}\n")

    def show(title: str, cols: list[tuple[str, str]]) -> None:
        print(f"  {title}")
        head = "  | 모델 | " + " | ".join(c[0] for c in cols) + " |"
        print(head)
        print("  |---|" + "---|" * len(cols))
        for r in rows:
            cells = [str(r.get(c[1], "")) for c in cols]
            short = r["model"].split("/")[-1]
            print(f"  | {short} | " + " | ".join(cells) + " |")
        print()

    show("검색 품질", [
        ("실행", "runner"),
        ("차원", "dim"),
        ("R@1 안겹침", "R@1_no_overlap"),
        ("R@5 안겹침", "R@5_no_overlap"),
        ("MRR 안겹침", "MRR_no_overlap"),
        ("R@5 겹침", "R@5_overlap"),
        ("R@5 전체", "R@5_all"),
    ])
    show("실행 비용", [
        ("실행", "runner"),
        ("적재 초", "load_sec"),
        ("전체 임베딩 초", "encode_sec"),
        ("100청크당 초", "sec_per_100_chunks"),
        ("메모리 MB", "mem_mb"),
        ("API 호출", "api_calls"),
        ("API 토큰", "api_tokens"),
    ])
    if any(r.get("runner") != "로컬CPU" for r in rows):
        print("  주의 — 로컬의 초는 CPU 시간이고 API 의 초는 네트워크 왕복이다.")
        print("         같은 열에 있어도 같은 자가 아니다. 품질만 비교해라.\n")

    n = rows[0]
    print(f"  질의 수 — 전체 {n.get('n_all')} · 겹침 {n.get('n_overlap')} "
          f"· 안겹침 {n.get('n_no_overlap')}")
    if not n.get("n_no_overlap"):
        print("\n  주의 — kind=no_overlap 질의가 없다. 임베딩을 쓸 근거를 못 만든다.")
        print("         청크의 단어를 쓰지 않는 질의를 넣어라.")


def main() -> None:
    parser = argparse.ArgumentParser(description="임베딩 모델 비교")
    # 입출력 경로를 바꿀 수 있게 한다. 기본값은 지금까지와 같다.
    # 이것이 없으면 남의 평가셋을 돌릴 때 우리 기준선 queries.csv 를 덮어야 하고,
    # 그러면 73건 기준선이 사라진다. 평가셋마다 폴더를 따로 두게 하려는 인자다.
    parser.add_argument("--chunks", default=None,
                        help="chunks.csv 경로 (기본: 이 스크립트 옆)")
    parser.add_argument("--queries", default=None,
                        help="queries.csv 경로 (기본: 이 스크립트 옆)")
    parser.add_argument("--result", default=None,
                        help="요약 결과 csv 출력 경로")
    parser.add_argument("--detail", default=None,
                        help="질의별 상세 csv 출력 경로")
    parser.add_argument("--limit-chunks", type=int, default=0,
                        help="청크를 앞에서 N개만 쓴다 (CPU 에서 빠른 반복용)")
    parser.add_argument("--batch-size", type=int, default=8,
                        help="인코딩 배치 크기. 메모리가 부족하면 줄인다")
    parser.add_argument("--only", action="append",
                        help="모델 이름 일부로 골라 실행 (여러 번 가능)")
    parser.add_argument("--self-test", action="store_true",
                        help="모델을 내려받지 않고 가짜 인코더로 하네스만 점검한다")
    parser.add_argument("--api", action="store_true",
                        help="API 모델도 함께 잰다. 문서 전량이 외부로 나가고 "
                             "키가 필요하다 (VOYAGE_API_KEY 등)")
    parser.add_argument("--api-only", action="store_true",
                        help="API 모델만 잰다. 로컬은 건너뛴다")
    parser.add_argument("--list", action="store_true",
                        help="쓸 수 있는 모델 이름만 출력하고 끝낸다")
    parser.add_argument("--api-check", action="store_true",
                        help="API 키·모델명·차원만 확인한다. 짧은 문장 하나만 "
                             "보내므로 문서가 나가지 않고 돈도 거의 안 든다")
    parser.add_argument("--yes", action="store_true",
                        help="API 전송 확인 물음을 건너뛴다")
    parser.add_argument("--rpm", type=int, default=0,
                        help="분당 요청 수 한도. 넘지 않게 기다린다 "
                             "(Voyage 카드 미등록이면 3)")
    parser.add_argument("--tpm", type=int, default=0,
                        help="분당 토큰 수 한도. 배치를 자동으로 작게 쪼갠다 "
                             "(Voyage 카드 미등록이면 10000)")
    parser.add_argument("--no-cache", action="store_true",
                        help="받아온 벡터를 파일에 남기지 않는다. 기본은 남긴다 "
                             "— 한도가 낮아 같은 텍스트를 두 번 사면 아깝다")
    parser.add_argument("--voyage-free", action="store_true",
                        help="Voyage 카드 미등록 한도를 그대로 적용한다 "
                             "(--rpm 3 --tpm 10000 과 같다)")
    args = parser.parse_args()

    # 경로 전역을 덮어쓴다. 함수들이 호출 시점에 전역을 읽으므로 이걸로 충분하다.
    global CHUNKS, QUERIES, RESULT, DETAIL
    if args.chunks:
        CHUNKS = pathlib.Path(args.chunks)
    if args.queries:
        QUERIES = pathlib.Path(args.queries)
    if args.result:
        RESULT = pathlib.Path(args.result)
    if args.detail:
        DETAIL = pathlib.Path(args.detail)
    # 결과 경로를 따로 주지 않았는데 평가셋을 바꿔 돌리면 기준선 결과를 덮는다.
    # 조용히 덮지 않고 입력 옆에 쓴다.
    if args.queries and not args.result:
        RESULT = QUERIES.parent / "results.csv"
    if args.queries and not args.detail:
        DETAIL = QUERIES.parent / "results_detail.csv"

    if args.voyage_free:
        args.rpm, args.tpm = args.rpm or 3, args.tpm or 10000

    if args.list:
        print("로컬 모델 (기본 실행)")
        for m in MODELS:
            print(f"  {m['name']}")
        print("\nAPI 모델 (--api 또는 --api-only 일 때만)")
        for m in API_MODELS:
            print(f"  {m['name']:26} {m['provider']:8} dim={m['dim']:<5} "
                  f"{m['provider'].upper()}_API_KEY")
        print("\n--only 는 이름의 일부만 적으면 된다. 예 — --only e5-base")
        print("키를 넣었는지 먼저 확인하려면 --api-check 를 쓴다.")
        return

    if args.api_check:
        sys.exit(api_check(args.only))

    chunks = load_csv(CHUNKS, ["chunk_id", "doc", "text"])
    if args.limit_chunks:
        chunks = chunks[:args.limit_chunks]
    valid_ids = {int(c["chunk_id"]) for c in chunks}
    queries = load_queries(valid_ids)

    if args.self_test:
        targets = [{"name": "self-test/fake", "query_prefix": "",
                    "passage_prefix": "", "note": "가짜 인코더. 채점 로직 점검용"}]
    else:
        pool = []
        if not args.api_only:
            pool += MODELS
        if args.api or args.api_only:
            pool += API_MODELS
        targets = pool

        if args.only:
            targets = [m for m in pool
                       if any(p.lower() in m["name"].lower() for p in args.only)]
            if not targets:
                # 예전에 여기서 이름만 알려주지 않아 원인을 찾기 어려웠다.
                # 파일이 낡아서 그 모델이 아직 없는 경우가 대부분이다.
                print(f"--only {args.only} 에 맞는 모델이 없다.\n",
                      file=sys.stderr)
                print("이 파일에 있는 모델은 다음뿐이다.", file=sys.stderr)
                for m in pool:
                    print(f"  {m['name']}", file=sys.stderr)
                if not (args.api or args.api_only):
                    print("\nAPI 모델을 찾는다면 --api 를 붙여라.",
                          file=sys.stderr)
                print("\n찾는 모델이 목록에 없으면 run_eval.py 가 낡은 것이다. "
                      "레포에서 다시 복사해라.", file=sys.stderr)
                sys.exit(1)

    api_targets = [m for m in targets if m.get("provider", "local") != "local"]
    if api_targets:
        docs: dict[str, int] = {}
        for c in chunks:
            docs[c.get("doc", "?")] = docs.get(c.get("doc", "?"), 0) + 1
        chars = sum(len(c["text"]) for c in chunks)

        print("\n" + "!" * 70)
        print("API 모델을 켰다 — 아래 문서의 본문이 외부 서버로 전송된다.")
        print("!" * 70)
        for d, cnt in sorted(docs.items(), key=lambda x: -x[1]):
            print(f"  청크 {cnt:>4}개   {d}")
        print(f"  합계 {len(chunks)}청크 · {chars:,}자 · 질의 {len(queries)}개도 함께 나간다")
        print()
        for m in api_targets:
            print(f"  보낼 곳 — {m['provider']:8} {m['name']}")
        print()
        print("  무료 등급 주의 — Gemini 무료 등급은 프롬프트와 응답이 Google")
        print("  제품 개선에 쓰일 수 있다고 공식 문서에 적혀 있다. 결제 계정을")
        print("  붙여 유료 등급으로 올리면 쓰이지 않는다.")
        print("  공개 입찰공고가 아닌 문서가 위 목록에 있으면 멈추고 팀에 물어라.")
        print("!" * 70)
        if not args.yes:
            try:
                if input("  계속하려면 yes 를 입력한다: ").strip().lower() != "yes":
                    print("  중단했다.")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\n  중단했다.")
                return

    print(f"청크 {len(chunks)}개 · 질의 {len(queries)}개 · 모델 {len(targets)}개")
    if args.self_test:
        print("자체 점검 모드 — 모델을 내려받지 않는다. 채점 로직만 확인한다.")
    else:
        print("CPU 로 실행한다. 큰 모델은 몇 분 걸린다.")

    summaries, details = [], []
    for cfg in targets:
        try:
            summary, detail = evaluate(cfg, chunks, queries,
                                       args.batch_size, args.self_test,
                                       args.rpm, args.tpm, not args.no_cache)
        except Exception as exc:
            print(f"  실패: {cfg['name']} — {type(exc).__name__}: {exc}")
            continue
        summaries.append(summary)
        details.extend(detail)

    if not summaries:
        print("\n성공한 모델이 없다.", file=sys.stderr)
        sys.exit(1)

    with RESULT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)

    with DETAIL.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(details[0].keys()))
        writer.writeheader()
        writer.writerows(details)

    print_table(summaries)
    print(f"\n  요약: {RESULT}")
    print(f"  질의별 상세: {DETAIL}   <- 틀린 질의를 여기서 확인한다")


if __name__ == "__main__":
    main()
