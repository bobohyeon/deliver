# =============================================================================
# 이 파일의 책임: 원본 문서를 corpus/ 에 넣을 텍스트(.md)로 바꾼다.
#   .pdf   PyMuPDF 로 텍스트를 뽑는다. 본구현과 같은 도구를 쓴다
#   .hwpx  zip+XML 을 풀어 문단·표를 텍스트로 (이미지 OCR 은 제외)
#   .csv   행을 읽을 수 있는 블록으로. 표 데이터를 검색 대상으로 만든다
#   .txt   그대로 복사
#   .hwp   변환할 수 없다. 안내만 출력한다
# 다른 파일과의 관계: input/ 에 원본을 넣고 실행하면 corpus/ 에 .md 가 생긴다.
#   그 다음 make_chunks.py 가 청크로 쪼갠다.
#   .hwpx 파싱은 Tasqra 본구현의 app/extractors/hwpx_extractor.py 와 같은
#   구조다. 여기서는 이미지 OCR 을 빼서 의존을 없앴다.
# Spring 비교: 배치의 ItemReader 어댑터 계층이다. 입력 형식마다 다른 리더를
#   두고 같은 출력(텍스트)으로 맞춘다. 본구현의 ExtractorRegistry 와 같은 역할.
#
# .hwp 를 지원하지 않는 이유
#   .hwp 는 OLE 기반 바이너리이고 .hwpx 는 zip+XML 이다. 완전히 다른 형식이다.
#   .hwp 를 파이썬으로 여는 라이브러리가 있지만 문서에 따라 실패하고, 표가
#   깨지는 경우가 많다. 한글 프로그램에서 저장하는 편이 확실하다.
#   실행하면 변환 방법을 안내한다.
# =============================================================================

import argparse
import csv
import pathlib
import re
import sys
import zipfile
from xml.etree import ElementTree as ET


# ── .pdf ─────────────────────────────────────────────────────────────────────

def read_pdf(path: pathlib.Path) -> str:
    """PDF 에서 텍스트를 뽑는다. 페이지 사이에 구분 제목을 넣는다.

    본구현(app/extractors/pdf_extractor.py)도 PyMuPDF 를 쓴다. 같은 도구로
    뽑으므로 여기서 잘 나오면 실제 파이프라인에서도 잘 나온다.

    나라장터 공고 화면을 인쇄한 PDF 는 텍스트 층이 있어 OCR 이 필요 없다.
    스캔한 PDF 라면 글자가 거의 안 나오는데, 그때는 본구현의 OCR 경로를
    써야 하므로 이 도구로는 처리하지 않는다.
    """
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf   # 옛 이름
        except ImportError:
            raise ValueError(
                "PyMuPDF 가 없다. pip install pymupdf") from None

    blocks = []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                blocks.append(f"## {number}쪽\n\n{text}")

    if not blocks:
        raise ValueError(
            "텍스트가 없다. 스캔한 PDF 로 보인다 (OCR 이 필요하다)")
    return "\n\n".join(blocks)

ROOT = pathlib.Path(__file__).resolve().parent
INPUT = ROOT / "input"
CORPUS = ROOT / "corpus"

_SECTION = re.compile(r"Contents/section(\d+)\.xml")


# ── .hwpx ────────────────────────────────────────────────────────────────────

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element, name: str) -> list:
    return [c for c in element if _local(c.tag) == name]


def _text_of(node) -> str:
    """t 요소의 텍스트. 탭·줄바꿈 자식을 살린다."""
    parts = []
    if node.text:
        parts.append(node.text)
    for child in node:
        name = _local(child.tag)
        if name == "tab":
            parts.append("\t")
        elif name in {"lineBreak", "br"}:
            parts.append("\n")
        elif child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _paragraph(paragraph) -> list[str]:
    out = []
    for run in _children(paragraph, "run"):
        for element in run:
            name = _local(element.tag)
            if name == "t":
                text = _text_of(element).strip()
                if text:
                    out.append(text)
            elif name == "tbl":
                table = _table(element)
                if table:
                    out.append(table)
    return out


def _table(table) -> str:
    """표를 파이프로 구분한 줄로 만든다.

    make_chunks.py 가 이 형태를 표로 인식해 중간에서 끊지 않는다.
    항목과 금액이 분리되면 뜻이 사라지기 때문이다.
    """
    rows = []
    for row in _children(table, "tr"):
        cells = []
        for cell in _children(row, "tc"):
            texts = []
            for sub in _children(cell, "subList"):
                for para in _children(sub, "p"):
                    texts.extend(_paragraph(para))
            cells.append(" ".join(texts).strip())
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def read_hwpx(path: pathlib.Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            (n for n in archive.namelist() if _SECTION.fullmatch(n)),
            key=lambda n: int(_SECTION.fullmatch(n).group(1)),
        )
        if not names:
            raise ValueError("HWPX 본문 section 을 찾을 수 없다")

        blocks = []
        for name in names:
            root = ET.fromstring(archive.read(name))
            for paragraph in _children(root, "p"):
                blocks.extend(_paragraph(paragraph))
    return "\n\n".join(blocks)


