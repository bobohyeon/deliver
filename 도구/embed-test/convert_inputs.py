# =============================================================================
# 이 파일의 책임: 원본 문서를 corpus/ 에 넣을 텍스트(.md)로 바꾼다.
#   .pdf   PyMuPDF 로 텍스트를 뽑는다. 본구현과 같은 도구를 쓴다
#   .hwpx  zip+XML 을 풀어 문단·표를 텍스트로 (이미지 OCR 은 제외)
#   .docx  같은 방식. 제목 스타일은 마크다운 제목으로 바꿔 청크 경계를 살린다
#   .csv   행을 읽을 수 있는 블록으로. 표 데이터를 검색 대상으로 만든다
#   .txt   그대로 복사
#   .hwp   변환할 수 없다. 안내만 출력한다
#   .doc   변환할 수 없다. .docx 로 저장하라고 안내한다
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

from __future__ import annotations   # str | None 어노테이션을 3.9 에서도 쓰려고

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
_HEADING = re.compile(r"^(?:heading|제목|개요)\s*(\d)$", re.IGNORECASE)


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


# ── .docx ────────────────────────────────────────────────────────────────────

def _docx_style(paragraph) -> str:
    """문단에 걸린 스타일 이름. 제목 문단을 찾는 데 쓴다."""
    for pPr in paragraph:
        if _local(pPr.tag) != "pPr":
            continue
        for element in pPr:
            if _local(element.tag) != "pStyle":
                continue
            for key, value in element.attrib.items():
                if _local(key) == "val":
                    return value
    return ""


def _docx_paragraph(paragraph) -> str:
    """문단의 글자를 모은다. 탭·줄바꿈을 살린다."""
    parts = []
    for element in paragraph.iter():
        name = _local(element.tag)
        if name == "t" and element.text:
            parts.append(element.text)
        elif name == "tab":
            parts.append("\t")
        elif name in {"br", "cr"}:
            parts.append("\n")
    return "".join(parts).strip()


def _docx_table(table) -> str:
    """표를 파이프로 구분한 줄로. hwpx 쪽과 같은 형태로 맞춘다."""
    rows = []
    for row in _children(table, "tr"):
        cells = []
        for cell in _children(row, "tc"):
            texts = [_docx_paragraph(p) for p in _children(cell, "p")]
            cells.append(" ".join(t for t in texts if t).strip())
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def read_docx(path: pathlib.Path) -> str:
    """DOCX 에서 문단·표를 텍스트로 뽑는다.

    .docx 는 .hwpx 와 마찬가지로 zip+XML 이라 파이썬으로 열 수 있다.
    (.doc 는 OLE 바이너리라 안 된다. .hwp 와 같은 사정이다.)

    제목 스타일이 걸린 문단은 마크다운 제목(`#`)으로 바꾼다. make_chunks.py 가
    절 제목을 청크 경계로 쓰므로, 이걸 살려야 문서 하나가 통째로 한 청크가
    되는 일을 막을 수 있다.
    """
    with zipfile.ZipFile(path) as archive:
        try:
            data = archive.read("word/document.xml")
        except KeyError:
            raise ValueError(
                "word/document.xml 이 없다 (.docx 가 아니다)") from None

    root = ET.fromstring(data)
    bodies = _children(root, "body")
    body = bodies[0] if bodies else root

    blocks = []
    for child in body:
        name = _local(child.tag)
        if name == "p":
            text = _docx_paragraph(child)
            if not text:
                continue
            match = _HEADING.match(_docx_style(child).strip())
            if match:
                level = min(int(match.group(1)), 6)
                text = f"{'#' * level} {text}"
            blocks.append(text)
        elif name == "tbl":
            table = _docx_table(child)
            if table:
                blocks.append(table)

    if not blocks:
        raise ValueError("본문에서 글자를 찾지 못했다")
    return "\n\n".join(blocks)


# ── .csv ─────────────────────────────────────────────────────────────────────

def _read_csv_rows(path: pathlib.Path) -> list[list[str]]:
    """CSV 를 행 단위 리스트로 읽는다. 인코딩을 차례로 시도한다."""
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            with path.open(encoding=encoding, newline="") as f:
                return [row for row in csv.reader(f)]
        except UnicodeDecodeError:
            continue
    raise ValueError("인코딩을 읽을 수 없다 (utf-8 · cp949 시도함)")


def _sniff_header(rows: list[list[str]], limit: int = 15) -> int:
    """헤더로 보이는 행의 위치를 찾는다.

    엑셀에서 내보낸 CSV 는 1행이 제목이고 그 아래 빈 행이 있는 경우가 많다.
    csv.DictReader 는 1행을 무조건 헤더로 보므로, 그대로 쓰면 제목 한 칸만
    열 이름이 되고 나머지 열이 이름 없는 열로 버려진다. 실제로 팀 문서를
    변환했을 때 번호 열만 남고 본문이 전부 사라졌다.

    채워진 칸이 가장 많은 행을 헤더로 본다. 동수면 앞쪽을 택한다.
    제목 행은 보통 한 칸만 차 있어서 실제 헤더에 밀린다.
    """
    best, best_filled = 0, -1
    for index, row in enumerate(rows[:limit]):
        filled = sum(1 for cell in row if (cell or "").strip())
        if filled > best_filled:
            best, best_filled = index, filled
    return best


