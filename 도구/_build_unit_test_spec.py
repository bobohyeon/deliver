# -*- coding: utf-8 -*-
"""단위테스트명세서(md)를 xlsx 한 장으로 만든다.

이 파일의 책임: `산출물/단위테스트명세서.md` 의 표를 그대로 읽어 엑셀로 만든다.
  이전 미니 프로젝트 명세서와 같은 열 구성(시험일자·CASE·순번·절차·테스트 데이터·
  시험결과·Y/N·결함/이상 내용)을 그대로 쓴다 — 팀이 이미 익숙한 형식이라서다.
  CASE 열은 같은 값이 이어지면 첫 행에만 채우고 뒤는 비운다(md 표와 동일하게).
다른 파일과의 관계: `도구/_build_integration_test_spec.py` 와 xlsx 유틸(zip+OOXML
  직접 생성)을 그대로 공유한다. 소스 md 가 갱신되면 이 스크립트를 다시 돌리면
  된다.
Spring 비교: 없음 — 순수 문서 변환 스크립트다.

사용:
    python3 도구/_build_unit_test_spec.py
"""

import pathlib
import zipfile
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "산출물" / "단위테스트명세서.md"
OUT = ROOT / "산출물" / "단위테스트명세서.xlsx"

TITLE = "Tasqra 단위테스트명세서"
SUBTITLE = "관리/기능명세서.md(v5) 13개 영역을 CASE 로 묶음 · 시험일자·시험결과·Y/N·결함내용은 수기 작성"

HEADER = ["시험일자", "CASE", "순번", "절차", "테스트 데이터", "시험결과", "Y/N", "결함/이상 내용"]

WIDTHS = [(1, 12), (2, 14), (3, 6), (4, 34), (5, 20), (6, 30), (7, 6), (8, 30)]

# 4=위정렬+줄바꿈, 5=가운데정렬+줄바꿈.
COL_STYLE = [5, 4, 5, 4, 4, 4, 5, 4]


def parse_md():
    text = SRC.read_text(encoding="utf-8")
    rows = []
    in_table = False
    for line in text.split("\n"):
        line = line.rstrip()
        if line.startswith("|---|---|---|---|---|---|---|---|"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        if line.startswith("| 시험일자 |"):
            continue
        cells = [c.strip() for c in line.split("|")]
        assert cells[0] == "" and cells[-1] == "", f"표 형식이 아니다: {line[:60]}"
        cells = cells[1:-1]
        if len(cells) != 8:
            raise SystemExit(f"칸이 {len(cells)}개다(8개여야 한다) — {line[:60]}")
        rows.append(cells)
    return rows


def clean(text):
    return text.replace("~~", "")


# ─────────────────────────────────────────────── xlsx 유틸 (통합기능테스트명세서 도구와 동일)
def col_letter(idx):
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_xml(row, col, value, style=0):
    ref = f"{col_letter(col)}{row}"
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>')


def sheet_xml(rows, widths=None, freeze=None, autofilter=None):
    cols = ""
    if widths:
        cols = "<cols>" + "".join(
            f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>'
            for c, w in widths) + "</cols>"

    body = []
    for rnum, (height, cells) in enumerate(rows, start=1):
        h = f' ht="{height}" customHeight="1"' if height else ""
        cs = "".join(cell_xml(rnum, c, v, s) for c, v, s in cells)
        body.append(f'<row r="{rnum}"{h}>{cs}</row>')

    pane = ""
    if freeze:
        top_left, xsplit, ysplit = freeze
        pane = (f'<pane xSplit="{xsplit}" ySplit="{ysplit}" topLeftCell="{top_left}" '
                f'activePane="bottomRight" state="frozen"/>')

    af = f'<autoFilter ref="{autofilter}"/>' if autofilter else ""

    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
            f'{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16.5"/>'
            f'{cols}<sheetData>{"".join(body)}</sheetData>{af}'
            '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" '
            'header="0.3" footer="0.3"/>'
            '</worksheet>')


STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="6">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="15"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="4">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF000000"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF6F6F6"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFC0C0C0"/></left>
<right style="thin"><color rgb="FFC0C0C0"/></right>
<top style="thin"><color rgb="FFC0C0C0"/></top>
<bottom style="thin"><color rgb="FFC0C0C0"/></bottom>
<diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="6">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                 '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                 '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                 '</Types>')

ROOT_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
             '</Relationships>')

WORKBOOK = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="단위테스트" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>')

WB_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
           '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
           '</Relationships>')


def build(rows):
    sheet = []
    sheet.append((26, [(1, TITLE, 1)]))
    sheet.append((30, [(1, SUBTITLE, 3)]))
    sheet.append((6, []))
    sheet.append((30, [(c, name, 2) for c, name in enumerate(HEADER, start=1)]))

    for cells in rows:
        cleaned = [clean(c) for c in cells]
        sheet.append((None, [(c, v, COL_STYLE[c - 1]) for c, v in enumerate(cleaned, start=1)]))

    last = len(sheet)
    return sheet_xml(sheet, widths=WIDTHS, freeze=("A5", 0, 4), autofilter=f"A4:H{last}")


def main():
    rows = parse_md()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels", WB_RELS)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/worksheets/sheet1.xml", build(rows))

    print(f"  {OUT.relative_to(ROOT)}")
    print(f"  행 {len(rows)}건 · {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
