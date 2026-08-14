# =============================================================================
# 이 파일의 책임: 우리 코퍼스를 sentence-transformers 의
#   InformationRetrievalEvaluator 로 재측정한다. 세현님과 같은 도구·같은 지표를
#   쓰기 위한 것이다. 파인튜닝 전/후를 --tag 로 나눠 나란히 놓을 수 있다.
#
# 다른 파일과의 관계: run_eval.py 와 같은 chunks.csv · queries.csv 를 읽는다.
#   run_eval.py 는 여러 모델을 돌려 속도·메모리까지 재는 비교용이고, 이 파일은
#   표준 IR 지표 하나만 정확히 맞추는 용도다. 둘을 합치지 않은 이유는 run_eval.py
#   의 지표 정의가 다르기 때문이다(아래).
#
# Spring 비교: 운영 코드가 쓰는 라이브러리의 표준 평가기를 그대로 불러 쓰는
#   자리다. 지표를 손으로 구현하면 팀원과 정의가 어긋난다.
#
# 왜 이 파일이 필요한가 — 우리 R@k 는 표준 recall@k 가 아니다
#   run_eval.py 의 R@k 는 "첫 정답의 순위가 k 이하면 1" 이다. 이것은
#   Success@k · HitRate@k 이고, InformationRetrievalEvaluator 의 accuracy@k 에
#   해당한다. 표준 recall@k 는 |상위k ∩ 정답| / |정답 전체| 다.
#
#   정답이 하나면 둘이 같지만 여러 개면 크게 갈린다. 실제로 정답 평균 2.7개짜리
#   자료에서 3.4배 차이가 났다 (우리 R@5 0.927 대 표준 recall@5 0.2724).
#   팀원과 숫자를 나란히 놓기 전에 반드시 도구를 맞춘다.
#
# 검산 — accuracy@1 이 run_eval.py 의 R@1 과 비슷하게 나와야 한다.
#   다르면 조건이 어딘가 어긋난 것이다.
#
# 사용법
#   python ir_eval.py --model dragonkue/BGE-m3-ko --tag before
#   python ir_eval.py --model "C:\경로\embedding-finetuned" --tag after
#
#   --model 은 HuggingFace 이름과 로컬 폴더 경로를 똑같이 받는다.
#   LoRA 체크포인트 폴더(adapter_model.safetensors 만 있는 것)는 안 된다.
#   병합된 모델(model.safetensors + config.json)을 줘야 한다.
#
# 주의 — 학습 전/후는 반드시 같은 --max-seq 로 돌린다.
#   인수인계 11절 "같은 조건이란 세 가지다" 중 두 번째(최대 입력 길이)다.
# =============================================================================

import argparse
import csv
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="InformationRetrievalEvaluator 로 표준 IR 지표를 낸다")
    parser.add_argument("--model", default="dragonkue/BGE-m3-ko")
    parser.add_argument("--chunks", default="chunks.csv")
    parser.add_argument("--queries", default="queries.csv")
    parser.add_argument("--tag", default="",
                        help="결과 파일 이름. 비우면 모델명으로 만든다")
    parser.add_argument("--max-seq", type=int, default=1024,
                        help="학습 전/후를 같은 값으로 돌려야 한다")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu",
                        help="cpu(기본) 또는 cuda. 정확도는 장치와 무관하다")
    args = parser.parse_args()

    tag = args.tag or re.sub(r"[^A-Za-z0-9._-]", "_", args.model)

    # ── 청크 ────────────────────────────────────────────────────────────────
    corpus: dict[str, str] = {}
    with open(ROOT / args.chunks, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            corpus[row["chunk_id"]] = row["text"]
    print("청크:", len(corpus))

    # ── 질의 ────────────────────────────────────────────────────────────────
    # gold_chunk_ids 는 쉼표로 여러 개가 올 수 있다. 코퍼스에 없는 id 는 버린다.
    queries: dict[str, str] = {}
    relevant: dict[str, set[str]] = {}
    skipped = 0
    with open(ROOT / args.queries, encoding="utf-8-sig") as file:
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

    if not queries:
        raise SystemExit("채점할 질의가 없다. queries.csv 를 확인하라.")

    counts = [len(v) for v in relevant.values()]
    print("질의:", len(queries), "/ 건너뜀:", skipped)
    print("질의당 정답 — 평균", round(sum(counts) / len(counts), 2),
          "· 최대", max(counts))
    print()

    # ── 모델 ────────────────────────────────────────────────────────────────
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.evaluation import InformationRetrievalEvaluator

    model = SentenceTransformer(args.model, device=args.device)
    print("모델:", args.model)
    print("max_seq_length 기본:", model.max_seq_length, "-> 설정:", args.max_seq)
    model.max_seq_length = args.max_seq

    evaluator = InformationRetrievalEvaluator(
        queries=queries,
        corpus=corpus,
        relevant_docs=relevant,
        name=tag,
        batch_size=args.batch_size,
        show_progress_bar=True,
        # 세현님 InformationRetrievalEvaluator 기본값과 맞춘다.
        # map@100 · mrr@10 · ndcg@10 · recall@1 · recall@5 가 그 조합이다.
        accuracy_at_k=[1, 3, 5, 10],
        precision_recall_at_k=[1, 3, 5, 10],
        mrr_at_k=[10],
        ndcg_at_k=[10],
        map_at_k=[100],
    )

    result = evaluator(model)

    print()
    print("=" * 62)
    print("모델:", args.model)
    print("청크", len(corpus), "· 질의", len(queries), "· max_seq", args.max_seq)
    print("=" * 62)
    for key in sorted(result):
        print(f"  {key:<48} {result[key]:.4f}")

    out = {k: round(float(v), 4) for k, v in result.items()}
    out["model"] = args.model
    out["chunks"] = len(corpus)
    out["queries"] = len(queries)
    out["max_seq"] = args.max_seq
    out["gold_per_query_avg"] = round(sum(counts) / len(counts), 2)

    path = ROOT / ("ir_" + tag + ".json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(out, file, ensure_ascii=False, indent=2)

    print()
    print("저장:", path.name)
    print()
    print("검산 — accuracy@1 이 run_eval.py 의 R@1 과 비슷해야 한다.")
    print("      recall@k 와 accuracy@k 를 혼동하지 않는다. 정의가 다르다.")


if __name__ == "__main__":
    main()
