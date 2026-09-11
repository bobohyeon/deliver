#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# ① 이 파일의 책임
#    HWPX(.hwpx) 파일에서 본문 텍스트를 뽑아 화면/파일로 낸다. HWPX 는 겉만
#    한글 확장자지 실체는 XML 을 담은 ZIP 이라(OWPML 규격) 표준 라이브러리만으로
#    연다 — 추가 설치가 필요 없다. 문단(<hp:p>)마다 한 줄로 내고, 표는 셀 문단이
#    순서대로 풀려 "추출된 텍스트"다운 모양이 된다(파인튜닝 입력과 결이 맞는다).
# ② 다른 파일과의 관계
#    데이터셋/파인튜닝/ 파이프라인의 맨 앞. 여기서 나온 텍스트를 사람이 검토해
#    라벨을 붙이고 validate_sft.py 로 검사한다. 구 바이너리 .hwp 는 이 도구가
#    아니라 한글/LibreOffice/pyhwp 로 txt 변환한다(README 참고).
# ③ Spring 비교
#    docx 를 POI(XWPFDocument) 로 열어 문단 텍스트를 훑는 것과 같은 일을,
#    한글 OWPML 에 대해 표준 라이브러리(zipfile+ElementTree)로 한 것이다.
# ---------------------------------------------------------------------------
"""사용법:
    python3 hwpx_to_text.py 파일.hwpx                # 화면에 출력
    python3 hwpx_to_text.py 파일.hwpx -o 파일.txt     # 파일로 저장
    python3 hwpx_to_text.py *.hwpx --outdir out       # 여러 개 일괄 → out/*.txt

주의: 나(Kiro)는 실물 .hwpx 를 받을 수 없어 이 도구를 가짜 hwpx 로 로직만
검증했다. 실제 파일로 한 번 돌려보고 결과가 이상하면 알려주면 고친다."""

import argparse
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

SECTION_RE = re.compile(r"Contents/section\d+\.xml$")


def _local(tag):
    """'{네임스페이스}t' → 't'. 한글 버전마다 네임스페이스가 달라 접두어로 판단."""
    return tag.rsplit("}", 1)[-1]


def _walk(el, lines, cur):
    """문단(p) 단위로 줄을 만든다. 표 셀 등 중첩 문단은 자기 줄로 따로 나가
    바깥 문단에 겹쳐 들어가지 않는다(중복 방지)."""
    tag = _local(el.tag)
    if tag == "t":                       # 실제 글자가 담긴 run 텍스트
        cur.append("".join(el.itertext()))
        return
    if tag == "p":                       # 문단 하나 = 한 줄
        mine = []
        for child in el:
            _walk(child, lines, mine)
        lines.append("".join(mine))
        return
    for child in el:
        _walk(child, lines, cur)


def extract_hwpx(path):
    """HWPX 한 개에서 본문 텍스트를 뽑아 문자열로 돌려준다."""
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError(f"{path}: ZIP 이 아니다. 구 .hwp 바이너리일 수 있다(한글/LibreOffice 로 변환 필요)")
    lines = []
    with zf:
        names = sorted(n for n in zf.namelist() if SECTION_RE.search(n))
        if not names:
            raise ValueError(f"{path}: Contents/section*.xml 이 없다. HWPX 가 아닐 수 있다")
        for n in names:
            root = ET.fromstring(zf.read(n))
            _walk(root, lines, [])
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="HWPX → 텍스트 추출 (표준 라이브러리만)")
    ap.add_argument("files", nargs="+", help="입력 .hwpx 파일들")
    ap.add_argument("-o", "--out", help="단일 파일 출력 경로")
    ap.add_argument("--outdir", help="여러 파일을 이 폴더에 <원본이름>.txt 로 저장")
    args = ap.parse_args(argv[1:])

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)

    rc = 0
    for path in args.files:
        try:
            text = extract_hwpx(path)
        except (ValueError, ET.ParseError) as e:
            print(f"[실패] {e}", file=sys.stderr)
            rc = 1
            continue
        if args.outdir:
            base = os.path.splitext(os.path.basename(path))[0] + ".txt"
            dest = os.path.join(args.outdir, base)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[저장] {dest} ({len(text)}자)")
        elif args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[저장] {args.out} ({len(text)}자)")
        else:
            print(text)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