def read_csv_as_blocks(path: pathlib.Path, rows_per_block: int,
                       header_row: int | None = None) -> str:
    """CSV 를 검색 가능한 텍스트 블록으로 바꾼다.

    낙찰현황·준공정보처럼 행이 곧 레코드인 데이터는 표로 붙여두면 검색이
    안 된다. 행마다 "열이름: 값" 형태로 풀어야 의미 검색이 걸린다.
    그렇게 만든 블록이 RAG-12(유사 사업 단가 선례 검색)의 실제 자료가 된다.

    header_row 를 주면 그 행(1부터 센다)을 헤더로 쓴다. 주지 않으면 찾는다.
    헤더 위쪽 제목 줄은 버리지 않고 문서 머리에 남긴다. "주요 결정사항 로그"
    처럼 그 자체가 검색에 쓸모 있는 정보이기 때문이다.
    """
    raw = _read_csv_rows(path)
    raw = [row for row in raw if row]           # 완전히 빈 줄만 걷어낸다
    if not raw:
        raise ValueError("내용이 비어 있다")

    if header_row is not None:
        index = header_row - 1
        if not 0 <= index < len(raw):
            raise ValueError(
                f"--header-row {header_row} 은 범위를 벗어난다 (행 {len(raw)}개)")
    else:
        index = _sniff_header(raw)

    header = [(cell or "").strip() for cell in raw[index]]
    if not any(header):
        raise ValueError(f"{index + 1}행이 헤더로 비어 있다")

    # 이름 없는 열에 자리 이름을 준다. 예전에는 버렸는데, 값이 있는 열이
    # 조용히 사라지는 사고가 났다. 버리지 않고 드러낸다.
    names, unnamed = [], 0
    for position, cell in enumerate(header, start=1):
        if cell:
            names.append(cell)
        else:
            names.append(f"열{position}")
            unnamed += 1

    records = []
    for row in raw[index + 1:]:
        if not any((cell or "").strip() for cell in row):
            continue
        padded = list(row) + [""] * (len(names) - len(row))
        records.append(dict(zip(names, padded)))

    if not records:
        raise ValueError(f"{index + 1}행을 헤더로 봤는데 그 아래 자료가 없다")

    keys = [k for k in names
            if any((r.get(k) or "").strip() for r in records)]

    print(f"    헤더 {index + 1}행 · 열 {len(keys)}개 · 자료 {len(records)}행", end="")
    if unnamed:
        print(f" · 이름 없는 열 {unnamed}개는 열N 으로 넣음", end="")
    print()

    blocks = [f"# {path.stem}"]

    # 헤더 위쪽 제목·부제를 살린다.
    for row in raw[:index]:
        line = " ".join(cell.strip() for cell in row if (cell or "").strip())
        if line:
            blocks.append(line)

    blocks += [f"열: {' · '.join(keys)}", ""]

    for start in range(0, len(records), rows_per_block):
        group = records[start:start + rows_per_block]
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
    parser.add_argument("--header-row", type=int, metavar="N",
                        help="CSV 의 N행을 헤더로 쓴다 (1부터). 안 주면 찾는다")
    parser.add_argument("--clean", action="store_true",
                        help="corpus 의 기존 .md 를 지우고 새로 만든다 "
                             "(샘플 파일은 남긴다)")
    args = parser.parse_args()

    INPUT.mkdir(exist_ok=True)
    CORPUS.mkdir(exist_ok=True)

    # ── 같은 문서가 두 벌 들어가는 것을 막는다 ──────────────────────────
    # input 에서 파일 이름을 바꾸면(예: 01_ 접두어를 붙이면) corpus 에 옛
    # 이름의 변환본이 그대로 남아 있어 같은 문서가 두 벌이 된다. 그러면
    # 같은 텍스트가 두 청크에 있고, 모델이 옛 쪽을 1위로 올려도 오답으로
    # 채점되어 측정이 오염된다. 실제로 5건이 중복됐다.
    existing = [p for p in CORPUS.glob("*.md") if "_샘플" not in p.stem]
    if existing:
        if args.clean:
            for p in existing:
                p.unlink()
            print(f"  corpus 의 기존 변환본 {len(existing)}개를 지웠다 "
                  f"(샘플은 남김)\n")
        else:
            will = {p.stem for p in INPUT.iterdir() if p.is_file()}
            stale = [p.stem for p in existing if p.stem not in will]
            print("!" * 66)
            print(f"  corpus 에 변환본이 이미 {len(existing)}개 있다.")
            if stale:
                print(f"  그중 {len(stale)}개는 지금 input 에 없는 이름이다 "
                      f"— 같은 문서가 두 벌이 될 수 있다.")
                for s in stale[:6]:
                    print(f"    {s[:56]}")
                if len(stale) > 6:
                    print(f"    ... 그리고 {len(stale) - 6}개 더")
            print("  이름을 바꿨거나 다시 만드는 것이면 --clean 을 붙여라.")
            print("!" * 66)
            print()

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
            elif suffix == ".docx":
                text = read_docx(path)
            elif suffix == ".csv":
                text = read_csv_as_blocks(path, args.rows_per_block,
                                          args.header_row)
            elif suffix in (".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="replace")
            elif suffix == ".hwp":
                print(f"  건너뜀  {path.name}  (.hwp 는 변환 불가)")
                hwp_found = True
                skipped += 1
                continue
            elif suffix == ".doc":
                print(f"  건너뜀  {path.name}  (.doc 는 변환 불가 — .docx 로 저장)")
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
