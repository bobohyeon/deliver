# -*- coding: utf-8 -*-
"""외부 라이브러리 없이 .pptx 를 만든다.

pptx 는 XML 을 담은 ZIP 이므로 표준 라이브러리만으로 조립할 수 있다.
자리표시자 상속을 쓰지 않고 도형마다 위치·서식을 직접 지정해, 파워포인트 버전에
따라 배치가 달라지는 일이 없도록 한다.

좌표 단위는 EMU (1인치 = 914400). 슬라이드는 16:9 (13.333 x 7.5인치).
"""

import re
import zipfile
from xml.sax.saxutils import escape

EMU_IN = 914400
W = 12192000          # 13.333in
H = 6858000           # 7.5in

# 웹 화면과 같은 색을 쓴다 (frontend/src/styles/tokens.css)
NAVY = "1E40AF"       # 주색 — 헤더·강조
BLUE = "3B82F6"       # 보조 강조
INK = "1F2937"        # 본문
MUTED = "6B7280"      # 설명
LINE = "E5E7EB"       # 구분선·표 테두리
PAPER = "F8FAFC"      # 옅은 배경
WHITE = "FFFFFF"
FONT = "맑은 고딕"

NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)


def _run(text, size, color=INK, bold=False, italic=False):
    """글자 조각 하나. 줄바꿈(\\n)은 OOXML 의 <a:br/> 로 바꾼다.

    문자열 안의 개행 문자는 파워포인트에서 줄바꿈으로 인식되지 않으므로
    조각을 나누고 사이에 <a:br/> 를 넣어야 한다.
    """
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    prop = (
        f'<a:rPr lang="ko-KR" sz="{size}"{b}{i} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr>'
    )
    parts = str(text).split("\n")
    out = []
    for idx, part in enumerate(parts):
        if idx:
            out.append(f"<a:br>{prop}</a:br>")
        if part:
            out.append(f"<a:r>{prop}<a:t>{escape(part)}</a:t></a:r>")
    return "".join(out) if out else f"<a:r>{prop}<a:t></a:t></a:r>"


def _para(runs, align="l", space_after=0, bullet=None, line=100000):
    """runs: [(text, size, color, bold)] 또는 문자열"""
    if isinstance(runs, str):
        runs = [(runs, 1600, INK, False)]
    body = "".join(_run(*r) for r in runs)
    marker = (
        f'<a:buFont typeface="Arial"/><a:buChar char="{bullet}"/>'
        if bullet
        else "<a:buNone/>"
    )
    indent = ' marL="228600" indent="-228600"' if bullet else ' marL="0" indent="0"'
    return (
        f'<a:p><a:pPr algn="{align}"{indent}>'
        f'<a:lnSpc><a:spcPct val="{line}"/></a:lnSpc>'
        f'<a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>{marker}</a:pPr>'
        f"{body}</a:p>"
    )


def _shape(sid, name, x, y, cx, cy, paras, fill=None, line_clr=None,
           anchor="t", line_w=12700):
    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    )
    ln_xml = (
        f'<a:ln w="{line_w}"><a:solidFill><a:srgbClr val="{line_clr}"/></a:solidFill></a:ln>'
        if line_clr
        else '<a:ln><a:noFill/></a:ln>'
    )
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/>'
        f"<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{fill_xml}{ln_xml}</p:spPr>'
        f'<p:txBody><a:bodyPr anchor="{anchor}" lIns="91440" rIns="91440" '
        f'tIns="45720" bIns="45720" wrap="square"><a:normAutofit/></a:bodyPr>'
        # txBody 에는 문단이 최소 하나 있어야 한다. 색칠용 사각형처럼 글이 없는
        # 도형도 빈 문단을 넣어야 파워포인트가 파일을 정상으로 인식한다.
        f"<a:lstStyle/>{''.join(paras) if paras else '<a:p/>'}</p:txBody></p:sp>"
    )


def _table(sid, x, y, cx, col_w, rows, head_fill=NAVY, font=1100):
    """rows[0] 이 머리글. col_w 는 각 열 폭(EMU) 목록."""
    row_h = 340000
    grid = "".join(f'<a:gridCol w="{w}"/>' for w in col_w)
    body = ""
    for ri, row in enumerate(rows):
        head = ri == 0
        cells = ""
        for cell in row:
            txt = _para(
                [(str(cell), font, WHITE if head else INK, head)],
                align="l", line=95000,
            )
            fill = head_fill if head else (PAPER if ri % 2 == 0 else WHITE)
            cells += (
                f'<a:tc><a:txBody><a:bodyPr anchor="ctr" lIns="72000" rIns="72000" '
                f'tIns="36000" bIns="36000"/><a:lstStyle/>{txt}</a:txBody>'
                f'<a:tcPr marL="72000" marR="72000" anchor="ctr">'
                f'<a:lnB w="6350"><a:solidFill><a:srgbClr val="{LINE}"/></a:solidFill></a:lnB>'
                f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>'
            )
        body += f'<a:tr h="{row_h}">{cells}</a:tr>'
    return (
        f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" name="표"/>'
        f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>'
        f"<p:nvPr/></p:nvGraphicFramePr>"
        f'<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{row_h * len(rows)}"/></p:xfrm>'
        f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
        f'<a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>'
        f"{body}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
    )


