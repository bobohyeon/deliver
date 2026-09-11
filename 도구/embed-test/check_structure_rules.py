# =============================================================================
# 이 파일의 책임: Tasqra 의 structure.py 자동 판정 규칙이 실제 문서에서 얼마나
#   맞는지 잰다. 정답은 KoViDoRe v2 Cybersecurity 데이터의 elements 컬럼에 든
#   상용 문서 파서 라벨을 쓴다 (한국인터넷진흥원 보고서 17건 · 1,150페이지).
#
# 다른 파일과의 관계: 규칙 본체는 Tasqra 레포의
#   backend/app/extractors/structure.py 다. 여기에 사본을 두지 않고 파일 경로로
#   불러온다. 사본을 두면 반드시 어긋난다.
#
# Spring 비교: 운영 코드의 규칙 클래스를 그대로 불러와 실제 데이터로 재는
#   특성 테스트(characterization test) 자리다. 통과·실패가 아니라 수치를 낸다.
#
# 왜 이 데이터를 쓰나
#   검색 성능 평가용으로는 도메인이 안 맞아 넘겼다(관리/RAG_평가데이터셋_선별기준.md).
#   그러나 "조항 번호로 시작하는 제목을 알아보는가" 는 도메인과 무관하다.
#   라벨을 정답으로 쓰는 것은 별개의 정당한 용도다.
#
# 정직하게 볼 것
#   1. 마크다운 제목 표기(#)를 떼고 잰다. 안 떼면 파서가 붙인 표기를 우리가
#      맞히는 셈이라 정확도가 부풀려진다.
#   2. elements 라벨에는 좌표가 없다. 그래서 머리글·바닥글은 use_position=False
#      로 재고, 이 조건에서는 오탐이 늘어난다(숫자만 다른 줄이 묶인다).
#      위치 조건은 실제 문서로 따로 봐야 한다.
#
# 사용법
#   python check_structure_rules.py
#   python check_structure_rules.py --structure "C:\dev\Tesqra\Tasqra\backend\app\extractors\structure.py"
# =============================================================================

import argparse
import ast
import importlib.util
import pathlib
import re
import sys
from collections import Counter, defaultdict

REPO = "whybe-choi/kovidore-v2-cybersecurity-beir"
DEFAULT_STRUCTURE = r"C:\dev\Tesqra\Tasqra\backend\app\extractors\structure.py"

ROOT = pathlib.Path(__file__).resolve().parent

# 파서가 붙인 마크다운 표기를 떼는 규칙.
# 이걸 안 떼면 우리 _MARKDOWN 정규식이 공짜로 맞혀서 정확도가 부풀려진다.
_MD_HEADING = re.compile(r"^\s*#{1,6}\s*")
_MD_BOLD = re.compile(r"\*\*([^*]*)\*\*")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")


def to_plain_text(markdown: str) -> str:
    text = _MD_LINK.sub(r"\1", markdown or "")
    text = _MD_BOLD.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = _MD_HEADING.sub("", text)
    return " ".join(text.split()).strip()


