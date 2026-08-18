# =============================================================================
# 이 파일의 책임: 파인튜닝 전/후 모델의 임베딩을 한 번만 만들어 캐시하고, 그것으로
#   "왜 떨어졌는가"를 구분하는 검사 다섯 개를 돌린다. ir_eval.py 가 총점을 주고
#   이 파일은 그 총점이 어디서 깎였는지를 본다.
#
#   검사 A. 표현 붕괴 — 청크 벡터끼리 서로 얼마나 비슷해졌는가
#     MultipleNegativesRankingLoss 가 망가지면 모든 벡터가 한 곳으로 뭉친다.
#     그러면 무엇을 물어도 비슷한 것이 나와 순위가 무의미해진다.
#   검사 B. 질의 종류별 — overlap(글자 겹침) 대 no_overlap(글자 안 겹침)
#     no_overlap 이 곧 RAG-04 판정 기준이다. 이쪽만 크게 떨어졌으면
#     "의미 매칭 능력이 상했다"는 뜻이고, 양쪽이 같이 떨어졌으면 전반적 손상이다.
#   검사 C. 청크 길이별 — 긴 청크에서 더 떨어지는가
#     학습 때 384 토큰으로 잘렸다면 긴 청크에서 손해가 커야 한다. 그렇지 않으면
#     절단은 주된 원인이 아니다.
#   검사 D. 회귀 사례 — before 에서 맞고 after 에서 틀린 질의 목록
#   검사 E. 정규화 — 벡터 노름이 1 인가 (normalize 설정이 바뀌었는지)
#
# 다른 파일과의 관계: ir_eval.py 와 같은 chunks.csv · queries.csv 를 읽고 같은
#   방식으로 정답을 걸러낸다(코퍼스에 없는 gold id 는 버린다). 그래서 여기 수치가
#   ir_eval.py 의 accuracy@k 와 맞아야 한다 — 맞지 않으면 어느 쪽이 잘못됐다.
#
# Spring 비교: 통합테스트가 실패했을 때 원인을 좁히려고 계층별로 나눠 재보는
#   진단 하네스에 해당한다.
#
# 사용법 (한 번에 두 모델)
#   python diag_embed.py --before dragonkue/BGE-m3-ko \
#                        --after "C:\Users\bbb\Desktop\임베딩 모델\embedding-finetuned"
#
#   임베딩은 .npy 로 캐시된다. 두 번째 실행부터는 인코딩을 건너뛴다.
#   설정을 바꿔 다시 재려면 --no-cache 를 준다.
# =============================================================================

import argparse
import csv
import gc
import hashlib
import io
import json
import pathlib
import statistics as st
import tempfile

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / "_diag_cache"


# ─── 입력 ────────────────────────────────────────────────────────────────────


