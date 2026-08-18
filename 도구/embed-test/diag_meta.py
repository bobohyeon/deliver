# =============================================================================
# 이 파일의 책임: 파인튜닝 모델의 "설정"과 "학습 데이터"만 검사한다. 모델 가중치를
#   불러오지 않으므로 몇 초 안에 끝나고 메모리를 거의 쓰지 않는다.
#   두 가지에 답하는 것이 목적이다.
#     (1) max_seq_length 기본값 384 가 어느 파일에서 오는가
#     (2) 학습 데이터 본문이 384 토큰에서 실제로 얼마나 잘리는가
#
# 다른 파일과의 관계: ir_eval.py 가 정확도를 재고, 이 파일은 그 결과의 원인을
#   찾는다. diag_embed.py 는 임베딩 공간을 검사한다 (모델 로딩이 필요하다).
#
# Spring 비교: 애플리케이션을 띄우지 않고 설정 파일과 입력 데이터만 훑는
#   진단용 CLI 도구다.
#
# 사용법
#   python diag_meta.py --model-dir "C:\Users\bbb\Desktop\임베딩 모델\embedding-finetuned"
#                       --train-data "C:\Users\bbb\Desktop\임베딩 모델\g2b_qa.jsonl"
# =============================================================================

import argparse
import io
import json
import pathlib
import re
import statistics as st

# max_seq_length 가 숨어 있을 수 있는 키 이름들. sentence-transformers 는
# 버전에 따라 이 값을 sentence_bert_config.json · tokenizer_config.json ·
# config.json 중 어디서든 읽는다.
KEY_PATTERN = re.compile(r"max.*(len|seq|pos)|seq.*len|model_max", re.IGNORECASE)


def scan_configs(model_dir: pathlib.Path) -> None:
    print("=" * 70)
    print("1. 설정 파일에서 길이 관련 키 찾기")
    print("=" * 70)
    if not model_dir.is_dir():
        print("  폴더가 없다:", model_dir)
        return

    found_any = False
    for path in sorted(model_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"  [읽기 실패] {path.name}: {exc}")
            continue
        if not isinstance(data, dict):
            continue
        hits = {k: v for k, v in data.items() if KEY_PATTERN.search(str(k))}
        rel = path.relative_to(model_dir)
        if hits:
            found_any = True
            print(f"  {rel}")
            for k, v in hits.items():
                print(f"      {k} = {v}")
        else:
            print(f"  {rel}  (길이 관련 키 없음)")

    if not found_any:
        print()
        print("  길이 관련 키가 어느 json 에도 없다.")
        print("  그러면 sentence-transformers 가 토크나이저의 model_max_length 나")
        print("  모델 config 의 max_position_embeddings 로 결정한 것이다.")


def scan_model_card(model_dir: pathlib.Path) -> None:
    print()
    print("=" * 70)
    print("2. 모델 카드(README.md) 에서 길이 · 학습 설정")
    print("=" * 70)
    readme = model_dir / "README.md"
    if not readme.is_file():
        print("  README.md 가 없다")
        return

    lines = readme.read_text(encoding="utf-8").splitlines()

    # sentence-transformers 가 자동 생성하는 모델 카드에는
    # "Maximum Sequence Length: N tokens" 줄이 있다.
    for i, line in enumerate(lines):
        if re.search(r"maximum sequence length|max_seq_length", line, re.IGNORECASE):
            print(f"  [{i}] {line.strip()}")

    # 학습 하이퍼파라미터 블록
    for i, line in enumerate(lines):
        if re.search(r"Training Hyperparameters|All Hyperparameters", line, re.IGNORECASE):
            print()
            print(f"  --- {line.strip()} (line {i}) ---")
            for l in lines[i : i + 45]:
                s = l.strip()
                if s.startswith("#") and i > 0 and l is not lines[i]:
                    break
                if s:
                    print("   ", s)
            break


