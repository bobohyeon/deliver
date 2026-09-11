# =============================================================================
# 이 파일의 책임: 질의·정답 평가셋을 사람이 쉽게 만들 수 있게 돕는다.
#   (1) chunks_worksheet.csv — 청크 번호와 미리보기. 엑셀로 열어 보면서 질의를
#       쓰기 위한 참고표다.
#   (2) queries.csv — 비어 있는 평가셋 템플릿. 예시 2줄이 들어 있다.
#   (3) --prompt 옵션 — LLM 에 붙여넣어 질의 초안을 받는 프롬프트를 출력한다.
# 다른 파일과의 관계: make_chunks.py 의 chunks.csv 를 읽고, run_eval.py 가
#   queries.csv 를 읽어 채점한다.
# Spring 비교: 테스트 픽스처를 만드는 도구다. src/test/resources 에 넣을
#   expected 데이터를 손으로 만들기 쉽게 돕는 스캐폴딩에 해당한다.
#
# 왜 질의를 두 종류로 나누나
#   overlap      질의의 단어가 청크에 그대로 있다. 키워드 검색으로도 찾힌다.
#   no_overlap   질의의 단어가 청크에 하나도 없다. 의미 검색만 찾을 수 있다.
#
#   RAG-04 의 완료 판정 기준이 "글자가 하나도 겹치지 않는 질의로 찾아진다" 다.
#   no_overlap 에서 이겨야 임베딩을 쓰는 근거가 생긴다. overlap 만 재면
#   기존 ILIKE 검색과 차이가 안 보인다.
# =============================================================================

import argparse
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CHUNKS = ROOT / "chunks.csv"
WORKSHEET = ROOT / "chunks_worksheet.csv"
QUERIES = ROOT / "queries.csv"

PREVIEW_CHARS = 160

PROMPT_TEMPLATE = """아래 문단들을 읽고 각 문단마다 질문 2개를 만들어라.

규칙
- 1번 질문: 문단에 나온 단어를 그대로 써서 묻는다.
- 2번 질문: 문단의 단어를 하나도 쓰지 않고 같은 뜻을 묻는다.
  (예: 문단이 "특급기술자 3인월 x 9,500,000원" 이면
        1번 "특급기술자 단가는 얼마인가"
        2번 "인건비를 얼마로 잡았나")
- 질문은 한 문장으로 짧게. 물음표 없이 명사구도 좋다.
- 그 문단을 읽어야만 답할 수 있는 질문이어야 한다. 일반 상식 질문은 안 된다.

출력 형식 — 다른 설명 없이 아래 형식으로만
{chunk_id}\t1번질문\toverlap
{chunk_id}\t2번질문\tno_overlap

문단
{blocks}
"""


def load_chunks() -> list[dict]:
    if not CHUNKS.exists():
        print(f"chunks.csv 가 없다: {CHUNKS}", file=sys.stderr)
        print("먼저 python make_chunks.py 를 실행해라.", file=sys.stderr)
        sys.exit(1)
    with CHUNKS.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= limit else flat[:limit] + " …"


def write_worksheet(chunks: list[dict]) -> None:
    with WORKSHEET.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["chunk_id", "doc", "chars", "preview",
                         "질의_단어겹침", "질의_단어안겹침"])
        for row in chunks:
            writer.writerow([row["chunk_id"], row["doc"], row["chars"],
                             preview(row["text"]), "", ""])
    print(f"작성용 워크시트: {WORKSHEET}")
    print("  엑셀로 열어서 오른쪽 두 칸에 질의를 쓰면 된다.")
    print("  모든 청크를 채울 필요 없다. 15개 정도만 골라 채워도 방향이 보인다.")


def write_queries_template() -> None:
    if QUERIES.exists():
        print(f"queries.csv 가 이미 있어 건드리지 않았다: {QUERIES}")
        return
    with QUERIES.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "gold_chunk_ids", "kind", "note"])
        writer.writerow(["특급기술자 단가", "7", "overlap", "예시 — 지우고 쓰세요"])
        writer.writerow(["인건비를 얼마로 잡았나", "7", "no_overlap",
                         "예시 — 정답이 여러 개면 7,8 처럼 쉼표로"])
    print(f"평가셋 템플릿: {QUERIES}")


def print_prompt(chunks: list[dict], count: int, start: int) -> None:
    picked = chunks[start:start + count]
    if not picked:
        print("해당 범위에 청크가 없다.", file=sys.stderr)
        sys.exit(1)

    blocks = []
    for row in picked:
        blocks.append(f"[chunk_id={row['chunk_id']}]\n{row['text']}\n")

    print(PROMPT_TEMPLATE.format(
        chunk_id="chunk_id",
        blocks="\n".join(blocks),
    ))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="질의·정답 평가셋 작성을 돕는다")
    parser.add_argument("--prompt", type=int, metavar="N",
                        help="청크 N개에 대한 LLM 프롬프트를 출력한다")
    parser.add_argument("--start", type=int, default=0,
                        help="--prompt 시작 위치 (기본 0)")
    args = parser.parse_args()

    chunks = load_chunks()

    if args.prompt:
        print_prompt(chunks, args.prompt, args.start)
        return

    write_worksheet(chunks)
    write_queries_template()
    print()
    print(f"청크 {len(chunks)}개")
    print()
    print("질의 만드는 요령")
    print("  단어겹침    청크의 단어를 그대로 쓴다. 키워드 검색으로도 찾힌다")
    print("  단어안겹침  청크의 단어를 하나도 쓰지 않는다. 이게 핵심이다")
    print()
    print("LLM 으로 초안을 받고 싶으면")
    print("  python make_queries.py --prompt 10")
    print("  출력을 복사해 아무 LLM 에 붙여넣고, 결과를 검수해서 queries.csv 에 넣는다")
    print()
    print("다음: queries.csv 를 채우고 python run_eval.py")


if __name__ == "__main__":
    main()