def load_corpus(name: str) -> dict[str, str]:
    corpus: dict[str, str] = {}
    with io.open(ROOT / name, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            corpus[row["chunk_id"]] = row["text"]
    return corpus


def load_queries(name: str, corpus: dict[str, str]) -> list[dict]:
    """ir_eval.py 와 똑같은 규칙으로 질의를 읽는다.

    코퍼스에 없는 gold id 를 버리는 것까지 같게 해야 두 도구의 수치가 맞는다.
    """
    out: list[dict] = []
    with io.open(ROOT / name, encoding="utf-8-sig") as file:
        for index, row in enumerate(csv.DictReader(file)):
            text = (row.get("query") or "").strip()
            gold = {
                part
                for part in (row.get("gold_chunk_ids") or "").replace(" ", "").split(",")
                if part and part in corpus
            }
            if not text or not gold:
                continue
            out.append(
                {
                    "key": "q" + str(index),
                    "query": text,
                    "gold": gold,
                    # kind 가 없는 오래된 queries.csv 도 있으므로 기본값을 둔다.
                    "kind": (row.get("kind") or "unknown").strip() or "unknown",
                    "note": (row.get("note") or "").strip(),
                }
            )
    return out


# ─── 인코딩 (캐시) ───────────────────────────────────────────────────────────


def _cache_path(model_path: str, texts: list[str], tag: str, max_seq: int) -> pathlib.Path:
    # 모델 · 길이 · 텍스트 내용이 모두 같을 때만 캐시를 쓴다.
    digest = hashlib.sha256(
        ("|".join(texts) + f"|{model_path}|{max_seq}").encode("utf-8")
    ).hexdigest()[:16]
    return CACHE / f"{tag}_{digest}.npy"


def encode_both(model_path: str, chunk_texts: list[str], query_texts: list[str],
                prefix: str, max_seq: int, batch_size: int, device: str,
                use_cache: bool) -> tuple[np.ndarray, np.ndarray]:
    """청크와 질의를 한 번의 모델 로딩으로 함께 인코딩한다.

    모델을 두 번 올리면 BGE-M3 는 로딩만 30초씩 더 걸리고, 무엇보다 메모리를
    두 번 오르내린다. 개발 노트북 가용 메모리가 넉넉하지 않아 한 번만 올린다.
    끝나면 즉시 내려서 다음 모델을 올릴 자리를 만든다.
    """
    CACHE.mkdir(exist_ok=True)
    cp = _cache_path(model_path, chunk_texts, prefix + "_chunk", max_seq)
    qp = _cache_path(model_path, query_texts, prefix + "_query", max_seq)
    if use_cache and cp.is_file() and qp.is_file():
        print(f"    캐시 사용: {cp.name} · {qp.name}")
        return np.load(cp), np.load(qp)

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_path, device=device)
    print(f"    max_seq_length 기본: {model.max_seq_length} -> 설정: {max_seq}")
    model.max_seq_length = max_seq

    def run(texts: list[str], what: str) -> np.ndarray:
        print(f"    {what} {len(texts)}건 인코딩")
        return model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            # 정규화하지 않은 원본을 저장한다. 검사 E 에서 노름을 봐야 하기 때문이다.
            normalize_embeddings=False,
        )

    cv = run(chunk_texts, "청크")
    qv = run(query_texts, "질의")
    np.save(cp, cv)
    np.save(qp, qv)

    # 다음 모델을 올리기 전에 확실히 내린다.
    del model
    gc.collect()
    return cv, qv


