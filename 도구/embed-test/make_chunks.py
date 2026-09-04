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

    # 파일명 순서로 청크 번호를 매기므로 새 문서가 중간에 끼어들면
    # 기존 번호가 전부 밀리고 queries.csv 의 gold_chunk_ids 가 어긋난다.
    # 파일명에 두 자리 숫자를 붙여 순서를 고정하고, doc 칸에는 그 접두어를
    # 떼고 적는다. 새 문서는 큰 번호를 붙여 뒤에 놓으면 기존 번호가 보존된다.
    #
    #   01_기초과학연구원...    ->  청크   1 ~   6
    #   02_[수의시담] 중앙보훈...->  청크   7 ~  39
    #   ...
    #   06_새로 받은 공고        ->  청크 128 부터   기존 번호 안 밀린다
    docs = []
    for path in sorted(CORPUS.iterdir()):
        if path.suffix.lower() not in (".txt", ".md"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            docs.append((strip_order_prefix(path.stem), text))

    if not docs:
        print(f"corpus 안에 읽을 파일이 없다: {CORPUS}", file=sys.stderr)
        sys.exit(1)
    return docs


def strip_order_prefix(stem: str) -> str:
    """파일명 앞의 정렬용 숫자 접두어를 뗀다.

    `01_한국지역난방공사_...` -> `한국지역난방공사_...`
    접두어가 없으면 그대로 돌려준다. 결과서와 results_detail.csv 의
    문서명이 접두어 때문에 달라지는 것을 막기 위한 것이다.
    """
    import re
    return re.sub(r"^\d{1,3}[_\-. ]+", "", stem)


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


def split_oversized(block: str, target: int, hard_max: int) -> list[str]:
    """상한을 넘는 덩어리를 쪼갠다.

    표      행 단위로 나누고 머리행을 각 조각에 복제한다. 머리행이 없으면
            어느 값이 어느 열인지 알 수 없어 조각이 뜻을 잃는다.
    본문    줄 단위로 모은다. 한 줄이 그것도 넘으면 문장 부호로 나눈다.
    최후    그래도 넘으면 글자 수로 자른다. 잘렸다는 사실이 드러나는 편이
            조용히 뒤가 사라지는 것보다 낫다.
    """
    lines = block.split("\n")
    table = [i for i, ln in enumerate(lines) if ln.strip().startswith("|")]

    # 마크다운 표 — 파이프로 시작하는 줄이 3개 이상이면 표로 본다.
    if len(table) >= 3:
        head = [lines[i] for i in table[:2]]          # 머리행 + 구분행
        head_len = sum(len(h) + 1 for h in head)
        body = [lines[i] for i in table[2:]]
        outside = [ln for i, ln in enumerate(lines) if i not in table]

        out, cur = [], []
        for row in body:
            if cur and head_len + sum(len(r) + 1 for r in cur) + len(row) > target:
                out.append("\n".join(head + cur))
                cur = []
            cur.append(row)
        if cur:
            out.append("\n".join(head + cur))

        # 표 밖의 글(제목 등)은 첫 조각 앞에 붙인다. 버리지 않는다.
        lead = "\n".join(x for x in outside if x.strip())
        if lead and out:
            out[0] = lead + "\n" + out[0]
        elif lead:
            out = [lead]
        return out or [block]

    # 본문 — 줄 단위로 모은다
    out, cur, size = [], [], 0
    for ln in lines:
        if size and size + len(ln) > target:
            out.append("\n".join(cur))
            cur, size = [], 0
        # 기준이 hard_max 가 아니라 target 이다. hard_max 로 두면 목표는
        # 500자인데 1,199자 줄이 그대로 통과한다. 실제로 1,080자 청크가
        # 나왔고 검사가 그것을 잡았다.
        if len(ln) > target:
            if cur:
                out.append("\n".join(cur))
                cur, size = [], 0
            out.extend(split_sentences(ln, target, hard_max))
            continue
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        out.append("\n".join(cur))
    return [c for c in out if c.strip()] or [block]


def split_sentences(line: str, target: int, hard_max: int) -> list[str]:
    """한 줄이 너무 길 때 문장 부호로 나눈다.

    한국어 공고문은 '~한다.' '~함' '~있음' 으로 끝나는 경우가 많아
    마침표만 보면 안 나뉜다. 세미콜론과 가운뎃점 목록도 경계로 쓴다.
    """
    parts = re.split(r"(?<=[.。!?])\s+|(?<=다\.)\s*|(?<=[함음됨])\s+|\s*;\s*",
                     line)
    parts = [p for p in parts if p and p.strip()]

    out, cur, size = [], [], 0
    for p in parts:
        if size and size + len(p) > target:
            out.append(" ".join(cur))
            cur, size = [], 0
        if len(p) >= hard_max:                 # 최후 — 글자 수로 자른다
            if cur:
                out.append(" ".join(cur))
                cur, size = [], 0
            for i in range(0, len(p), target):
                out.append(p[i:i + target])
            continue
        cur.append(p)
        size += len(p) + 1
    if cur:
        out.append(" ".join(cur))
    return [c for c in out if c.strip()] or [line]


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

        # 혼자서도 상한을 넘는 덩어리는 쪼갠다.
        #
        # 전에는 그대로 뒀다. 표를 자르지 않으려는 의도였는데, 그러면 한
        # 청크가 4,789자까지 나온다. e5 계열은 최대 입력이 512 토큰이라
        # 뒤가 조용히 잘리고 그 모델만 억울하게 진다. 접두어 규칙을 신경 쓴
        # 것과 같은 종류의 공정성 문제다.
        #
        # 결정사항은 "표는 행 단위로 자르고 머리행 복제" 였고 "표를 통째로
        # 유지" 는 기각했는데 코드가 기각한 쪽이었다. 결정에 맞춘다.
        # 기능명세서 RAG-01 판정 기준도 "표는 행 단위로 유지된다" 다 —
        # 표 전체가 아니라 행이 유지되는 것이다.
        if block_len >= hard_max:
            flush()
            chunks.extend(split_oversized(block, target, hard_max))
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
    parser.add_argument("--max-per-doc", type=int, default=0,
                        help="문서 하나에서 가져올 청크 수 상한. 0 이면 제한 없다. "
                             "큰 CSV 하나가 코퍼스를 지배하는 것을 막는다")
    args = parser.parse_args()

    rows = []
    chunk_id = 0
    trimmed = {}
    for doc_name, text in read_documents():
        blocks = split_paragraphs(text)
        made = 0
        for chunk in merge_to_target(blocks, args.target, args.max):
            body = chunk.strip()
            if len(body) < args.min:
                continue
            # 한 문서가 코퍼스를 지배하면 그 문서의 성격이 측정을 좌우한다.
            # 질의응답 해석사례 CSV 하나가 코퍼스의 95% 를 차지한 적이 있다.
            if args.max_per_doc and made >= args.max_per_doc:
                trimmed[doc_name] = trimmed.get(doc_name, 0) + 1
                continue
            chunk_id += 1
            made += 1
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
    longest = max((r["chars"] for r in rows), default=0)
    print(f"문서 {docs}건 -> 청크 {len(rows)}개")
    print(f"총 {total:,}자 · 평균 {total // max(len(rows), 1)}자")
    print(f"가장 긴 청크 {longest:,}자")
    print(f"저장: {OUT}")

    # ── 문서별 내역. 이걸 안 찍어서 한 문서가 코퍼스를 95% 차지한 것을
    #    한참 뒤에 알았다. 항상 보여준다.
    per = {}
    for r in rows:
        d = per.setdefault(r["doc"], [0, 0])
        d[0] += 1
        d[1] += r["chars"]
    print("\n문서별 내역")
    for doc, (cnt, ch) in sorted(per.items(), key=lambda x: -x[1][0]):
        share = cnt / len(rows) * 100
        mark = "  <- 이 문서가 코퍼스를 지배한다" if share >= 50 else ""
        cut = f" (상한으로 {trimmed[doc]}개 버림)" if doc in trimmed else ""
        print(f"  {cnt:>6,} 청크 ({share:>4.1f}%) · {ch:>10,}자   "
              f"{doc[:44]}{cut}{mark}")

    # ── 경고 세 가지 ─────────────────────────────────────────────────────
    warn = []
    if per:
        top_doc, (top_cnt, _) = max(per.items(), key=lambda x: x[1][0])
        if top_cnt / len(rows) >= 0.5:
            warn.append(
                f"한 문서가 청크의 {top_cnt / len(rows) * 100:.0f}% 다 "
                f"({top_doc[:34]}).\n"
                f"    그 문서의 성격이 측정을 좌우한다. "
                f"--max-per-doc 로 상한을 두는 것을 생각해라.")

    over = [r for r in rows if r["chars"] > 1000]
    if over:
        warn.append(
            f"1,000자를 넘는 청크가 {len(over)}개다 (최대 {longest:,}자).\n"
            f"    e5 계열은 최대 입력이 512 토큰이라 뒤가 조용히 잘린다.\n"
            f"    그 모델만 억울하게 지므로 비교가 공정하지 않다.\n"
            f"    --max 를 줄이거나 원본에서 표를 손봐라.")

    if len(rows) > 2000:
        est_local = len(rows) * 0.4 / 60
        warn.append(
            f"청크가 {len(rows):,}개다. 로컬 1024 모델 하나에 "
            f"약 {est_local:.0f}분, 5개면 {est_local * 5:.0f}분이 걸린다.\n"
            f"    API 는 호출 한도까지 겹쳐 훨씬 오래 걸린다. "
            f"500~1,000개로 줄이는 것이 좋다.")

    if warn:
        print("\n" + "!" * 66)
        for w in warn:
            print(f"  주의 — {w}")
        print("!" * 66)

    print("\n다음: python make_queries.py")


if __name__ == "__main__":
    main()
