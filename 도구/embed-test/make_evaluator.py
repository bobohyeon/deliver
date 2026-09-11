# =============================================================================
# 이 파일의 책임: 우리 조달문서 평가셋(chunks.csv · queries.csv)으로
#   InformationRetrievalEvaluator 를 만들어 준다. 학습하는 쪽이 이것을
#   SentenceTransformerTrainer 에 넣으면, 학습 중간중간 우리 기준 점수가
#   학습 로그에 찍힌다.
#
#   왜 필요한가: 학습이 끝난 모델을 zip 으로 주고받으면 왕복 한 번에 몇 시간이
#   걸린다. 그리고 끝난 뒤에야 나빠진 것을 안다. 평가기를 학습 안에 넣으면
#   50스텝마다 우리 기준 점수가 보이므로, 학습 초반에 방향이 틀린 것을 알 수 있다.
#
# 다른 파일과의 관계: ir_eval.py 와 **똑같은 규칙**으로 CSV 를 읽고 **똑같은 지표
#   설정**을 쓴다. 그래서 학습 로그에 찍히는 값과 나중에 ir_eval.py 로 재는 값이
#   맞아야 한다 — 맞지 않으면 어느 한쪽 조건이 어긋난 것이다.
#
# Spring 비교: 테스트 픅스처(고정 데이터셋)를 팀이 공유하는 모듈로 빼서,
#   각자 자기 코드에서 같은 기준으로 검증하게 만드는 것과 같다.
#
# 사용법 1 — 평가셋이 제대로 읽히는지 먼저 확인 (모델 불필요, 1초)
#   python make_evaluator.py
#
# 사용법 2 — 학습 스크립트에 넣기
#   from make_evaluator import build_evaluator
#
#   evaluator = build_evaluator(name="tasqra")
#
#   args = SentenceTransformerTrainingArguments(
#       output_dir=...,
#       per_device_train_batch_size=128,
#       num_train_epochs=1,
#       learning_rate=2e-5,
#       eval_strategy="steps",     # <- 이 두 줄이 있어야 곡선이 찍힌다
#       eval_steps=50,
#       logging_steps=50,
#   )
#   trainer = SentenceTransformerTrainer(
#       model=model, args=args, train_dataset=..., loss=...,
#       evaluator=evaluator,       # <- 여기
#   )
#
#   그러면 학습 로그에 tasqra_cosine_ndcg@10 · tasqra_cosine_accuracy@1 등이
#   50스텝마다 찍힌다. 여러 개를 함께 보려면 SequentialEvaluator 로 묶는다.
# =============================================================================

from __future__ import annotations

import csv
import io
import pathlib
import statistics as st

ROOT = pathlib.Path(__file__).resolve().parent