def unit(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return v / norm


# ─── 검사 ────────────────────────────────────────────────────────────────────


def ranks_and_hits(qv: np.ndarray, cv: np.ndarray, queries: list[dict],
                   chunk_ids: list[str]) -> tuple[np.ndarray, list[int]]:
    """각 질의에 대해 (유사도 행렬, 첫 정답의 순위) 를 돌려준다.

    순위는 1부터 센다. 정답을 못 찾으면 len(chunk_ids)+1 로 둔다.
    """
    sim = unit(qv) @ unit(cv).T
    index_of = {cid: i for i, cid in enumerate(chunk_ids)}
    first_rank: list[int] = []
    for row, q in zip(sim, queries):
        order = np.argsort(-row)
        gold_idx = {index_of[g] for g in q["gold"]}
        rank = len(chunk_ids) + 1
        for position, idx in enumerate(order, start=1):
            if idx in gold_idx:
                rank = position
                break
        first_rank.append(rank)
    return sim, first_rank


def acc_at(ranks: list[int], k: int) -> float:
    if not ranks:
        return float("nan")
    return sum(1 for r in ranks if r <= k) / len(ranks)


def check_collapse(cv_before: np.ndarray, cv_after: np.ndarray) -> None:
    print()
    print("=" * 72)
    print("A. 표현 붕괴 — 청크 벡터끼리 서로 얼마나 비슷한가")
    print("=" * 72)
    print("   벡터가 한 곳으로 뭉치면(평균↑ 표준편차↓) 무엇을 물어도 비슷한 것이")
    print("   나와 순위가 무의미해진다. MNRL 이 망가질 때 나타나는 증상이다.")
    print()
    rows = []
    for label, cv in (("before", cv_before), ("after", cv_after)):
        u = unit(cv)
        sim = u @ u.T
        n = sim.shape[0]
        # 대각선(자기 자신)을 뺀 상삼각만 본다.
        iu = np.triu_indices(n, k=1)
        vals = sim[iu]
        rows.append((label, float(vals.mean()), float(vals.std()),
                     float(np.percentile(vals, 95)), float(vals.max())))
    print(f"   {'':8} {'평균':>8} {'표준편차':>10} {'상위5%':>10} {'최대':>8}")
    for label, mean, sd, p95, mx in rows:
        print(f"   {label:8} {mean:8.4f} {sd:10.4f} {p95:10.4f} {mx:8.4f}")
    dm = rows[1][1] - rows[0][1]
    ds = rows[1][2] - rows[0][2]
    print()
    print(f"   변화: 평균 {dm:+.4f} · 표준편차 {ds:+.4f}")
    if dm > 0.05 and ds < 0:
        print("   -> 뭉쳤다. 표현 붕괴 신호다. 손실·배치 구성 문제일 가능성이 크다.")
    elif abs(dm) <= 0.05:
        print("   -> 분포가 크게 변하지 않았다. 붕괴는 주된 원인이 아니다.")
    else:
        print("   -> 판단 보류. 아래 검사와 함께 본다.")


def check_by_kind(queries: list[dict], rb: list[int], ra: list[int]) -> None:
    print()
    print("=" * 72)
    print("B. 질의 종류별 — no_overlap 이 RAG-04 판정 기준이다")
    print("=" * 72)
    print("   overlap    = 질의 글자가 본문에 겹치는 것")
    print("   no_overlap = 글자가 하나도 겹치지 않는 것 (의미로만 찾아야 한다)")
    print()
    kinds = sorted({q["kind"] for q in queries})
    print(f"   {'종류':<12} {'수':>4} {'acc@1 전':>9} {'acc@1 후':>9} {'변화':>8}"
          f" {'acc@5 전':>9} {'acc@5 후':>9} {'변화':>8}")
    for kind in kinds:
        idx = [i for i, q in enumerate(queries) if q["kind"] == kind]
        b1 = acc_at([rb[i] for i in idx], 1)
        a1 = acc_at([ra[i] for i in idx], 1)
        b5 = acc_at([rb[i] for i in idx], 5)
        a5 = acc_at([ra[i] for i in idx], 5)
        d1 = (a1 / b1 - 1) * 100 if b1 else float("nan")
        d5 = (a5 / b5 - 1) * 100 if b5 else float("nan")
        print(f"   {kind:<12} {len(idx):>4} {b1:>9.4f} {a1:>9.4f} {d1:>+7.1f}%"
              f" {b5:>9.4f} {a5:>9.4f} {d5:>+7.1f}%")
    print()
    print("   읽는 방법")
    print("   · no_overlap 만 크게 떨어졌다 -> 의미 매칭이 상했다 (손실·데이터 문제)")
    print("   · 양쪽이 비슷하게 떨어졌다   -> 전반적 손상 (설정·절단 등)")
    print("   · overlap 이 더 떨어졌다     -> 어휘 표면 정보가 상했다 (드문 경우)")


def check_by_length(queries: list[dict], corpus: dict[str, str],
                    rb: list[int], ra: list[int]) -> None:
    print()
    print("=" * 72)
    print("C. 정답 청크 길이별 — 학습 때 384 토큰 절단의 흔적을 찾는다")
    print("=" * 72)
    print("   학습이 짧게 잘린 본문으로 이뤄졌다면 긴 청크에서 손해가 커야 한다.")
    print()
    buckets = [(0, 200), (200, 400), (400, 700), (700, 10 ** 9)]
    print(f"   {'정답 청크 글자':<16} {'수':>4} {'acc@1 전':>9} {'acc@1 후':>9} {'변화':>8}")
    for low, high in buckets:
        idx = []
        for i, q in enumerate(queries):
            # 정답이 여러 개면 가장 짧은 것을 기준으로 한다 (가장 찾기 쉬운 것).
            lengths = [len(corpus[g]) for g in q["gold"]]
            if low <= min(lengths) < high:
                idx.append(i)
        if not idx:
            continue
        b1 = acc_at([rb[i] for i in idx], 1)
        a1 = acc_at([ra[i] for i in idx], 1)
        d1 = (a1 / b1 - 1) * 100 if b1 else float("nan")
        label = f"{low}~{high if high < 10 ** 9 else ''}"
        print(f"   {label:<16} {len(idx):>4} {b1:>9.4f} {a1:>9.4f} {d1:>+7.1f}%")


def check_regressions(queries: list[dict], rb: list[int], ra: list[int],
                      corpus: dict[str, str], limit: int) -> None:
    print()
    print("=" * 72)
    print("D. 회귀 사례 — before 에서 맞고 after 에서 틀린 질의")
    print("=" * 72)
    worse = [
        (ra[i] - rb[i], i) for i in range(len(queries))
        if rb[i] <= 5 and ra[i] > 5
    ]
    worse.sort(reverse=True)
    better = sum(1 for i in range(len(queries)) if ra[i] <= 5 and rb[i] > 5)
    print(f"   상위5 안에 있다가 밖으로 나간 질의: {len(worse)}개")
    print(f"   반대로 들어온 질의: {better}개")
    print()
    for delta, i in worse[:limit]:
        q = queries[i]
        gold_len = min(len(corpus[g]) for g in q["gold"])
        print(f"   [{q['kind']}] 순위 {rb[i]} -> {ra[i]} (정답 {gold_len}자)")
        print(f"       {q['query'][:60]}")


def check_norm(cv_before: np.ndarray, cv_after: np.ndarray) -> None:
    print()
    print("=" * 72)
    print("E. 벡터 노름 — normalize 설정이 바뀌었는지")
    print("=" * 72)
    for label, cv in (("before", cv_before), ("after", cv_after)):
        norms = np.linalg.norm(cv, axis=1)
        print(f"   {label:8} 평균 {norms.mean():8.4f} · 표준편차 {norms.std():7.4f}"
              f" · 최소 {norms.min():7.4f} · 최대 {norms.max():7.4f}")
    print()
    print("   코사인 유사도만 쓴다면 노름 차이는 결과에 영향이 없다.")
    print("   다만 크게 다르면 모듈 구성(Normalize 레이어)이 바뀐 것이므로,")
    print("   저장 과정에서 무언가 달라졌다는 단서가 된다.")


# ─── 실행 ────────────────────────────────────────────────────────────────────


def selftest() -> None:
    """이 파일의 계산 로직을 가짜 데이터로 검증한다.

    왜 필요한가: 진짜 실행은 인코딩에 10분 넘게 걸린다. 계산이 틀렸으면 그
    시간을 버리고 다시 돌려야 한다. 먼저 1초 안에 확인한다.
    numpy 가 없는 환경에서는 이 파일의 로직을 검사할 수 없어서, 검사를
    스크립트 안에 넣어 실행하는 쪽에서 돌리게 했다.
    """
    import contextlib

    print("=" * 72)
    print("자체 검사")
    print("=" * 72)

    # 1. unit — 0 벡터를 0 으로 나누지 않는다
    v = np.array([[3.0, 4.0], [0.0, 0.0], [1.0, 0.0]])
    u = unit(v)
    norms = [round(float(x), 6) for x in np.linalg.norm(u, axis=1)]
    assert abs(norms[0] - 1.0) < 1e-9, norms
    assert norms[1] == 0.0, "0 벡터가 nan 이 되면 안 된다"
    print("  unit               노름", norms, "OK")

    # 2. ranks_and_hits — 순위를 1부터, 못 찾으면 n+1
    chunk_ids = ["c1", "c2", "c3"]
    cv = np.array([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]])
    qs = [
        {"key": "q0", "query": "a", "gold": {"c1"}, "kind": "overlap", "note": ""},
        {"key": "q1", "query": "b", "gold": {"c2"}, "kind": "no_overlap", "note": ""},
    ]
    _, ranks = ranks_and_hits(np.array([[1.0, 0.0], [0.0, 1.0]]), cv, qs, chunk_ids)
    assert ranks == [1, 1], ranks
    print("  ranks_and_hits     정확히 맞는 질의 -> 순위", ranks, "OK")

    qs_far = [{"key": "q", "query": "a", "gold": {"c2"}, "kind": "x", "note": ""}]
    _, far = ranks_and_hits(np.array([[1.0, 0.0]]), cv, qs_far, chunk_ids)
    assert 1 <= far[0] <= 3, far
    print("  ranks_and_hits     엉뚱한 질의 -> 순위", far, "OK")

    # 3. acc_at
    assert acc_at([1, 2, 3], 1) == 1 / 3 and acc_at([1, 2, 3], 3) == 1.0
    empty = acc_at([], 1)  # 빈 목록은 nan 이어야 하고 예외가 나면 안 된다
    assert empty != empty, "빈 목록에서 nan 이 아니다"
    print("  acc_at             @1", round(acc_at([1, 2, 3], 1), 4),
          "· @3", acc_at([1, 2, 3], 3), "· 빈 목록 nan OK")

    # 4. load_corpus / load_queries — BOM · kind 없음 · 없는 gold id
    global ROOT
    original_root = ROOT
    try:
        tmp = pathlib.Path(tempfile.mkdtemp())
        ROOT = tmp
        (tmp / "c.csv").write_text("chunk_id,text\n1,가나다\n2,라마바\n", encoding="utf-8")
        (tmp / "q1.csv").write_text("query,gold_chunk_ids\n질문,1\n버려질것,99\n", encoding="utf-8")
        corpus = load_corpus("c.csv")
        loaded = load_queries("q1.csv", corpus)
        assert len(loaded) == 1, f"코퍼스에 없는 gold(99)는 버려야 한다: {loaded}"
        assert loaded[0]["kind"] == "unknown", loaded[0]["kind"]
        print("  load_queries       kind 없는 csv ->", len(loaded), "질의 · kind unknown OK")

        (tmp / "q2.csv").write_text(
            "query,gold_chunk_ids,kind,note\n질문,\"1, 2\",no_overlap,메모\n",
            encoding="utf-8-sig")
        loaded2 = load_queries("q2.csv", corpus)
        assert loaded2[0]["gold"] == {"1", "2"}, loaded2[0]["gold"]
        assert loaded2[0]["kind"] == "no_overlap"
        print("  load_queries       BOM + 정답 2개 + kind ->",
              sorted(loaded2[0]["gold"]), loaded2[0]["kind"], "OK")
    finally:
        ROOT = original_root

    # 5. 검사 함수들이 예외 없이 돌고, 붕괴 시나리오를 붕괴로 판정하는가
    rng = np.random.default_rng(0)
    cb = rng.normal(size=(30, 8))
    ca = rng.normal(size=(30, 8)) * 0.05 + 5.0  # 일부러 한 곳으로 뭉치게
    corpus3 = {str(i): "가" * (50 + i * 40) for i in range(30)}
    ids3 = list(corpus3)
    qs3 = [
        {"key": f"q{i}", "query": f"질의{i}", "gold": {str(i % 30)},
         "kind": "overlap" if i % 2 else "no_overlap", "note": ""}
        for i in range(20)
    ]
    _, rb3 = ranks_and_hits(rng.normal(size=(20, 8)), cb, qs3, ids3)
    _, ra3 = ranks_and_hits(rng.normal(size=(20, 8)), ca, qs3, ids3)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check_collapse(cb, ca)
        check_by_kind(qs3, rb3, ra3)
        check_by_length(qs3, corpus3, rb3, ra3)
        check_regressions(qs3, rb3, ra3, corpus3, 3)
        check_norm(cb, ca)
    out = buf.getvalue()
    assert "표현 붕괴" in out and "no_overlap" in out, "출력이 비었다"
    assert "뭉쳤다" in out, "일부러 뭉친 데이터를 붕괴로 판정하지 못했다"
    print("  검사 A~E           예외 없음 ·", len(out.splitlines()),
          "줄 · 붕괴 시나리오 판정 OK")

    print()
    print("자체 검사 전부 통과. 이제 실제 측정을 돌려도 된다.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="파인튜닝 전/후 임베딩을 비교해 하락 원인을 구분한다")
    parser.add_argument("--before", default="dragonkue/BGE-m3-ko")
    parser.add_argument("--after", default="")
    parser.add_argument("--selftest", action="store_true",
                        help="계산 로직만 1초 안에 검증하고 끝낸다 (모델 불필요)")
    parser.add_argument("--chunks", default="chunks.csv")
    parser.add_argument("--queries", default="queries.csv")
    parser.add_argument("--max-seq", type=int, default=1024,
                        help="ir_eval.py 와 같은 값을 써야 수치가 맞는다")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--show", type=int, default=8, help="회귀 사례 표시 개수")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.after:
        raise SystemExit("--after 가 필요하다 (파인튜닝 모델 폴더). "
                         "로직만 검증하려면 --selftest 를 준다.")

    corpus = load_corpus(args.chunks)
    queries = load_queries(args.queries, corpus)
    chunk_ids = list(corpus)
    chunk_texts = [corpus[c] for c in chunk_ids]
    query_texts = [q["query"] for q in queries]

    print("청크", len(chunk_ids), "· 질의", len(queries))
    counts = [len(q["gold"]) for q in queries]
    print("질의당 정답 — 평균", round(st.mean(counts), 2), "· 최대", max(counts))
    kinds = {}
    for q in queries:
        kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
    print("질의 종류:", ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))

    use_cache = not args.no_cache
    print()
    print("[before]", args.before)
    cb, qb = encode_both(args.before, chunk_texts, query_texts, "before",
                         args.max_seq, args.batch_size, args.device, use_cache)
    print()
    print("[after]", args.after)
    ca, qa = encode_both(args.after, chunk_texts, query_texts, "after",
                         args.max_seq, args.batch_size, args.device, use_cache)

    _, rb = ranks_and_hits(qb, cb, queries, chunk_ids)
    _, ra = ranks_and_hits(qa, ca, queries, chunk_ids)

    print()
    print("=" * 72)
    print("검산 — ir_eval.py 의 accuracy@k 와 맞아야 한다")
    print("=" * 72)
    for k in (1, 3, 5, 10):
        print(f"   accuracy@{k:<3} before {acc_at(rb, k):.4f}   after {acc_at(ra, k):.4f}")
    print("   맞지 않으면 두 도구의 조건이 어긋난 것이므로 아래 해석을 믿지 않는다.")

    check_collapse(cb, ca)
    check_by_kind(queries, rb, ra)
    check_by_length(queries, corpus, rb, ra)
    check_regressions(queries, rb, ra, corpus, args.show)
    check_norm(cb, ca)

    out = {
        "before": args.before,
        "after": args.after,
        "max_seq": args.max_seq,
        "chunks": len(chunk_ids),
        "queries": len(queries),
        "accuracy": {
            f"@{k}": {"before": round(acc_at(rb, k), 4), "after": round(acc_at(ra, k), 4)}
            for k in (1, 3, 5, 10)
        },
        "by_kind": {
            kind: {
                "n": sum(1 for q in queries if q["kind"] == kind),
                "acc@1_before": round(acc_at([rb[i] for i, q in enumerate(queries) if q["kind"] == kind], 1), 4),
                "acc@1_after": round(acc_at([ra[i] for i, q in enumerate(queries) if q["kind"] == kind], 1), 4),
            }
            for kind in sorted({q["kind"] for q in queries})
        },
    }
    path = ROOT / "diag_embed.json"
    with io.open(path, "w", encoding="utf-8") as file:
        json.dump(out, file, ensure_ascii=False, indent=2)
    print()
    print("저장:", path.name)


if __name__ == "__main__":
    main()
