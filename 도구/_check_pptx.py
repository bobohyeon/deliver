# -*- coding: utf-8 -*-
"""만든 .pptx 가 파워포인트에서 열리는지 미리 점검한다.

파워포인트는 스키마를 엄격하게 보고, 어긋나면 원인을 알려주지 않고
'복구가 필요합니다' 만 표시한다. 그래서 자주 걸리는 항목을 직접 확인한다.
"""

import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def check(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    problems = []

    # 1) 모든 XML 이 파싱되는지
    for n in names:
        if n.endswith((".xml", ".rels")):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                problems.append(f"XML 파싱 실패  {n}  {e}")

    # 2) 필수 파트가 있는지
    need = ["[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels", "ppt/slideMasters/slideMaster1.xml",
            "ppt/slideLayouts/slideLayout1.xml", "ppt/theme/theme1.xml"]
    for n in need:
        if n not in names:
            problems.append(f"필수 파트 없음  {n}")

    slides = sorted(n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n))
    ct = z.read("[Content_Types].xml").decode()

    for s in slides:
        # 3) Content_Types 등록
        if f"/{s}" not in ct:
            problems.append(f"Content_Types 미등록  {s}")
        # 4) 슬라이드별 rels 존재
        rel = f"ppt/slides/_rels/{s.rsplit('/', 1)[1]}.rels"
        if rel not in names:
            problems.append(f"관계 파일 없음  {rel}")

        raw = z.read(s).decode()
        root = ET.fromstring(raw)

        # 5) txBody 안에 문단이 있는지 (가장 자주 걸리는 항목)
        for tb in root.iter(f"{P}txBody"):
            if tb.find(f"{A}p") is None:
                problems.append(f"문단 없는 txBody  {s}")
                break
        for tb in root.iter(f"{A}txBody"):
            if tb.find(f"{A}p") is None:
                problems.append(f"문단 없는 표 셀 txBody  {s}")
                break

        # 6) 도형 id 중복 (그룹이 쓰는 1번 포함)
        ids = re.findall(r'<p:cNvPr id="(\d+)"', raw)
        dup = [k for k, v in Counter(ids).items() if v > 1]
        if dup:
            problems.append(f"도형 id 중복  {s}  {dup}")

        # 7) 도형에 위치·크기가 있는지
        for sp in root.iter(f"{P}sp"):
            if sp.find(f"{P}spPr/{A}xfrm") is None:
                nm = sp.find(f"{P}nvSpPr/{P}cNvPr")
                problems.append(f"위치 없는 도형  {s}  {nm.get('name') if nm is not None else '?'}")
                break

    # 8) presentation 이 참조하는 rId 가 모두 선언되었는지
    pres = z.read("ppt/presentation.xml").decode()
    rels = z.read("ppt/_rels/presentation.xml.rels").decode()
    declared = set(re.findall(r'Id="(rId\d+)"', rels))
    for rid in set(re.findall(r'r:id="(rId\d+)"', pres)):
        if rid not in declared:
            problems.append(f"presentation 이 참조하는 rId 미선언  {rid}")

    # 9) 관계 대상 파일이 실제로 있는지
    for target in re.findall(r'Target="([^"]+)"', rels):
        full = "ppt/" + target.lstrip("./")
        if full not in names:
            problems.append(f"관계 대상 파일 없음  {full}")

    # 10) 슬라이드 수와 sldIdLst 항목 수가 맞는지
    n_sld = len(re.findall(r"<p:sldId ", pres))
    if n_sld != len(slides):
        problems.append(f"슬라이드 수 불일치  목록 {n_sld} vs 파일 {len(slides)}")

    return slides, problems


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "발표자료.pptx"
    slides, problems = check(target)
    print(f"점검: {target}  (슬라이드 {len(slides)}장)")
    if problems:
        print(f"\n문제 {len(problems)}건")
        for p in problems:
            print("  ", p)
        sys.exit(1)
    print("\n이상 없음 — 파워포인트에서 열 수 있는 형식입니다.")
