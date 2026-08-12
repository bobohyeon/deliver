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
    if self_test:
        SentenceTransformer = _FakeModel
    else:
        from sentence_transformers import SentenceTransformer

    name = model_cfg["name"]
    print(f"\n{'=' * 66}")
    print(f"{name}")
    print(f"  {model_cfg['note']}")
    print(f"{'=' * 66}")

    before = rss_mb()
    t0 = time.perf_counter()
    model = SentenceTransformer(name, device="cpu")
    load_sec = time.perf_counter() - t0
    dim = model.get_sentence_embedding_dimension()
    print(f"  적재 {load_sec:.1f}초 · 차원 {dim}")

    passages = [model_cfg["passage_prefix"] + c["text"] for c in chunks]
    t0 = time.perf_counter()
    doc_vecs = model.encode(passages, batch_size=batch_size,
                            normalize_embeddings=True,
                            show_progress_bar=True,
                            convert_to_numpy=True)
    encode_sec = time.perf_counter() - t0
    peak = rss_mb()

    q_texts = [model_cfg["query_prefix"] + q["query"] for q in queries]
    q_vecs = model.encode(q_texts, batch_size=batch_size,
                          normalize_embeddings=True,
                          convert_to_numpy=True)

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
        "dim": dim,
        "load_sec": round(load_sec, 1),
        "encode_sec": round(encode_sec, 1),
        "sec_per_100_chunks": round(encode_sec / max(len(chunks), 1) * 100, 2),
        "mem_mb": round(peak - before, 0) if peak == peak else "",
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
        ("차원", "dim"),
        ("R@1 안겹침", "R@1_no_overlap"),
        ("R@5 안겹침", "R@5_no_overlap"),
        ("MRR 안겹침", "MRR_no_overlap"),
        ("R@5 겹침", "R@5_overlap"),
        ("R@5 전체", "R@5_all"),
    ])
    show("실행 비용 (CPU)", [
        ("적재 초", "load_sec"),
        ("전체 임베딩 초", "encode_sec"),
        ("100청크당 초", "sec_per_100_chunks"),
        ("메모리 MB", "mem_mb"),
    ])

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
    args = parser.parse_args()

    chunks = load_csv(CHUNKS, ["chunk_id", "doc", "text"])
    if args.limit_chunks:
        chunks = chunks[:args.limit_chunks]
    valid_ids = {int(c["chunk_id"]) for c in chunks}
    queries = load_queries(valid_ids)

    targets = MODELS
    if args.self_test:
        targets = [{"name": "self-test/fake", "query_prefix": "",
                    "passage_prefix": "", "note": "가짜 인코더. 채점 로직 점검용"}]
    elif args.only:
        targets = [m for m in MODELS
                   if any(pat.lower() in m["name"].lower() for pat in args.only)]
        if not targets:
            print("--only 조건에 맞는 모델이 없다.", file=sys.stderr)
            sys.exit(1)

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
