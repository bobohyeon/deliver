# =============================================================================
# 이 파일의 책임: queries.csv 가 채점에 쓸 수 있는 상태인지 미리 검사한다.
#   (1) run_eval.py 가 조용히 건너뛸 행을 찾아낸다 — 없는 청크 번호, 정답 없음,
#       note 에 "예시" 가 들어간 행
#   (2) kind 라벨이 맞는지 글자 대조로 확인한다 — no_overlap 인데 정답 청크와
#       단어가 겹치면 잡아낸다. 이건 사람 눈으로는 반드시 새어나간다
#   (3) 정답 청크가 몇 개 문서에 퍼져 있는지 보여준다. 한 문서에 몰리면
#       모델 비교가 그 문서 특성만 재게 된다
# 다른 파일과의 관계: make_chunks.py 의 chunks.csv 와 사람이 채운 queries.csv 를
#   읽는다. run_eval.py 의 load_queries() 와 같은 규칙으로 판정하므로, 여기서
#   통과하면 run_eval.py 에서도 같은 수의 질의가 채점된다.
#   numpy·torch 가 필요 없어 모델을 내려받기 전에 돌릴 수 있다.
# Spring 비교: 통합테스트 전에 도는 검증 계층이다. @Valid 로 요청 DTO 를 걸러
#   컨트롤러까지 못 들어가게 막는 것과 같은 자리다. run_eval.py 가 잘못된 행을
#   예외 없이 버리므로, 그 앞에 검증을 세워 소리가 나게 한다.
#
# 왜 필요한가
#   run_eval.py 는 못 쓰는 행을 건너뛰고 채점을 계속한다. 질의 40개를 넣었는데
#   32개만 채점돼도 알아채기 어렵다. 특히 note 에 "예시" 두 글자가 들어가면
#   경고 없이 빠진다. 실제로 그 사고가 났다.
# =============================================================================

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CHUNKS = ROOT / "chunks.csv"
QUERIES = ROOT / "queries.csv"

MIN_TOKEN = 2          # 한 글자 토큰은 우연히 겹치므로 세지 않는다
TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")


def load(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        print(f"파일이 없다: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text) if len(t) >= MIN_TOKEN]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="queries.csv 를 run_eval.py 규칙으로 미리 검사한다")
    parser.add_argument("--chunks", default=str(CHUNKS))
    parser.add_argument("--queries", default=str(QUERIES))
    args = parser.parse_args()

    chunk_rows = load(pathlib.Path(args.chunks))
    chunks = {int(r["chunk_id"]): r for r in chunk_rows}
    rows = load(pathlib.Path(args.queries))

    kept: list[tuple[int, str, set[int], str]] = []
    dropped: list[tuple[int, str, str]] = []
    label: list[tuple[int, str, str]] = []

    for line, row in enumerate(rows, start=2):     # 2행부터 (1행은 머리글)
        query = (row.get("query") or "").strip()
        if not query:
            continue

        if "예시" in (row.get("note") or ""):
            dropped.append((line, query, 'note 에 "예시" 가 있다'))
            continue

        gold, bad_ids = set(), []
        for part in (row.get("gold_chunk_ids") or "").replace(" ", "").split(","):
            if not part:
                continue
            if not part.isdigit():
                bad_ids.append(f"{part}(숫자 아님)")
            elif int(part) not in chunks:
                bad_ids.append(f"{part}(없는 청크)")
            else:
                gold.add(int(part))

        if bad_ids:
            dropped.append((line, query, "정답 " + " ".join(bad_ids)))
        if not gold:
            dropped.append((line, query, "쓸 수 있는 정답이 없다"))
            continue

        kind = (row.get("kind") or "").strip()
        kept.append((line, query, gold, kind))

        # 라벨 검증 — 질의 토큰이 정답 청크 본문에 있는지 본다
        hit = sorted({t for t in tokens(query)
                      for g in gold if t in chunks[g]["text"]})
        if kind == "no_overlap" and hit:
            label.append((line, query, "겹치는 말: " + " ".join(hit)))
        elif kind == "overlap" and not hit:
            label.append((line, query, "겹치는 말이 없다 (overlap 이 아니다)"))
        elif kind not in {"overlap", "no_overlap"}:
            label.append((line, query, f"모르는 kind: {kind or '(빈칸)'}"))

    n_overlap = sum(1 for *_, k in kept if k == "overlap")
    n_no = sum(1 for *_, k in kept if k == "no_overlap")

    print(f"청크 {len(chunks)}개 · queries.csv {len(rows)}행")
    print(f"채점될 질의 {len(kept)}개  ·  overlap {n_overlap}  ·  no_overlap {n_no}")

    if dropped:
        print(f"\n채점에서 빠지는 행 {len(dropped)}개 — run_eval.py 는 조용히 넘긴다")
        for line, query, why in dropped:
            print(f"  {line}행  {query[:34]:34}  {why}")

    if label:
        print(f"\n라벨이 안 맞는 행 {len(label)}개")
        for line, query, why in label:
            print(f"  {line}행  {query[:34]:34}  {why}")

    # 정답 청크가 어느 문서에 퍼져 있는지
    covered: set[int] = set()
    for *_, gold, _ in [(0, 0, g, k) for _, _, g, k in kept]:
        covered |= gold
    docs: dict[str, int] = {}
    for cid in covered:
        doc = chunks[cid].get("doc", "?")
        docs[doc] = docs.get(doc, 0) + 1

    print(f"\n정답으로 쓴 청크 {len(covered)}개 / 전체 {len(chunks)}개")
    for doc, count in sorted(docs.items(), key=lambda kv: -kv[1]):
        print(f"  {count:3}개  {doc}")
    if len(docs) < 2:
        print("  주의 — 정답이 문서 한 곳에 몰려 있다. 그 문서 특성만 재게 된다")

    if not n_no:
        print("\n주의 — no_overlap 질의가 없다. 임베딩을 쓸 근거를 못 만든다")

    if dropped or label:
        print("\n고칠 것이 있다. 위 행을 손보고 다시 돌려라")
        sys.exit(1)
    print("\n이상 없다. python run_eval.py --self-test 로 넘어가라")


if __name__ == "__main__":
    main()
