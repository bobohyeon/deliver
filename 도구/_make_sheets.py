# -*- coding: utf-8 -*-
"""발표자료 C-2 · C-3 시트를 각각 한 장씩 만든다.

기존 덱이 흑백이므로 색을 전혀 쓰지 않는다. 강조는 검정 채움 하나로만 한다.
본문 영역만 복사해 다른 덱에 붙일 수 있도록, 제목·구분선과 본문 도형을
겹치지 않게 배치한다.

_pptx.py 에 없는 것(둥근 사각형 · 연결선 · 그림 삽입)은 이 파일에서 처리한다.
그림은 build() 가 만든 zip 을 다시 쓰면서 media 와 rels 를 끼워 넣는다.

사용:
    python3 도구/_make_sheets.py
"""

import pathlib
import shutil
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _pptx as P  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOT = ROOT / "산출물" / "캡처" / "분석이력표.png"
OUT = ROOT / "산출물"

IN = P.EMU_IN
BLACK = "000000"     # 제목 · 강조 채움
INK = "1A1A1A"       # 본문
MUTED = "595959"     # 설명
FAINT = "8C8C8C"     # 연결선 · 흐린 숫자
LINE = "BFBFBF"      # 상자 테두리
SOFT = "F2F2F2"      # 옅은 채움
WHITE = "FFFFFF"


def emu(v):
    return int(round(v * IN))


def box(x, y, w, h, paras, fill=None, border=None, border_w=9525,
        radius=9000, anchor="ctr"):
    fill_xml = (f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
                if fill else "<a:noFill/>")
    ln_xml = (f'<a:ln w="{border_w}"><a:solidFill>'
              f'<a:srgbClr val="{border}"/></a:solidFill></a:ln>'
              if border else '<a:ln><a:noFill/></a:ln>')
    geom = (f'<a:prstGeom prst="roundRect"><a:avLst>'
            f'<a:gd name="adj" fmla="val {radius}"/></a:avLst></a:prstGeom>'
            if radius else '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>')
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="상자"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
        f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>{geom}{fill_xml}{ln_xml}</p:spPr>'
        f'<p:txBody><a:bodyPr anchor="{anchor}" lIns="72000" rIns="72000" '
        f'tIns="36000" bIns="36000" wrap="square"><a:normAutofit/></a:bodyPr>'
        f"<a:lstStyle/>{''.join(paras) if paras else '<a:p/>'}</p:txBody></p:sp>"
    )


def text(x, y, w, h, paras, anchor="t"):
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="글"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
        f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>'
        f'<a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr anchor="{anchor}" lIns="0" rIns="0" tIns="0" bIns="0" '
        f'wrap="square"><a:normAutofit/></a:bodyPr>'
        f"<a:lstStyle/>{''.join(paras) if paras else '<a:p/>'}</p:txBody></p:sp>"
    )


def rect(x, y, w, h, fill):
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="면"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
        f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
        f'<a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
    )


def line(x1, y1, x2, y2, clr=FAINT, w=12700, arrow=False):
    ox, oy = min(x1, x2), min(y1, y2)
    cx, cy = abs(x2 - x1), abs(y2 - y1)
    flip = (' flipH="1"' if x2 < x1 else "") + (' flipV="1"' if y2 < y1 else "")
    head = '<a:tailEnd type="triangle" w="med" len="med"/>' if arrow else ""
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="선"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm{flip}><a:off x="{emu(ox)}" y="{emu(oy)}"/>'
        f'<a:ext cx="{emu(cx)}" cy="{emu(cy)}"/></a:xfrm>'
        f'<a:prstGeom prst="line"><a:avLst/></a:prstGeom><a:noFill/>'
        f'<a:ln w="{w}"><a:solidFill><a:srgbClr val="{clr}"/></a:solidFill>{head}</a:ln>'
        f'</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
    )


def pic(x, y, w, h, rid="rId2", border=LINE):
    ln_xml = (f'<a:ln w="9525"><a:solidFill>'
              f'<a:srgbClr val="{border}"/></a:solidFill></a:ln>' if border else "")
    return (
        f'<p:pic><p:nvPicPr><p:cNvPr id="9" name="분석이력표"/>'
        f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch>'
        f"</p:blipFill>"
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
        f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{ln_xml}</p:spPr></p:pic>'
    )


