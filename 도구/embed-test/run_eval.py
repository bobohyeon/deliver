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
             batch_size: int, self_test: bool = False) -> tuple[dict, list[dict]]:
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
        model = api_encoders.build(provider, name, model_cfg["dim"])
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
    }
    for group in ("all", "overlap", "no_overlap"):
        n = counts[group]
        for k in TOP_K:
            summary[f"R@{k}_{group}"] = round(hits[k][group] / n, 3) if n else ""
        summary[f"MRR_{group}"] = round(rr_sum[group] / n, 3) if n else ""
        summary[f"n_{group}"] = n

    return summary, detail


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
    args = parser.parse_args()

    if args.list:
        print("로컬 모델 (기본 실행)")
        for m in MODELS:
            print(f"  {m['name']}")
        print("\nAPI 모델 (--api 또는 --api-only 일 때만)")
        for m in API_MODELS:
            key = f"{m['provider'].upper()}_API_KEY"
            if m["provider"] == "gemini":
                key = "GEMINI_API_KEY"
            print(f"  {m['name']:28} {m['provider']:8} dim={m['dim']}  {key}")
        print("\n--only 는 이름의 일부만 적으면 된다. 예 — --only e5-base")
        return

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
        print("\n" + "!" * 66)
        print("API 모델을 켰다 — 청크 전문이 외부 서버로 전송된다.")
        print("입찰·계약 문서를 넣은 상태라면 팀 합의가 먼저다.")
        for m in api_targets:
            print(f"  {m['provider']:8} {m['name']}")
        print("!" * 66)

    print(f"청크 {len(chunks)}개 · 질의 {len(queries)}개 · 모델 {len(targets)}개")
    if args.self_test:
        print("자체 점검 모드 — 모델을 내려받지 않는다. 채점 로직만 확인한다.")
    else:
        print("CPU 로 실행한다. 큰 모델은 몇 분 걸린다.")

    summaries, details = [], []
    for cfg in targets:
        try:
            summary, detail = evaluate(cfg, chunks, queries,
                                       args.batch_size, args.self_test)
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