def load_structure(path: str):
    file = pathlib.Path(path)
    if not file.exists():
        sys.exit(
            f"structure.py 를 찾을 수 없다: {file}\n"
            f"--structure 로 경로를 지정하라."
        )
    spec = importlib.util.spec_from_file_location("structure", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_labeled_elements():
    """(doc_id, page, category, plain_text) 목록을 만든다."""
    try:
        import pyarrow.parquet as pq
        from huggingface_hub import HfFileSystem, list_repo_files
    except ImportError:
        sys.exit("pip install datasets huggingface_hub pyarrow 가 필요하다.")

    shards = [
        f for f in list_repo_files(REPO, repo_type="dataset")
        if f.startswith("corpus/") and f.endswith(".parquet")
    ]
    if not shards:
        sys.exit("corpus parquet 을 찾을 수 없다.")

    fs = HfFileSystem()
    rows = []
    for shard in sorted(shards):
        pf = pq.ParquetFile(fs.open("datasets/" + REPO + "/" + shard))
        table = pf.read(columns=["doc_id", "page_number_in_doc", "elements"])
        for row in table.to_pylist():
            try:
                items = ast.literal_eval(row["elements"])
            except (ValueError, SyntaxError):
                continue
            for item in items:
                category = item.get("category")
                content = item.get("content") or {}
                text = to_plain_text(content.get("markdown") or "")
                if category and text:
                    rows.append((row["doc_id"], row["page_number_in_doc"], category, text))
    return rows


def rate(hit: int, total: int) -> str:
    return f"{hit / total * 100:5.1f}%  ({hit}/{total})" if total else "     -"


def report_heading(structure, rows):
    print("=" * 66)
    print("detect_heading() — 정답은 파서의 heading 라벨")
    print("=" * 66)

    positives = [t for _, _, c, t in rows if c.startswith("heading")]
    negatives = [t for _, _, c, t in rows if c == "paragraph"]

    tp = sum(1 for t in positives if structure.detect_heading(t))
    fp = sum(1 for t in negatives if structure.detect_heading(t))

    print(f"  재현율 (heading 을 맞힌 비율)   {rate(tp, len(positives))}")
    print(f"  오탐률 (paragraph 를 제목으로)  {rate(fp, len(negatives))}")
    if tp + fp:
        print(f"  정밀도 (제목이라 한 것 중 참)   {rate(tp, tp + fp)}")

    print()
    print("  놓친 heading 예시 (번호가 없어 판정 못 하는 것이 대부분일 것)")
    missed = [t for t in positives if not structure.detect_heading(t)]
    for t in missed[:8]:
        print(f"    - {t[:70]}")

    print()
    print("  오탐 예시 (이게 늘면 본문이 조각난다)")
    wrong = [t for t in negatives if structure.detect_heading(t)]
    for t in wrong[:8]:
        print(f"    - {t[:70]}")
    return len(missed), len(wrong)


def report_header_footer(structure, rows):
    print()
    print("=" * 66)
    print("detect_header_footer() — 정답은 파서의 header·footer 라벨")
    print("=" * 66)
    print("  주의 — elements 라벨에 좌표가 없어 use_position=False 로 잰다.")
    print("         위치 조건 없이 재는 것이므로 오탐이 실제보다 높게 나온다.")
    print()

    by_doc = defaultdict(lambda: defaultdict(list))
    for doc_id, page, category, text in rows:
        by_doc[doc_id][page].append((category, text))

    tp = fn = fp = tn = 0
    for doc_id, page_map in by_doc.items():
        page_numbers = sorted(page_map)
        pages = [[(t, None) for _, t in page_map[p]] for p in page_numbers]
        found = structure.detect_header_footer(pages, use_position=False)
        for page_index, page_number in enumerate(page_numbers):
            for element_index, (category, _) in enumerate(page_map[page_number]):
                is_hf = category in ("header", "footer")
                predicted = (page_index, element_index) in found
                if is_hf and predicted:
                    tp += 1
                elif is_hf and not predicted:
                    fn += 1
                elif not is_hf and predicted:
                    fp += 1
                else:
                    tn += 1

    print(f"  재현율 (header·footer 를 맞힌 비율)  {rate(tp, tp + fn)}")
    print(f"  정밀도 (반복이라 한 것 중 참)        {rate(tp, tp + fp)}")
    print(f"  오탐률 (그 외를 반복으로)            {rate(fp, fp + tn)}")
    return fn, fp


def main():
    parser = argparse.ArgumentParser(description="structure.py 규칙 정확도 측정")
    parser.add_argument("--structure", default=DEFAULT_STRUCTURE)
    args = parser.parse_args()

    structure = load_structure(args.structure)
    print("규칙 파일:", args.structure)
    print("데이터 불러오는 중...")
    rows = load_labeled_elements()

    print()
    print(f"요소 {len(rows):,}개 · 문서 {len({r[0] for r in rows})}건")
    print("분류 분포")
    for category, count in Counter(c for _, _, c, _ in rows).most_common():
        print(f"    {category:<12} {count:>6,}")
    print()

    report_heading(structure, rows)
    report_header_footer(structure, rows)

    print()
    print("=" * 66)
    print("읽는 법")
    print("  오탐률이 재현율보다 중요하다. HEADING 은 is_paragraph_start 를")
    print("  강제하므로 잘못 붙으면 본문 한가운데서 단락이 끊겨 청크가 조각난다.")
    print("  놓친 것은 사람이 검수 화면에서 한 번 누르면 된다.")
    print("=" * 66)


if __name__ == "__main__":
    main()
