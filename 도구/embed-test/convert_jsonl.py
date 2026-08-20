# =============================================================================
# 이 파일의 책임: 남이 만든 JSONL 데이터셋을 우리 run_eval.py 입력으로 바꾼다.
#   (1) corpus.jsonl -> chunks.csv (chunk_id, doc, chars, text)
#       '문서명#c12' 형식의 source 에 1부터 정수 chunk_id 를 매기고 대응표를 남긴다
#   (2) summary 가 있는 행 -> queries.csv (query, gold_chunk_ids, kind, note)
#       summary 를 질의로, 그 행의 source 가 가리키는 청크를 정답으로 놓는다
#   (3) kind(overlap / no_overlap) 를 check_queries.py 와 똑같은 규칙으로 매긴다.
#       사람이 손으로 붙이지 않으므로 규칙이 어긋나면 두 데이터셋의 수치를
#       나란히 놓을 수 없다
#   (4) --normalize 로 전처리를 켜고 끌 수 있다. 같은 자료를 두 번 돌려
#       전처리가 점수를 얼마나 바꾸는지 재는 것이 목적이다
# 다른 파일과의 관계: diag_dataset.py 로 진단한 뒤 이 파일로 변환하고
#   check_queries.py 로 검사한 다음 run_eval.py --chunks/--queries 로 돌린다.
#   출력 형식은 make_chunks.py·make_queries.py 가 만드는 것과 같다.
#   표준 라이브러리만 쓴다.
# Spring 비교: 외부 시스템 응답을 우리 도메인 모델로 옮기는 매퍼다. 남의 DTO 를
#   그대로 서비스 계층에 흘리지 않고 우리 엔티티로 변환하는 자리와 같다.
#   변환 과정에서 버려지는 레코드를 세어 로그로 남기는 것까지 같은 이유다.
#
# 왜 필요한가
#   run_eval.py 는 chunks.csv 와 queries.csv 를 고정 형식으로 읽는다. 남의
#   JSONL 을 손으로 옮기면 정답 번호가 어긋나고, 어긋나도 run_eval.py 는
#   조용히 그 행을 건너뛴다. 그래서 변환을 코드로 고정하고 건너뛴 수를 찍는다.
#
# 사용법
#   python convert_jsonl.py --corpus ~/Desktop/worksheet/corpus.jsonl \
#                           --eval   ~/Desktop/worksheet/si_eval.jsonl \
#                           --out    ./sehyeon_eval
#   python convert_jsonl.py ... --out ./sehyeon_eval_norm --normalize
# =============================================================================

from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import re
import sys
import unicodedata

# check_queries.py 와 같은 값이어야 한다. 다르면 kind 라벨이 어긋난다.
MIN_TOKEN = 2
TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")

TEXT_KEYS = ("text", "body", "content", "passage", "chunk")
QUERY_KEYS = ("summary", "query", "question", "anchor")


def tokens(text: str) -> list[str]:
    """check_queries.py 의 tokens() 와 같은 규칙이다. 바꾸면 라벨이 어긋난다."""
    return [t for t in TOKEN.findall(str(text)) if len(t) >= MIN_TOKEN]