def p(runs, align="l", after=0, line_pct=100000, bullet=None):
    return P._para(runs, align=align, space_after=after, line=line_pct,
                   bullet=bullet)


def head(title):
    """제목 + 구분선. 본문만 복사해 갈 경우 이 두 개는 버리면 된다."""
    return [
        text(0.75, 0.44, 8.0, 0.62, [p([(title, 3200, BLACK, True)])]),
        text(8.9, 0.60, 3.68, 0.30,
             [p([("PDF Brief AI", 1100, FAINT, False)], align="r")]),
        rect(0.75, 1.20, 11.83, 0.011, BLACK),
    ]


# ─────────────────────────────────────────────────────────────
# C-2 데이터 모델 설계
# ─────────────────────────────────────────────────────────────
def sheet_c2():
    s = head("데이터 모델 설계")

    # 관계도 — 왼쪽
    s.append(box(2.15, 1.62, 2.60, 0.72,
                 [p([("documents", 1500, INK, True)], align="ctr")],
                 fill=WHITE, border=LINE))
    s.append(line(3.45, 2.34, 3.45, 2.86))
    s.append(line(2.10, 2.86, 4.80, 2.86))
    s.append(line(2.10, 2.86, 2.10, 3.35, arrow=True))
    s.append(line(4.80, 2.86, 4.80, 3.35, arrow=True))
    s.append(text(1.44, 2.94, 0.60, 0.30,
                  [p([("1 : 1", 1100, MUTED, True)], align="r")]))
    s.append(text(4.90, 2.94, 0.70, 0.30,
                  [p([("1 : N", 1100, BLACK, True)])]))
    s.append(box(0.90, 3.35, 2.40, 0.72,
                 [p([("extracted_texts", 1400, INK, True)], align="ctr")],
                 fill=WHITE, border=LINE))
    # 핵심 상자만 검정 채움 — 덱의 셰브론·표 머리글과 같은 강조 방식
    s.append(box(3.60, 3.35, 2.40, 0.72,
                 [p([("analyses", 1400, WHITE, True)], align="ctr")],
                 fill=BLACK))
    s.append(text(0.90, 4.16, 2.40, 0.28,
                  [p([("추출 원문 1건", 1000, MUTED, False)], align="ctr")]))
    s.append(text(3.60, 4.16, 2.40, 0.28,
                  [p([("분석 결과 N건", 1000, BLACK, True)], align="ctr")]))

    # 실제 화면 근거
    s.append(text(0.75, 4.64, 5.40, 0.26,
                  [p([("실제 화면 — 문서 1건에 summary · category 두 행",
                       1000, MUTED, False)])]))
    s.append(pic(0.75, 4.94, 5.40, 5.40 * 226 / 1056))

    # 설계 판단 — 오른쪽
    items = [
        ("documents 에 summary 컬럼을 두지 않았다",
         "컬럼으로 두면 재분석할 때 이전 결과가 덮여 사라진다"),
        ("1 : N 이라 이력이 남는다",
         "같은 문서에 요약 · 분류 · 재분석 결과가 행으로 쌓인다"),
        ("result_json 은 JSONB",
         "분석기가 늘어나도 테이블을 바꾸지 않는다"),
        ("실행 정보를 함께 기록한다",
         "model_name · prompt_version · tokens · latency_ms\n"
         "→ 자체 모델과 상용 API 를 비교할 근거 데이터"),
    ]
    top = 1.62
    for lead, detail in items:
        s.append(rect(6.75, top + 0.03, 0.035, 0.62, BLACK))
        s.append(text(6.98, top, 5.60, 1.05, [
            p([(lead, 1500, INK, True)], after=500),
            p([(detail, 1200, MUTED, False)], line_pct=118000),
        ]))
        top += 1.22

    s.append(rect(0.75, 6.52, 11.83, 0.007, LINE))
    s.append(text(0.75, 6.66, 11.83, 0.46, [
        p([("남은 과제  ", 1000, BLACK, True),
           ("목록 조회는 현재 2+2N — 문서 9건에 쿼리 20개. 표시용 값을 documents 에 "
            "비정규화하면 2개로 줄어든다. 코드 프리즈 이후라 본프로젝트로 이관했다.",
            1000, MUTED, False)])]))
    return P.slide_xml(s, bg=WHITE)


