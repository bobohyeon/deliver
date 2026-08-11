# =============================================================================
# 이 파일의 책임: corpus/ 안의 문서를 청크로 쪼개 chunks.csv 로 만든다.
#   문단(빈 줄) 단위로 자르고, 너무 짧은 문단은 목표 길이까지 이어 붙인다.
#   표처럼 보이는 줄은 쪼개지 않고 한 청크에 유지한다.
# 다른 파일과의 관계: make_queries.py 가 이 결과로 질의 작성용 워크시트를
#   만들고, run_eval.py 가 이 청크를 임베딩해 검색 대상으로 쓴다.
#   나중에 본구현(RAG-01)의 청킹 기준을 정할 때 이 스크립트가 기준선이 된다.
# Spring 비교: 배치 전처리 단계다. Spring Batch 의 ItemReader + ItemProcessor
#   에 해당한다. 여기서는 파일을 읽어 청크 목록으로 바꾸는 것까지만 한다.
#
# 이 단계의 목적은 "정답을 만들기 쉽게" 하는 것이다.
#   청크에 번호가 붙어야 질의의 정답을 번호로 적을 수 있다. 청크를 너무 작게
#   자르면 정답이 여러 개로 흩어져 표시가 어렵고, 너무 크게 자르면 검색이
#   쉬워져서 모델 차이가 안 보인다. 400~600자가 그 사이다.
# =============================================================================

import argparse
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
OUT = ROOT / "chunks.csv"

# 표로 보이는 줄. 숫자·금액·탭·연속 공백이 많으면 표라고 본다.
# 표는 문단 중간에서 끊으면 뜻이 사라지므로 이어 붙인다.
_TABLE_LINE = re.compile(r"(\d[\d,\.]{2,})|\t|\s{3,}|[│|]")

# 새 청크의 경계로 볼 줄.
#   마크다운 제목(#), 조항 번호(제3조·1.·가.), 목록 기호.
# 제목을 경계로 넣지 않으면 짧은 문서가 통째로 한 청크가 되어, 질의의 정답을
# 문단 단위로 표시할 수 없다. 실제로 그렇게 나와서 추가했다.
_CLAUSE_START = re.compile(
    r"^\s*(#{1,6}\s|제\s*\d+\s*[조항]|[0-9]+[\.\)]\s|[가-하][\.\)]\s|[■□○●▪]\s)")


def looks_like_table(line: str) -> bool:
    return bool(_TABLE_LINE.search(line))


def read_documents() -> list[tuple[str, str]]:
    if not CORPUS.exists():
        print(f"corpus 폴더가 없다: {CORPUS}", file=sys.stderr)
        print("폴더를 만들고 .txt 또는 .md 파일을 넣어라.", file=sys.stderr)
        sys.exit(1)

    docs = []
    for path in sorted(CORPUS.iterdir()):
        if path.suffix.lower() not in (".txt", ".md"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            docs.append((path.stem, text))

    if not docs:
        print(f"corpus 안에 읽을 파일이 없다: {CORPUS}", file=sys.stderr)
        sys.exit(1)
    return docs


def split_paragraphs(text: str) -> list[str]:
    """빈 줄로 문단을 나눈다. 표로 보이는 연속 줄은 한 덩어리로 유지한다."""
    blocks: list[str] = []
    buffer: list[str] = []
    in_table = False

    for raw in text.splitlines():
        line = raw.rstrip()

        if not line.strip():
            if buffer:
                blocks.append("\n".join(buffer))
                buffer = []
            in_table = False
            continue

        is_table = looks_like_table(line)

        # 표가 끝나고 일반 문장이 시작되면 경계로 본다.
        if in_table and not is_table and buffer:
            blocks.append("\n".join(buffer))
            buffer = []

        # 조항 번호로 시작하면 새 덩어리로 본다. 표 안에서는 예외.
        if not is_table and not in_table and buffer and _CLAUSE_START.match(line):
            blocks.append("\n".join(buffer))
            buffer = []

        buffer.append(line)
        in_table = is_table

    if buffer:
        blocks.append("\n".join(buffer))
    return blocks


def is_section_head(block: str) -> bool:
    """이 덩어리가 절 제목으로 시작하는가."""
    first = block.lstrip().split("\n", 1)[0]
    return bool(re.match(r"^#{1,6}\s|^제\s*\d+\s*[조항]", first))


def merge_to_target(blocks: list[str], target: int, hard_max: int) -> list[str]:
    """짧은 덩어리를 목표 길이까지 이어 붙인다.

    절 제목(#, 제N조)에서는 목표 길이에 못 미쳐도 끊는다. 안 끊으면 짧은
    문서가 통째로 한 청크가 되어 질의의 정답을 문단 단위로 표시할 수 없다.
    실제로 그렇게 나와서 규칙을 추가했다.

    표는 쪼개지 않는다. 중간에서 끊으면 항목과 금액이 분리되어 뜻이 사라진다.
    """
    chunks: list[str] = []
    current: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal current, size
        if current:
            chunks.append("\n\n".join(current))
            current, size = [], 0

    for block in blocks:
        block_len = len(block)

        # 혼자서도 상한을 넘는 덩어리는 그대로 둔다. 표를 자르지 않기 위해서다.
        if block_len >= hard_max:
            flush()
            chunks.append(block)
            continue

        # 절 제목이 나오면 앞 내용을 끊는다. 단, 제목만 있는 청크가 생기지
        # 않도록 현재 덩어리가 제목 하나뿐이면 이어 붙인다.
        if current and is_section_head(block):
            only_head = len(current) == 1 and is_section_head(current[0])
            if not only_head:
                flush()

        if size and size + block_len > target:
            flush()

        current.append(block)
        size += block_len

    flush()
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="corpus 를 청크로 쪼갠다")
    parser.add_argument("--target", type=int, default=500,
                        help="청크 목표 글자 수 (기본 500)")
    parser.add_argument("--max", type=int, default=1200,
                        help="이 길이를 넘는 덩어리는 쪼개지 않고 그대로 둔다")
    parser.add_argument("--min", type=int, default=30,
                        help="이보다 짧은 청크는 버린다 (제목만 있는 줄 등)")
    args = parser.parse_args()

    rows = []
    chunk_id = 0
    for doc_name, text in read_documents():
        blocks = split_paragraphs(text)
        for chunk in merge_to_target(blocks, args.target, args.max):
            body = chunk.strip()
            if len(body) < args.min:
                continue
            chunk_id += 1
            rows.append({
                "chunk_id": chunk_id,
                "doc": doc_name,
                "chars": len(body),
                "text": body,
            })

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["chunk_id", "doc", "chars", "text"])
        writer.writeheader()
        writer.writerows(rows)

    docs = len({r["doc"] for r in rows})
    total = sum(r["chars"] for r in rows)
    print(f"문서 {docs}건 -> 청크 {len(rows)}개")
    print(f"총 {total:,}자 · 평균 {total // max(len(rows), 1)}자")
    print(f"가장 긴 청크 {max((r['chars'] for r in rows), default=0):,}자")
    print(f"저장: {OUT}")
    print()
    print("다음: python make_queries.py")


if __name__ == "__main__":
    main()