def slide_xml(shapes, bg=WHITE):
    # 도형 id 를 2부터 다시 매긴다. 1번은 spTree 의 그룹이 쓰므로 겹치면
    # 파워포인트가 파일을 복구 대상으로 판단한다. 호출 측에서 번호를 관리하지
    # 않아도 되도록 여기서 일괄 부여한다.
    body = "".join(shapes)
    counter = [1]

    def renumber(match):
        counter[0] += 1
        return f'<p:cNvPr id="{counter[0]}"{match.group(1)}'

    body = re.sub(r'<p:cNvPr id="\d+"((?:\s+[a-zA-Z:]+="[^"]*")*)', renumber, body)
    shapes = [body]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<p:sld {NS}><p:cSld>"
        f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg}"/></a:solidFill>'
        f"<a:effectLst/></p:bgPr></p:bg>"
        '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
        "</p:nvGrpSpPr><p:grpSpPr/>"
        f"{''.join(shapes)}</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


THEME = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="PDF Brief AI">'
    "<a:themeElements><a:clrScheme name=\"기본\">"
    '<a:dk1><a:srgbClr val="1F2937"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="1E40AF"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>'
    '<a:accent1><a:srgbClr val="1E40AF"/></a:accent1><a:accent2><a:srgbClr val="3B82F6"/></a:accent2>'
    '<a:accent3><a:srgbClr val="6B7280"/></a:accent3><a:accent4><a:srgbClr val="E5E7EB"/></a:accent4>'
    '<a:accent5><a:srgbClr val="16A34A"/></a:accent5><a:accent6><a:srgbClr val="DC2626"/></a:accent6>'
    '<a:hlink><a:srgbClr val="1E40AF"/></a:hlink><a:folHlink><a:srgbClr val="6B7280"/></a:folHlink>'
    '</a:clrScheme><a:fontScheme name="기본">'
    f'<a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface=""/></a:majorFont>'
    f'<a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface=""/></a:minorFont>'
    "</a:fontScheme><a:fmtScheme name=\"기본\">"
    "<a:fillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:fillStyleLst>"
    '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    '<a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    '<a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
    "<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>"
    "<a:bgFillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:bgFillStyleLst>"
    "</a:fmtScheme></a:themeElements></a:theme>"
)

MASTER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f"<p:sldMaster {NS}><p:cSld><p:bg><p:bgPr>"
    '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
    '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    "<p:grpSpPr/></p:spTree></p:cSld>"
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
    'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" '
    'folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
    # 마스터에는 기본 글자 서식 정의가 있어야 한다
    "<p:txStyles><p:titleStyle><a:lvl1pPr>"
    f'<a:defRPr sz="2800" b="1"><a:solidFill><a:srgbClr val="{INK}"/></a:solidFill>'
    f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr>'
    "</a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr>"
    f'<a:defRPr sz="1400"><a:solidFill><a:srgbClr val="{INK}"/></a:solidFill>'
    f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr>'
    "</a:lvl1pPr></p:bodyStyle><p:otherStyle><a:lvl1pPr>"
    f'<a:defRPr sz="1400"><a:solidFill><a:srgbClr val="{INK}"/></a:solidFill>'
    f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr>'
    "</a:lvl1pPr></p:otherStyle></p:txStyles>"
    "</p:sldMaster>"
)

LAYOUT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="빈 화면">'
    '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    "<p:grpSpPr/></p:spTree></p:cSld>"
    '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
)


def build(path, slides, title="발표자료"):
    n = len(slides)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
          '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
          '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
          '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
          '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>']
    for i in range(1, n + 1):
        ct.append(f'<Override PartName="/ppt/slides/slide{i}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    ct.append("</Types>")

    sld_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, n + 1)
    )
    pres = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<p:presentation {NS} saveSubsetFonts=\"1\">"
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{sld_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{W}" cy="{H}"/><p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for i in range(1, n + 1):
        rels.append(f'<Relationship Id="rId{i + 1}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
                    f'Target="slides/slide{i}.xml"/>')
    rels.append(f'<Relationship Id="rId{n + 2}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
                'Target="theme/theme1.xml"/>')
    rels.append("</Relationships>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                   '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
                   "</Relationships>")
        z.writestr("docProps/core.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                   'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                   f"<dc:title>{escape(title)}</dc:title><dc:creator>김보현</dc:creator>"
                   "</cp:coreProperties>")
        z.writestr("docProps/app.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
                   f"<Slides>{n}</Slides></Properties>")
        z.writestr("ppt/presentation.xml", pres)
        z.writestr("ppt/_rels/presentation.xml.rels", "".join(rels))
        z.writestr("ppt/theme/theme1.xml", THEME)
        z.writestr("ppt/slideMasters/slideMaster1.xml", MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
                   "</Relationships>")
        z.writestr("ppt/slideLayouts/slideLayout1.xml", LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
                   "</Relationships>")
        for i, body in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", body)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                       "</Relationships>")
    return path