# ─────────────────────────────────────────────────────────────
# C-3 본문 검색 구현
# ─────────────────────────────────────────────────────────────
def sheet_c3():
    """건수를 주장하지 않는다. 같은 검색어로 결과 없음 → 조회됨 을 캡처로 보인다.

    캡처 자리는 비워 둔다. 비율 2.5 : 1 로 자른 화면을 넣으면 맞는다.
    """
    s = head("본문 검색 구현")

    shots = [
        (1.42, "적용 전", "저장된 값을 그대로 비교했다", "검색 화면 캡처 — 적용 전"),
        (4.28, "적용 후", "공백을 지운 뒤 비교한다", "검색 화면 캡처 — 적용 후"),
    ]
    for top, tag, note, hint in shots:
        s.append(text(0.75, top, 6.00, 0.26, [
            p([(tag + "  ", 1150, BLACK, True), (note, 1050, MUTED, False)])]))
        # 캡처를 넣을 자리. 그림을 얹은 뒤 이 상자는 지운다
        s.append(box(0.75, top + 0.28, 6.00, 2.40,
                     [p([(hint, 1000, FAINT, False)], align="ctr")],
                     fill=SOFT, border=LINE, radius=0))

    items = [
        ("같은 검색어인데 결과가 달라진다",
         '두 화면 모두 "제안자" 로 조회한 것이다'),
        ("왜 못 찾았나",
         '자간이 넓은 공문서는 추출 결과에 "제 안 자" 처럼 공백이 섞인다'),
        ("어떻게 고쳤나",
         "검색어와 저장값 양쪽에서 공백을 지운 뒤 비교한다"),
        ("함께 처리한 것",
         "파일명과 본문을 같이 검색하고, JOIN 대신 서브쿼리로 중복 행을 막는다"),
    ]
    top = 1.70
    for lead, detail in items:
        s.append(rect(7.10, top + 0.03, 0.035, 0.62, BLACK))
        s.append(text(7.33, top, 5.25, 1.05, [
            p([(lead, 1500, INK, True)], after=500),
            p([(detail, 1200, MUTED, False)], line_pct=118000),
        ]))
        top += 1.22

    s.append(rect(0.75, 6.52, 11.83, 0.007, LINE))
    s.append(text(0.75, 6.66, 11.83, 0.46, [
        p([("같은 일을 두 곳에서  ", 1000, BLACK, True),
           ("검색어는 앱에서 re.sub 로, 저장된 본문은 DB에서 regexp_replace 로 "
            "공백을 지운다. 공백만 입력한 경우에는 조건을 걸지 않아 전체 조회로 "
            "새지 않게 했다.", 1000, MUTED, False)])]))
    return P.slide_xml(s, bg=WHITE)


def add_image(path, shot):
    """build() 로 만든 pptx 에 그림 한 장을 끼워 넣는다."""
    tmp = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(path) as src, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.replace(
                    b'<Default Extension="xml"',
                    b'<Default Extension="png" ContentType="image/png"/>'
                    b'<Default Extension="xml"',
                )
            elif item.filename == "ppt/slides/_rels/slide1.xml.rels":
                data = data.replace(
                    b"</Relationships>",
                    b'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org'
                    b'/officeDocument/2006/relationships/image" '
                    b'Target="../media/image1.png"/></Relationships>',
                )
            dst.writestr(item, data)
        dst.writestr("ppt/media/image1.png", shot.read_bytes())
    shutil.move(str(tmp), str(path))


def main():
    if not SHOT.exists():
        raise SystemExit(f"캡처가 없다: {SHOT}  (먼저 _crop_shot.py 실행)")

    c2 = OUT / "C2_데이터모델설계.pptx"
    P.build(str(c2), [sheet_c2()], title="데이터 모델 설계")
    add_image(c2, SHOT)
    print(f"만들었다: {c2.relative_to(ROOT)}  ({c2.stat().st_size:,} bytes)")

    c3 = OUT / "C3_본문검색구현.pptx"
    P.build(str(c3), [sheet_c3()], title="본문 검색 구현")
    print(f"만들었다: {c3.relative_to(ROOT)}  ({c3.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