def normalize(text: str) -> str:
    """diag_dataset.py 가 찾아낸 전처리 흔적을 되돌린다.

    켜고 끄며 두 번 돌려 점수 차이를 보는 것이 목적이다. 그래서 무엇을
    바꾸는지 한 줄씩 적어 둔다. 추측으로 손대지 않는다.
    """
    t = unicodedata.normalize("NFC", str(text))          # 자모 분리 되돌림
    t = t.replace("\u3000", " ")                          # 전각 공백
    # '제\n2026\n–403호' -> '제2026–403호'. 공고번호가 쪼개진 것을 붙인다.
    t = re.sub(r"제\s*\n\s*(\d)", r"제\1", t)
    # 숫자 사이 줄바꿈을 없앤다. 대시가 끼어 있어도 붙인다.
    t = re.sub(r"(\d)\s*\n\s*([\-\u2013\u2014\u2212]?)\s*(\d)", r"\1\2\3", t)
    # en dash·em dash 를 하이픈으로. '2026-403호' 로 검색되게 한다.
    t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    # 줄바꿈이 ' / ' 로 치환된 자리를 줄바꿈으로 돌린다.
    t = re.sub(r"(?<=\S) / (?=\S)", "\n", t)
    # 표를 옮기며 생긴 연속 공백을 한 칸으로. 줄바꿈은 건드리지 않는다.
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def load_jsonl(path: pathlib.Path):
    rows, broken = [], 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                broken += 1
    return rows, broken


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="외부 JSONL 을 run_eval.py 입력(chunks.csv·queries.csv)으로 바꾼다")
    ap.add_argument("--corpus", required=True,
                    help="후보 청크 전체가 든 jsonl (예: corpus.jsonl)")
    ap.add_argument("--eval", required=True, dest="eval_path",
                    help="질의 필드(summary 등)가 든 jsonl (예: si_eval.jsonl)")
    ap.add_argument("--out", required=True, help="출력 폴더. 없으면 만든다")
    ap.add_argument("--normalize", action="store_true",
                    help="전처리 흔적을 되돌린다. 켜고 끈 두 벌을 비교하는 용도")
    ap.add_argument("--gold-includes-duplicates", action="store_true",
                    help="본문이 완전히 같은 청크를 모두 정답으로 인정한다")
    args = ap.parse_args(argv)

    corpus_path = pathlib.Path(args.corpus).expanduser()
    eval_path = pathlib.Path(args.eval_path).expanduser()
    out_dir = pathlib.Path(args.out).expanduser()
    for p in (corpus_path, eval_path):
        if not p.exists():
            print(f"없는 파일: {p}", file=sys.stderr)
            return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    corpus, c_broken = load_jsonl(corpus_path)
    ev, e_broken = load_jsonl(eval_path)
    if not corpus or not ev:
        print("읽은 행이 0이다.", file=sys.stderr)
        return 2

    field = next((k for k in TEXT_KEYS if k in corpus[0]), "text")
    qkey = next((k for k in QUERY_KEYS
                 if any(str(r.get(k, "")).strip() for r in ev)), None)
    if not qkey:
        print(f"질의 필드를 찾지 못했다 (찾은 이름: {', '.join(QUERY_KEYS)})",
              file=sys.stderr)
        return 2

    print(f"코퍼스 {len(corpus)}행 · 평가 {len(ev)}행"
          f" · 본문 필드 '{field}' · 질의 필드 '{qkey}'")
    if c_broken or e_broken:
        print(f"  [!] JSON 파싱 실패 — 코퍼스 {c_broken}줄 · 평가 {e_broken}줄")
    if args.normalize:
        print("  전처리 정규화: 켜짐")

    # ---- chunks.csv ----------------------------------------------------------
    # source 에 1부터 정수를 매긴다. run_eval.py 가 정수 chunk_id 를 요구한다.
    src_to_id: dict[str, int] = {}
    chunk_rows = []
    dup_src = 0
    for r in corpus:
        src = str(r.get("source", "")).strip()
        if not src:
            continue
        if src in src_to_id:
            dup_src += 1
            continue                      # 같은 source 가 두 번 오면 첫 것만 쓴다
        text = str(r.get(field, ""))
        if args.normalize:
            text = normalize(text)
        cid = len(chunk_rows) + 1
        src_to_id[src] = cid
        chunk_rows.append({"chunk_id": cid, "doc": str(r.get("doc", "")),
                           "chars": len(text), "text": text})
    if dup_src:
        print(f"  [!] source 중복 {dup_src}개는 첫 행만 남겼다")

    chunks_csv = out_dir / "chunks.csv"
    with chunks_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["chunk_id", "doc", "chars", "text"])
        w.writeheader()
        w.writerows(chunk_rows)

    # 본문이 같은 청크 묶음 — 정답 확장과 보고에 쓴다
    by_text = collections.defaultdict(list)
    for row in chunk_rows:
        by_text[re.sub(r"\s+", " ", row["text"]).strip()].append(row["chunk_id"])

    # ---- queries.csv --------------------------------------------------------
    q_rows = []
    missing_src, empty_q, expanded = 0, 0, 0
    kind_count = collections.Counter()
    for r in ev:
        q = str(r.get(qkey, "")).strip()
        if not q:
            continue
        src = str(r.get("source", "")).strip()
        cid = src_to_id.get(src)
        if cid is None:
            missing_src += 1        # 코퍼스에 없는 정답이다. 채점할 수 없다
            continue
        gold = [cid]
        if args.gold_includes_duplicates:
            twins = by_text.get(
                re.sub(r"\s+", " ", chunk_rows[cid - 1]["text"]).strip(), [])
            if len(twins) > 1:
                gold = sorted(set(twins))
                expanded += 1

        gold_text = " ".join(chunk_rows[g - 1]["text"] for g in gold)
        hit = [t for t in tokens(q) if t in gold_text]
        kind = "overlap" if hit else "no_overlap"
        kind_count[kind] += 1
        if not tokens(q):
            empty_q += 1
        q_rows.append({"query": q,
                       "gold_chunk_ids": ",".join(str(g) for g in gold),
                       "kind": kind,
                       # note 에 '예시' 를 쓰면 run_eval.py 가 조용히 건너뛴다
                       "note": src})

    queries_csv = out_dir / "queries.csv"
    with queries_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["query", "gold_chunk_ids", "kind", "note"])
        w.writeheader()
        w.writerows(q_rows)

    # source -> chunk_id 대응표. 나중에 결과를 원본과 맞춰 보려면 필요하다.
    map_csv = out_dir / "source_map.csv"
    with map_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chunk_id", "source"])
        for src, cid in sorted(src_to_id.items(), key=lambda x: x[1]):
            w.writerow([cid, src])

    # ---- 보고 ---------------------------------------------------------------
    print()
    print(f"  청크 {len(chunk_rows)}개  -> {chunks_csv}")
    print(f"  질의 {len(q_rows)}개  -> {queries_csv}")
    print(f"  대응표          -> {map_csv}")
    print(f"  kind: overlap {kind_count['overlap']}"
          f" · no_overlap {kind_count['no_overlap']}")
    if missing_src:
        print(f"  [!] 정답 source 가 코퍼스에 없어 버린 질의 {missing_src}개")
    if empty_q:
        print(f"  [!] 토큰이 없는 질의 {empty_q}개")
    if expanded:
        print(f"  정답을 쌍둥이까지 확장한 질의 {expanded}개")
    elif not args.gold_includes_duplicates:
        would = sum(1 for r in q_rows
                    for g in [int(r["gold_chunk_ids"].split(",")[0])]
                    if len(by_text.get(
                        re.sub(r"\s+", " ", chunk_rows[g - 1]["text"]).strip(),
                        [])) > 1)
        if would:
            print(f"  참고 — 본문이 같은 쌍둥이가 있는 질의 {would}개."
                  " --gold-includes-duplicates 로 정답에 포함할 수 있다")

    if kind_count["no_overlap"] == 0:
        print("\n  [!] no_overlap 이 0개다. 질의가 정답 본문의 낱말을 늘 포함한다.")
        print("      뜻으로만 찾는 능력을 재지 못한다. 점수가 높게 나올 것이다.")
    print()
    print("다음 순서")
    print(f"  python check_queries.py --chunks {chunks_csv} --queries {queries_csv}")
    print(f"  python run_eval.py --chunks {chunks_csv} --queries {queries_csv}"
          " --only KURE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