# ── .csv ─────────────────────────────────────────────────────────────────────

def read_csv_as_blocks(path: pathlib.Path, rows_per_block: int) -> str:
    """CSV 를 검색 가능한 텍스트 블록으로 바꾼다.

    낙찰현황·준공정보처럼 행이 곧 레코드인 데이터는 표로 붙여두면 검색이
    안 된다. 행마다 "열이름: 값" 형태로 풀어야 의미 검색이 걸린다.
    그렇게 만든 블록이 RAG-12(유사 사업 단가 선례 검색)의 실제 자료가 된다.
    """
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            with path.open(encoding=encoding, newline="") as f:
                rows = list(csv.DictReader(f))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("인코딩을 읽을 수 없다 (utf-8 · cp949 시도함)")

    if not rows:
        raise ValueError("내용이 비어 있다")

    # 값이 전부 빈 열은 버린다. 공공 데이터에 빈 열이 흔하다.
    keys = [k for k in rows[0].keys()
            if k and any((r.get(k) or "").strip() for r in rows)]

    blocks = [f"# {path.stem}", f"열: {' · '.join(keys)}", ""]

    for start in range(0, len(rows), rows_per_block):
        group = rows[start:start + rows_per_block]
        lines = [f"## {start + 1}~{start + len(group)}행"]
        for offset, row in enumerate(group):
            if rows_per_block > 1:
                lines.append(f"[{start + offset + 1}행]")
            for key in keys:
                value = (row.get(key) or "").strip()
                if value:
                    lines.append(f"{key}: {value}")
            lines.append("")
        blocks.append("\n".join(lines).rstrip())

    return "\n\n".join(blocks)


# ── 실행 ─────────────────────────────────────────────────────────────────────

HWP_GUIDE = """
  .hwp 는 이 스크립트로 변환할 수 없다. OLE 바이너리라 .hwpx(zip+XML)와
  형식이 다르다.

  한글 프로그램에서 여는 방법 두 가지 — 위쪽이 낫다.

    1. 다른 이름으로 저장 -> 파일 형식 "한글 문서 (*.hwpx)"
       본구현의 HWPX 추출기로도 뽑을 수 있어 실제 파이프라인 검증까지 된다.

    2. 다른 이름으로 저장 -> 파일 형식 "텍스트 문서 (*.txt)"
       가장 단순하다. 표가 탭으로 남는다.

  한글 프로그램이 없으면 — 이게 가장 확실하다
    나라장터 공고 상세 화면에서 브라우저 인쇄(Ctrl+P) -> PDF 로 저장.
    화면에 보이는 표가 그대로 텍스트로 남고, 본구현도 PDF 를 처리하므로
    파이프라인 검증까지 된다. 첨부 .hwp 를 못 열어도 공고 본문은 얻는다.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="원본 문서를 corpus/ 용 텍스트로 바꾼다")
    parser.add_argument("--rows-per-block", type=int, default=1,
                        help="CSV 몇 행을 한 블록으로 묶을지 (기본 1)")
    args = parser.parse_args()

    INPUT.mkdir(exist_ok=True)
    CORPUS.mkdir(exist_ok=True)

    files = [p for p in sorted(INPUT.iterdir()) if p.is_file()]
    if not files:
        print(f"input 폴더가 비어 있다: {INPUT}")
        print("원본 문서를 넣고 다시 실행해라. (.pdf · .hwpx · .csv · .txt · .md)")
        return

    converted = skipped = 0
    hwp_found = False

    for path in files:
        suffix = path.suffix.lower()
        target = CORPUS / f"{path.stem}.md"

        try:
            if suffix == ".pdf":
                text = read_pdf(path)
            elif suffix == ".hwpx":
                text = read_hwpx(path)
            elif suffix == ".csv":
                text = read_csv_as_blocks(path, args.rows_per_block)
            elif suffix in (".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="replace")
            elif suffix == ".hwp":
                print(f"  건너뜀  {path.name}  (.hwp 는 변환 불가)")
                hwp_found = True
                skipped += 1
                continue
            else:
                print(f"  건너뜀  {path.name}  (지원하지 않는 형식)")
                skipped += 1
                continue
        except Exception as exc:
            print(f"  실패    {path.name}  {type(exc).__name__}: {exc}")
            skipped += 1
            continue

        body = text.strip()
        if len(body) < 50:
            print(f"  건너뜀  {path.name}  (내용이 너무 짧다: {len(body)}자)")
            skipped += 1
            continue

        target.write_text(body, encoding="utf-8")
        print(f"  변환    {path.name}  ->  corpus/{target.name}  ({len(body):,}자)")
        converted += 1

    print()
    print(f"변환 {converted}건 · 건너뜀 {skipped}건")

    if hwp_found:
        print(HWP_GUIDE)

    if converted:
        print("다음: python make_chunks.py")


if __name__ == "__main__":
    main()