def scan_train_data(path: pathlib.Path, model_name: str, limits: list[int]) -> None:
    print()
    print("=" * 70)
    print("3. 학습 데이터가 실제 토크나이저에서 몇 토큰인가")
    print("=" * 70)
    if not path.is_file():
        print("  파일이 없다:", path)
        return

    rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    print("  총", len(rows), "건")

    # 토크나이저만 받는다. 모델 가중치(2.2GB)는 내려받지 않는다.
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)
    print("  토크나이저:", model_name)
    print()

    for field in ("text", "summary"):
        values = [r.get(field, "") or "" for r in rows]
        chars = [len(v) for v in values]
        # add_special_tokens=False 로 순수 본문 토큰만 센다.
        toks = [len(tok.encode(v, add_special_tokens=False)) for v in values]

        print(f"  [{field}]")
        print(f"    글자  중앙값 {st.median(chars):>6.0f} · 평균 {st.mean(chars):>6.0f} · 최대 {max(chars):>6}")
        print(f"    토큰  중앙값 {st.median(toks):>6.0f} · 평균 {st.mean(toks):>6.0f} · 최대 {max(toks):>6}")
        ratio = st.mean(c / t for c, t in zip(chars, toks) if t)
        print(f"    글자/토큰 비 평균 {ratio:.2f}")
        for limit in limits:
            over = sum(1 for t in toks if t > limit)
            # 잘려 나가는 토큰의 총량도 본다. 비율만 보면 체감이 안 된다.
            lost = sum(max(0, t - limit) for t in toks)
            total = sum(toks)
            print(
                f"    {limit:>5} 토큰 초과: {over:>4}건 ({over / len(toks) * 100:5.1f}%)"
                f" · 잘려 버려지는 토큰 {lost:,} / {total:,} ({lost / total * 100:.1f}%)"
            )
        print()


def scan_duplicates(path: pathlib.Path) -> None:
    print("=" * 70)
    print("4. 학습 데이터 중복 — MNRL 거짓음성이 생기는 자리")
    print("=" * 70)
    if not path.is_file():
        return
    rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]

    from collections import Counter

    for field in ("text", "summary"):
        values = [(r.get(field, "") or "").strip() for r in rows]
        counter = Counter(values)
        dup_groups = {k: v for k, v in counter.items() if v > 1}
        dup_rows = sum(dup_groups.values())
        print(f"  [{field}] 완전 중복 그룹 {len(dup_groups)}개 · 해당 행 {dup_rows}건")
        for value, count in sorted(dup_groups.items(), key=lambda x: -x[1])[:3]:
            print(f"      {count}회: {value[:55]}")
    print()
    print("  완전 중복이 한 배치에 같이 들어가면 MultipleNegativesRankingLoss 가")
    print("  서로를 오답으로 학습한다. batch_sampler=NO_DUPLICATES 가 막는 대상이다.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="파인튜닝 모델 설정과 학습 데이터를 검사한다 (모델 로딩 없음)")
    parser.add_argument("--model-dir", required=True, help="embedding-finetuned 폴더")
    parser.add_argument("--train-data", default="", help="g2b_qa.jsonl 경로")
    parser.add_argument("--tokenizer", default="dragonkue/BGE-m3-ko",
                        help="토큰 길이를 잴 기준 토크나이저 (베이스 모델)")
    parser.add_argument("--limits", default="384,512,1024",
                        help="초과 비율을 볼 토큰 상한들")
    args = parser.parse_args()

    model_dir = pathlib.Path(args.model_dir)
    limits = [int(x) for x in args.limits.split(",") if x.strip()]

    scan_configs(model_dir)
    scan_model_card(model_dir)

    if args.train_data:
        data = pathlib.Path(args.train_data)
        scan_train_data(data, args.tokenizer, limits)
        scan_duplicates(data)

    print()
    print("=" * 70)
    print("읽는 방법")
    print("=" * 70)
    print("  · 384 토큰 초과 비율이 높고 버려지는 토큰이 많으면,")
    print("    학습이 잘린 본문으로 이뤄졌다는 뜻이다 -> 설정 문제(코드 수정 대상)")
    print("  · 초과 비율이 낮으면 절단은 원인이 아니다 -> 손실·데이터 쪽을 본다")
    print("  · 완전 중복이 많으면 MNRL 거짓음성이 실재한다 -> NO_DUPLICATES")


if __name__ == "__main__":
    main()
