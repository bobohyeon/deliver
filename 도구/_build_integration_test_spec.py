# -*- coding: utf-8 -*-
"""통합기능테스트명세서(md)를 xlsx 한 장으로 만든다.

이 파일의 책임: `산출물/통합기능테스트명세서.md` 의 표를 그대로 읽어 엑셀로
  만든다. 기능 ID 열은 빼고 기능명만 남긴다(사용자 요청) — 팀 시트에 붙일 때
  ID 매핑까지 옮기면 한 칸 밀림 같은 사고가 나기 쉬워서다. 섹션(영역별 소제목)도
  나누지 않고 115행을 한 표로 이어 붙인다.
다른 파일과의 관계: `도구/_build_feature_spec_v5.py` 의 xlsx 유틸(zip+OOXML 직접
  생성, openpyxl 없이)을 그대로 복사해 쓴다. 소스 md 가 갱신되면 이 스크립트를
  다시 돌리면 된다 — md 를 손으로 다시 표로 옮기지 않는다.
Spring 비교: 없음 — 순수 문서 변환 스크립트다.

사용:
    python3 도구/_build_integration_test_spec.py
"""

import pathlib
import re
import zipfile
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "산출물" / "통합기능테스트명세서.md"
OUT = ROOT / "산출물" / "통합기능테스트명세서.xlsx"

TITLE = "Tasqra 통합기능테스트명세서"
SUBTITLE = "관리/기능명세서.md(v5, 115건) 기준 · 기능명 · 선행 기능은 이름으로 표기 · 수행결과·비고는 수기 작성"

HEADER = ["기능명", "선행 기능", "테스트 절차", "예상 결과", "수행결과", "비고"]

WIDTHS = [(1, 22), (2, 22), (3, 46), (4, 40), (5, 12), (6, 30)]

# 각 열 스타일(STYLES 의 cellXfs 인덱스). 4=위정렬+줄바꿈, 5=가운데정렬+줄바꿈.
COL_STYLE = [4, 4, 4, 4, 5, 4]


# ─────────────────────────────────────────────── md 파싱
ROW_PATTERN = re.compile(r"^`([A-Za-z0-9-]+)`\s+(.+)$")


def parse_md():
    """`| \`IT-xxx\` | \`FID\` 기능명 | 선행 | 절차 | 예상결과 | 수행결과 | 비고 |` 행만 골라낸다."""
    text = SRC.read_text(encoding="utf-8")
    id_to_name = {}
    raw_rows = []

    for line in text.split("\n"):
        line = line.rstrip()
        if not line.startswith("| `IT-"):
            continue
        cells = [c.strip() for c in line.split("|")]
        assert cells[0] == "" and cells[-1] == "", f"표 형식이 아니다: {line[:60]}"
        cells = cells[1:-1]
        if len(cells) != 7:
            raise SystemExit(f"칸이 {len(cells)}개다(7개여야 한다) — {line[:60]}")
        _testid, feat, prereq, proc, expect, result, note = cells
        m = ROW_PATTERN.match(feat)
        if not m:
            # 머리말의 규칙 설명 줄("`IT-` + 기능ID (예: `IT-AUTH-001`) — ...")처럼
            # 표 모양이지만 데이터 행이 아닌 줄을 건너뛴다.
            continue
        fid, fname = m.group(1), m.group(2)
        id_to_name[fid] = fname
        raw_rows.append([fid, fname, prereq, proc, expect, result, note])

    return raw_rows, id_to_name


def prereq_to_names(raw, id_to_name):
    """선행 기능 칸의 `AUTH-001` 같은 ID 를 기능명으로 바꾼다. 매핑에 없으면 ID 그대로 둔다."""
    raw = raw.strip()
    if raw in ("-", ""):
        return "-"
    ids = re.findall(r"`([A-Za-z0-9-]+)`", raw)
    if not ids:
        return raw
    return " · ".join(id_to_name.get(i, i) for i in ids)


def clean(text):
    return text.replace("<br>", "\n").replace("`", "")


# ─────────────────────────────────────────────── xlsx 유틸 (_build_feature_spec_v5.py 와 동일)
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
            '<sheets><sheet name="통합기능테스트" sheetId="1" r:id="rId1"/></sheets>'
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

    for fname, prereq_names, proc, expect, result, note in rows:
        cells = [fname, prereq_names, proc, expect, result, note]
        sheet.append((None, [(c, v, COL_STYLE[c - 1]) for c, v in enumerate(cells, start=1)]))

    last = len(sheet)
    return sheet_xml(sheet, widths=WIDTHS, freeze=("A5", 0, 4), autofilter=f"A4:F{last}")


def main():
    raw_rows, id_to_name = parse_md()

    ids = [r[0] for r in raw_rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"기능 ID 중복 — 파일을 만들지 않는다: {sorted(dup)}")

    out_rows = []
    for fid, fname, prereq, proc, expect, result, note in raw_rows:
        out_rows.append([
            clean(fname),
            clean(prereq_to_names(prereq, id_to_name)),
            clean(proc),
            clean(expect),
            clean(result),
            clean(note),
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels", WB_RELS)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/worksheets/sheet1.xml", build(out_rows))

    print(f"  {OUT.relative_to(ROOT)}")
    print(f"  행 {len(out_rows)}건 · {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