def load_corpus(path: str | pathlib.Path = "chunks.csv") -> dict[str, str]:
    file_path = pathlib.Path(path)
    if not file_path.is_absolute():
        file_path = ROOT / file_path
    corpus: dict[str, str] = {}
    with io.open(file_path, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            corpus[row["chunk_id"]] = row["text"]
    if not corpus:
        raise SystemExit(f"청크가 비어 있다: {file_path}")
    return corpus


def load_queries(
    corpus: dict[str, str], path: str | pathlib.Path = "queries.csv"
) -> tuple[dict[str, str], dict[str, set[str]], list[str]]:
    """질의와 정답을 읽는다.

    ir_eval.py 와 같은 규칙이다 — 코퍼스에 없는 gold id 는 버리고, 정답이
    하나도 남지 않은 질의는 건너뛴다. 이 규칙이 다르면 점수가 달라진다.
    """
    file_path = pathlib.Path(path)
    if not file_path.is_absolute():
        file_path = ROOT / file_path

    queries: dict[str, str] = {}
    relevant: dict[str, set[str]] = {}
    kinds: list[str] = []
    skipped = 0

    with io.open(file_path, encoding="utf-8-sig") as file:
        for index, row in enumerate(csv.DictReader(file)):
            text = (row.get("query") or "").strip()
            gold = {
                part
                for part in (row.get("gold_chunk_ids") or "").replace(" ", "").split(",")
                if part and part in corpus
            }
            if not text or not gold:
                skipped += 1
                continue
            key = "q" + str(index)
            queries[key] = text
            relevant[key] = gold
            kinds.append((row.get("kind") or "unknown").strip() or "unknown")

    if not queries:
        raise SystemExit(f"채점할 질의가 없다: {file_path}")
    if skipped:
        print(f"  건너뛴 질의: {skipped}건 (정답 id 가 코퍼스에 없음)")
    return queries, relevant, kinds


def build_evaluator(
    chunks: str | pathlib.Path = "chunks.csv",
    queries: str | pathlib.Path = "queries.csv",
    name: str = "tasqra",
    batch_size: int = 8,
    show_progress_bar: bool = False,
    quiet: bool = False,
):
    """우리 평가셋으로 InformationRetrievalEvaluator 를 만든다.

    지표 조합은 ir_eval.py 와 같게 고정했다. 학습 로그에 찍히는 이름은
    "{name}_cosine_ndcg@10" 처럼 된다.

    show_progress_bar 기본값이 False 인 이유: 학습 중 50스텝마다 불리므로
    진행바가 로그를 덮는다. 단독으로 잴 때만 True 로 준다.
    """
    from sentence_transformers.evaluation import InformationRetrievalEvaluator

    corpus = load_corpus(chunks)
    query_map, relevant, kinds = load_queries(corpus, queries)

    if not quiet:
        counts = [len(v) for v in relevant.values()]
        kind_summary: dict[str, int] = {}
        for k in kinds:
            kind_summary[k] = kind_summary.get(k, 0) + 1
        print(f"  평가셋 '{name}': 청크 {len(corpus)} · 질의 {len(query_map)}")
        print(f"  질의당 정답 — 평균 {st.mean(counts):.2f} · 최대 {max(counts)}")
        print("  질의 종류 —", ", ".join(f"{k} {v}" for k, v in sorted(kind_summary.items())))

    return InformationRetrievalEvaluator(
        queries=query_map,
        corpus=corpus,
        relevant_docs=relevant,
        name=name,
        batch_size=batch_size,
        show_progress_bar=show_progress_bar,
        # ir_eval.py 와 같은 조합. 바꾸면 두 도구의 수치가 안 맞는다.
        accuracy_at_k=[1, 3, 5, 10],
        precision_recall_at_k=[1, 3, 5, 10],
        mrr_at_k=[10],
        ndcg_at_k=[10],
        map_at_k=[100],
    )


def main() -> None:
    """평가셋만 확인한다. 모델을 불러오지 않으므로 즉시 끝난다."""
    print("=" * 66)
    print("평가셋 확인 (모델 로딩 없음)")
    print("=" * 66)
    corpus = load_corpus()
    query_map, relevant, kinds = load_queries(corpus)

    lengths = [len(v) for v in corpus.values()]
    counts = [len(v) for v in relevant.values()]
    kind_summary: dict[str, int] = {}
    for k in kinds:
        kind_summary[k] = kind_summary.get(k, 0) + 1

    print(f"  청크 {len(corpus)}개")
    print(f"    글자 중앙값 {st.median(lengths):.0f} · 평균 {st.mean(lengths):.0f} · 최대 {max(lengths)}")
    print(f"  질의 {len(query_map)}개")
    print(f"    질의당 정답 평균 {st.mean(counts):.2f} · 최대 {max(counts)}")
    print("    종류 —", ", ".join(f"{k} {v}" for k, v in sorted(kind_summary.items())))
    print()
    print("  기준값 (dragonkue/BGE-m3-ko · max_seq 1024 · 청크 649 · 질의 133)")
    print("    accuracy@1  0.5639")
    print("    map@100     0.6518")
    print("    ndcg@10     0.6878")
    print("    recall@5    0.7506")
    print()
    print("  청크·질의 수가 위와 다르면 다른 평가셋이므로 기준값과 비교할 수 없다.")
    print()
    print("  학습 스크립트에 넣는 방법은 이 파일 맨 위 주석을 본다.")


if __name__ == "__main__":
    main()
